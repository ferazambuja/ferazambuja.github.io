#!/usr/bin/env python3
"""Measure the built site in a real browser engine.

Every other check in this repository is a regex over markup or CSS text. That
cannot see the defects that matter most to a reader: an anchor that resolves
correctly but lands behind the sticky header, a sidebar that overlaps the bar
it is supposed to sit below, or a page that scrolls sideways on a phone.

Those are geometry, and geometry needs layout. This script loads the built
pages in headless Chrome, reads the measurements back out of the document
title, and fails on the relationships rather than on a declared constant --
so a header that grows past its reserve is caught by the reserve no longer
being enough, not by someone remembering to update a number.
"""

from __future__ import annotations

import argparse
import http.server
import re
import shutil
import socketserver
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

CHROME_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)

# Injected into a temporary copy of the page. Everything the checks need is
# reported through document.title, which --dump-dom returns.
PROBE = """
<script>
addEventListener("load", function () {
  if (%(hash)s) { location.hash = %(hash)s; }
  setTimeout(function () {
    var out = [];
    var doc = document.documentElement;
    var bar = document.querySelector(".topbar");
    var barH = bar ? Math.round(bar.getBoundingClientRect().height) : 0;
    out.push("bar=" + barH);
    out.push("overflow=" + (doc.scrollWidth - doc.clientWidth));
    var target = %(hash)s ? document.getElementById(%(hash)s) : null;
    if (target) {
      out.push("anchorTop=" + Math.round(target.getBoundingClientRect().top));
    }
    var side = document.querySelector(".sidebar");
    if (side && getComputedStyle(side).position === "sticky") {
      out.push("sidebarTop=" + Math.round(side.getBoundingClientRect().top));
    }
    document.title = out.join("|");
  }, 400);
});
</script>
"""


# The theme has three states and only one of them can be forced from the
# command line, so drive the root element directly and read the tokens back.
# Clicking the real control rather than calling a helper keeps the handler,
# the stored choice, and the stylesheet on one tested path.
THEME_PROBE = """
<script>
addEventListener("load", function () {
  setTimeout(function () {
    var root = document.documentElement;
    var out = [];
    function tokens() {
      var style = getComputedStyle(root);
      return style.getPropertyValue("--bg").trim() + "," +
             style.getPropertyValue("--ink").trim();
    }
    root.setAttribute("data-theme", "dark");
    out.push("dark=" + tokens());
    root.setAttribute("data-theme", "light");
    out.push("light=" + tokens());
    var button = document.querySelector(".theme-toggle");
    out.push("control=" + (button ? "1" : "0"));
    out.push("label=" + (button && button.getAttribute("aria-label") ? "1" : "0"));
    if (button) {
      button.click();
      out.push("afterClick=" + tokens());
      out.push("stored=" + (function () {
        try { return localStorage.getItem("theme"); } catch (e) { return "blocked"; }
      })());
    }
    document.title = out.join("|");
  }, 400);
});
</script>
"""


# Text contrast is a property of a color token against the surface it lands
# on, and a token that clears the page background can still fail on a tinted
# one. Reading the stylesheet cannot tell you which pairs actually occur, so
# this resolves the computed color of every visible HTML text node against its
# composited ancestor backgrounds and applies the WCAG AA text-contrast ratio
# for its size.
# Both themes run in one browser load; forcing a computed-style read after each
# switch makes the theme change synchronous even though page loading is not.
CONTRAST_PROBE = """
<script>
addEventListener("load", function () {
  setTimeout(function () {
    function parseColor(value) {
      value = String(value || "").trim().toLowerCase();
      if (value === "transparent") { return [0, 0, 0, 0]; }
      var parts = value.match(/-?\\d*\\.?\\d+(?:e[+-]?\\d+)?/g);
      if (!parts || parts.length < 3) { return null; }
      var channels = parts.slice(0, 3).map(Number);
      if (value.indexOf("color(srgb ") === 0) {
        channels = channels.map(function (channel) { return channel * 255; });
      } else if (value.indexOf("rgb") !== 0) {
        return null;
      }
      return channels.concat(parts.length > 3 ? Number(parts[3]) : 1);
    }
    function over(top, bottom) {
      var alpha = top[3] + bottom[3] * (1 - top[3]);
      if (alpha <= 0) { return [0, 0, 0, 0]; }
      return [0, 1, 2].map(function (index) {
        return (top[index] * top[3] +
                bottom[index] * bottom[3] * (1 - top[3])) / alpha;
      }).concat(alpha);
    }
    function backgroundFor(element) {
      var layers = [];
      while (element) {
        var style = getComputedStyle(element);
        if (style.backgroundImage !== "none") { return null; }
        var color = parseColor(style.backgroundColor);
        if (!color) { return null; }
        layers.push(color);
        element = element.parentElement;
      }
      var result = [255, 255, 255, 1];
      for (var index = layers.length - 1; index >= 0; index -= 1) {
        result = over(layers[index], result);
      }
      return result;
    }
    function luminance(rgb) {
      var linear = rgb.slice(0, 3).map(function (channel) {
        channel /= 255;
        return channel <= 0.04045
          ? channel / 12.92
          : Math.pow((channel + 0.055) / 1.055, 2.4);
      });
      return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
    }
    function measure(theme) {
      document.documentElement.setAttribute("data-theme", theme);
      getComputedStyle(document.documentElement).color;
      var worst = 99, worstNeed = 0, worstWhere = "none";
      var failing = 0, unsupported = 0;
      Array.prototype.forEach.call(document.querySelectorAll("*"), function (el) {
        var text = Array.prototype.some.call(el.childNodes, function (node) {
          return node.nodeType === 3 && node.textContent.trim();
        });
        if (!text || el.getClientRects().length === 0) { return; }
        var style = getComputedStyle(el);
        if (style.visibility !== "visible" || style.display === "none") { return; }
        var background = backgroundFor(el);
        var foreground = parseColor(style.color);
        if (!background || !foreground) { unsupported += 1; return; }
        foreground = over(foreground, background);
        var size = parseFloat(style.fontSize);
        var weight = parseInt(style.fontWeight, 10) || 400;
        var need = (size >= 24 || (size >= 18.6667 && weight >= 700)) ? 3 : 4.5;
        var first = luminance(foreground), second = luminance(background);
        var ratio = (Math.max(first, second) + 0.05) /
                    (Math.min(first, second) + 0.05);
        if (ratio < need) { failing += 1; }
        if (ratio - need < worst - worstNeed) {
          worst = ratio;
          worstNeed = need;
          worstWhere = (el.tagName + "." + String(el.className || ""))
            .replace(/[|=\\s]+/g, "-").slice(0, 40);
        }
      });
      return {
        failing: failing,
        unsupported: unsupported,
        worst: worst.toFixed(6),
        need: worstNeed.toFixed(1),
        where: worstWhere,
      };
    }
    var out = [];
    ["light", "dark"].forEach(function (theme) {
      var result = measure(theme);
      Object.keys(result).forEach(function (key) {
        out.push(theme + key[0].toUpperCase() + key.slice(1) + "=" + result[key]);
      });
    });
    document.title = out.join("|");
  }, 400);
});
</script>
"""


# Exercise the real ES-module form. The build-time Python result is carried in
# data-reference attributes, so the first assertion crosses all three layers:
# Python fallback, browser model, and controller rendering. Submitting changed,
# near-neutral, and refused inputs covers the useful path and both user-facing
# edge states. Resource counts prove recalculation does not start a network
# request.
CALCULATOR_PROBE = """
<script>
addEventListener("load", function () {
  setTimeout(function () {
    var out = [];
    var form = document.querySelector("#cam16-calculator");
    var status = document.querySelector("#calculator-status");
    var targets = Array.prototype.slice.call(
      document.querySelectorAll("[data-model][data-correlate]")
    );
    if (!form || !status || targets.length !== 12) {
      document.title = "ready=0";
      return;
    }
    out.push("ready=" + (status.textContent.indexOf("Calculated locally") >= 0 ? "1" : "0"));
    out.push("default=" + (targets.every(function (target) {
      return target.textContent.trim() === target.getAttribute("data-reference");
    }) ? "1" : "0"));
    var resources = performance.getEntriesByType("resource").length;

    form.elements.namedItem("x").value = "46";
    form.requestSubmit();
    var changed = targets.find(function (target) {
      return target.dataset.model === "cam16" && target.dataset.correlate === "J";
    });
    out.push("changed=" + (changed.textContent.trim() !== changed.dataset.reference ? "1" : "0"));

    [["x", "95.047"], ["y", "100"], ["z", "108.883"],
     ["white_x", "95.047"], ["white_y", "100"], ["white_z", "108.883"],
     ["la", "2000"]]
      .forEach(function (item) { form.elements.namedItem(item[0]).value = item[1]; });
    form.requestSubmit();
    var hueTargets = targets.filter(function (target) {
      return target.dataset.correlate === "h";
    });
    var chromaTargets = targets.filter(function (target) {
      return ["C", "M", "s"].indexOf(target.dataset.correlate) >= 0;
    });
    out.push("nearNeutral=" + (
      hueTargets.every(function (target) { return target.textContent.trim() === "n/a"; }) &&
      chromaTargets.every(function (target) { return target.textContent.trim() === "~0"; }) &&
      status.textContent.indexOf("Hue is unresolved") >= 0 ? "1" : "0"
    ));

    ["x", "y", "z"].forEach(function (name) {
      form.elements.namedItem(name).value = "0";
    });
    form.requestSubmit();
    out.push("refused=" + (
      status.textContent.indexOf("Cannot calculate") === 0 &&
      targets.every(function (target) { return target.textContent.trim() === "—"; })
        ? "1" : "0"
    ));
    out.push("network=" + (
      performance.getEntriesByType("resource").length === resources ? "0" : "1"
    ));
    document.title = out.join("|");
  }, 900);
});
</script>
"""


# The homepage is a hiring front door, not a long-form article. The opening
# statement and owner-authored artwork may lead, but they must not consume the
# whole desktop viewport and hide every project behind a scroll.
HOME_FLOW_PROBE = """
<script>
addEventListener("load", function () {
  setTimeout(function () {
    var selected = document.querySelector("#selected-work");
    document.title = selected
      ? "selectedTop=" + Math.round(selected.getBoundingClientRect().top) +
        "|selectedBottom=" + Math.round(selected.getBoundingClientRect().bottom) +
        "|viewport=" + window.innerHeight
      : "selectedTop=-1|selectedBottom=-1|viewport=" + window.innerHeight;
  }, 400);
});
</script>
"""


def find_chrome() -> str | None:
    for name in CHROME_CANDIDATES:
        found = shutil.which(name) or (name if Path(name).exists() else None)
        if found:
            return found
    return None


@contextmanager
def serving(root: Path):
    """Serve the generated pages from a local origin."""

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):  # request noise, not results
            pass

    handler = lambda *a, **kw: Quiet(*a, directory=str(root), **kw)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield httpd.server_address[1]
        finally:
            httpd.shutdown()


def report(chrome: str, root: Path, port: int, route: str, width: int,
           probe: str) -> dict[str, str]:
    """Run one page with a probe injected and read its findings back."""

    page = root / route.strip("/") / "index.html" if route != "/" else root / "index.html"
    original = page.read_text(encoding="utf-8")
    page.write_text(original.replace("</body>", probe + "</body>"), encoding="utf-8")
    try:
        result = subprocess.run(
            [
                chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                f"--window-size={width},900", "--virtual-time-budget=6000",
                "--dump-dom", f"http://127.0.0.1:{port}{route}",
            ],
            capture_output=True, text=True, timeout=90,
        )
    finally:
        page.write_text(original, encoding="utf-8")
    title = re.search(r"<title>([^<]*)</title>", result.stdout)
    if not title:
        raise SystemExit(f"no measurement returned for {route}")
    values = {}
    for part in title.group(1).split("|"):
        key, _, raw = part.partition("=")
        values[key] = raw
    return values


def measure(chrome: str, root: Path, port: int, route: str, width: int,
            anchor: str | None) -> dict[str, int]:
    literal = f'"{anchor}"' if anchor else "null"
    found = report(chrome, root, port, route, width, PROBE % {"hash": literal})
    try:
        return {key: int(value) for key, value in found.items()}
    except ValueError as error:
        raise SystemExit(f"invalid layout measurement for {route}: {found}") from error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=Path("_site"))
    parser.add_argument(
        "--require-browser",
        action="store_true",
        help="fail instead of skipping when Chrome or Chromium is unavailable",
    )
    args = parser.parse_args()
    root = args.site.resolve()

    chrome = find_chrome()
    if chrome is None:
        message = "render check skipped: no Chrome or Chromium binary found"
        if args.require_browser:
            print(f"FAIL {message}", file=sys.stderr)
            return 1
        print(message)
        return 0

    failures: list[str] = []
    checks = 0

    def route_for(page: Path) -> str:
        relative = page.relative_to(root)
        if relative == Path("index.html"):
            return "/"
        return f"/{relative.parent.as_posix()}/"

    # Anchor navigation is how a reader reaches an implementation excerpt from
    # a method page, and how the landing page skips to its code.
    anchored = [("/imaging/", "how-it-is-computed")]
    anchored.extend(
        (
            f"/imaging/studies/{page.parent.name}/",
            "implementation",
        )
        for page in sorted((root / "imaging" / "studies").glob("*/index.html"))
    )
    with serving(root) as port:
        for route, anchor in anchored:
            m = measure(chrome, root, port, route, 1400, anchor)
            checks += 1
            if m["anchorTop"] < m["bar"]:
                failures.append(
                    f"{route}#{anchor}: target lands {m['anchorTop']}px from the top, "
                    f"behind a {m['bar']}px sticky header"
                )
            if "sidebarTop" in m and m["sidebarTop"] < m["bar"]:
                failures.append(
                    f"{route}: sticky sidebar at {m['sidebarTop']}px overlaps the "
                    f"{m['bar']}px header"
                )

        # A phone reader must never scroll sideways. Wide code and figures are
        # expected to scroll inside their own box, not to widen the document.
        # Exercise every rendered page, not a hand-picked sample. The site is
        # small enough that a missing responsive rule on a report or method
        # should not be accepted merely because its study page looks correct.
        mobile_routes = tuple(
            route_for(page)
            for page in sorted(root.rglob("index.html"))
            if 'http-equiv="refresh"' not in page.read_text(encoding="utf-8")
        )
        for route in mobile_routes:
            m = measure(chrome, root, port, route, 390, None)
            checks += 1
            if m["overflow"] > 0:
                failures.append(
                    f"{route}: document is {m['overflow']}px wider than the viewport "
                    "at 390px"
                )

        # Only the two explicit choices can be asserted here: the untouched
        # default follows the runner's own color preference, which differs
        # between a developer's machine and CI. That the media query guards
        # itself against an explicit light choice is a property of the
        # stylesheet text, and test_site.py checks it there -- asserting it
        # through a selector written into this probe would only restate a
        # rule of CSS back to itself.
        theme = report(chrome, root, port, "/imaging/", 1400, THEME_PROBE)
        if theme.get("dark") == theme.get("light"):
            failures.append(
                "theme: the light and dark choices resolve to the same tokens "
                f"({theme.get('dark')})"
            )
        if theme.get("control") != "1" or theme.get("label") != "1":
            failures.append("theme: no labelled toggle was added to the header")
        # The probe leaves the root on "light", so one click must reach dark
        # and record that choice for the next page the reader opens.
        if theme.get("afterClick") != theme.get("dark"):
            failures.append(
                "theme: the toggle did not switch the applied tokens "
                f"({theme.get('afterClick')})"
            )
        if theme.get("stored") not in {"dark", "blocked"}:
            failures.append(
                f"theme: the choice was not persisted (stored {theme.get('stored')})"
            )

        calculator = report(
            chrome,
            root,
            port,
            "/imaging/cam16-hellwig-comparator/",
            1400,
            CALCULATOR_PROBE,
        )
        checks += 6
        for key in ("ready", "default", "changed", "nearNeutral", "refused"):
            if calculator.get(key) != "1":
                failures.append(
                    f"calculator: {key} browser flow failed ({calculator})"
                )
        if calculator.get("network") != "0":
            failures.append("calculator: recalculation started a network request")

        home_flow = report(chrome, root, port, "/", 1280, HOME_FLOW_PROBE)
        checks += 1
        selected_top = int(home_flow.get("selectedTop", "-1"))
        selected_bottom = int(home_flow.get("selectedBottom", "-1"))
        viewport = int(home_flow.get("viewport", "0"))
        if selected_top < 0:
            failures.append("homepage: Selected work heading is missing")
        elif selected_bottom > viewport:
            failures.append(
                "homepage: opening artwork hides Selected work below the "
                f"desktop viewport ({selected_bottom}px > {viewport}px)"
            )

        # New routes can introduce new token/surface pairs, so sampling pages
        # is not a durable contrast contract. Exercise every generated
        # route in both explicit themes. One page load measures both themes.
        for route in mobile_routes:
            found = report(chrome, root, port, route, 1400, CONTRAST_PROBE)
            checks += 2
            for scheme in ("light", "dark"):
                prefix = scheme
                unsupported = int(found.get(prefix + "Unsupported", "0"))
                if unsupported:
                    failures.append(
                        f"{route} [{scheme}]: {unsupported} text element(s) "
                        "use a color or background the contrast probe cannot "
                        "evaluate"
                    )
                if int(found.get(prefix + "Failing", "0")) > 0:
                    failures.append(
                        f"{route} [{scheme}]: {found[prefix + 'Failing']} text "
                        f"element(s) below WCAG AA text contrast; worst is "
                        f"{float(found[prefix + 'Worst']):.3f}:1 where "
                        f"{float(found[prefix + 'Need']):.1f}:1 is required, at "
                        f"{found.get(prefix + 'Where')}"
                    )

    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        print(f"\n{len(failures)} problem(s)", file=sys.stderr)
        return 1
    print(
        f"render check: {checks} measured checks, no obscured anchors or "
        "overflow; both themes apply, the toggle persists, and every "
        "measured HTML text element meets WCAG AA contrast in both themes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
