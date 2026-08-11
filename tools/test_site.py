#!/usr/bin/env python3
"""Verify a built site before it is published.

Checks that every internal link and image resolves to a file that exists, that
no Markdown-era link survived the rewrite, and that every published source excerpt
is byte-identical to the range it cites in the tested source.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
from pathlib import Path
from urllib.parse import unquote

from build_site import (
    COMPARATOR_CI_URL,
    THEME_BOOTSTRAP,
    COMPARATOR_LEGACY_ROUTE,
    COMPARATOR_ROUTE,
    COMPARATOR_URL,
    IMAGING,
    PROFILE_ASSETS,
    SITE_URL,
)

LINK = re.compile(r'(?:href|src)="([^"]+)"')
ID = re.compile(r'\bid="([^"]+)"')
IMAGE = re.compile(r'<img\b(?P<attrs>[^>]*)>', re.S)
ALT = re.compile(r'\balt="(?P<value>[^"]*)"')
EXCERPT = re.compile(
    r'<pre class="code highlight"><code>(?P<code>.*?)</code></pre>\s*'
    r'<p class="excerpt-src"><a href="(?P<url>[^"]+)">(?P<source>[^<]+)</a>'
    r"\s*·\s*lines (?P<first>\d+)–(?P<last>\d+)",
    re.S,
)
PROFILE_SITE_LINK = re.compile(
    r"https://ferazambuja\.github\.io(?P<route>/[^\s\)\]\"'<>]*)"
)
LEGACY_REDIRECT_ROUTE = re.compile(
    r'["\']#study-[^"\']+["\']\s*:\s*["\'](?P<route>/imaging/[^"\']+)["\']'
)

# Contrast floor for body-sized text. Inline code, selected navigation, cards,
# and callouts can put any text token on any declared text surface. Checking
# the full product prevents a new selector from creating an unguarded pair.
TOKEN_CONTRAST_PAIRS = tuple(
    (foreground, background)
    for foreground in ("--ink", "--ink-soft", "--ink-faint", "--accent")
    for background in ("--bg", "--surface", "--rule-soft", "--accent-soft")
)
CONTRAST_FLOOR = 4.5


def relative_luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    if len(value) == 3:
        value = "".join(channel * 2 for channel in value)
    channels = []
    for index in (0, 2, 4):
        raw = int(value[index : index + 2], 16) / 255
        channels.append(
            raw / 12.92 if raw <= 0.04045 else ((raw + 0.055) / 1.055) ** 2.4
        )
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def hdr_manifest(site_dir: Path) -> dict[str, str]:
    """Return the recorded digest for every HDR asset."""

    listing = site_dir / "hdr" / "manifest.sha256"
    if not listing.is_file():
        return {}
    entries = {}
    for line in listing.read_text(encoding="utf-8").splitlines():
        digest, _, name = line.partition("  ")
        if digest and name:
            entries[name.strip()] = digest.strip()
    return entries


def route_to_file(root: Path, route: str) -> Path:
    clean = unquote(route.split("#")[0].split("?")[0])
    if clean.endswith("/"):
        return root / clean.strip("/") / "index.html"
    return root / clean.lstrip("/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=Path("_site"))
    parser.add_argument("--imaging", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--comparator", type=Path, required=True)
    args = parser.parse_args()
    root = args.site.resolve()
    content = args.imaging.resolve()
    profile = args.profile.resolve()
    comparator = args.comparator.resolve()

    failures: list[str] = []
    pages = sorted(root.rglob("*.html"))
    if not pages:
        print("no pages built", file=sys.stderr)
        return 1

    internal = 0
    external = 0
    checked_excerpts = 0
    excerpt_ranges: set[tuple[str, int, int]] = set()

    for page in pages:
        rel = page.relative_to(root)
        text = page.read_text(encoding="utf-8")
        page_ids = set(ID.findall(text))

        if len(re.findall(r"<h1(?:\s|>)", text)) != 1:
            failures.append(f"{rel}: page must contain exactly one H1")
        if len(re.findall(r'<link rel="canonical"', text)) != 1:
            failures.append(f"{rel}: page must contain exactly one canonical URL")
        expected_current = 0 if 'http-equiv="refresh"' in text else 1
        if text.count('aria-current="page"') != expected_current:
            failures.append(
                f"{rel}: expected {expected_current} current-page navigation link(s)"
            )

        # The stored theme has to be on the root element before the first
        # paint. If this ever moves into the deferred script, or lands after
        # the stylesheet stops being render-blocking, a reader who chose dark
        # gets a white flash on every navigation -- which no other check here
        # would notice, because the page ends up correct either way.
        if THEME_BOOTSTRAP not in text:
            failures.append(f"{rel}: theme is applied too late to avoid a flash")
        elif text.index(THEME_BOOTSTRAP) > text.index("</head>"):
            failures.append(f"{rel}: theme bootstrap runs after the head")

        # A page either offers a preview image or it does not. Check the
        # shape rather than naming which page is allowed one: pinning it to
        # the home page meant any new route shipped as a bare text card in
        # every feed and chat that unfurls it, and nothing said so.
        og_images = re.findall(
            r'<meta property="og:image" content="([^"]+)"', text
        )
        twitter_images = re.findall(
            r'<meta name="twitter:image" content="([^"]+)"', text
        )
        og_image_alts = re.findall(
            r'<meta property="og:image:alt" content="([^"]*)"', text
        )
        twitter_image_alts = re.findall(
            r'<meta name="twitter:image:alt" content="([^"]*)"', text
        )
        image_meta = len(og_images)
        if og_images != twitter_images or image_meta > 1:
            failures.append(f"{rel}: social-image metadata is inconsistent")
        if image_meta:
            if (
                len(og_image_alts) != 1
                or og_image_alts != twitter_image_alts
                or not html.unescape(og_image_alts[0]).strip()
            ):
                failures.append(f"{rel}: social image needs matching useful alt text")
        elif og_image_alts or twitter_image_alts:
            failures.append(f"{rel}: social-image alt text has no image")
        expected_card = "summary_large_image" if image_meta else "summary"
        if f'<meta name="twitter:card" content="{expected_card}">' not in text:
            failures.append(f"{rel}: social-card type does not match its image")
        for declared in og_images:
            if not declared.startswith(SITE_URL):
                failures.append(f"{rel}: social image is not an absolute site URL")
            elif not route_to_file(root, declared[len(SITE_URL):]).is_file():
                failures.append(f"{rel}: social image does not resolve: {declared}")
        if "<!-- " in text and "_ART -->" in text:
            failures.append(f"{rel}: unresolved home-page placement marker")

        for image in IMAGE.finditer(text):
            alt = ALT.search(image.group("attrs"))
            if alt is None or not html.unescape(alt.group("value")).strip():
                failures.append(f"{rel}: image is missing useful alt text")

        for target in LINK.findall(text):
            target = html.unescape(target)
            if target.startswith("#"):
                fragment = unquote(target[1:])
                if fragment and fragment not in page_ids:
                    failures.append(f"{rel}: dead same-page anchor {target!r}")
                internal += 1
                continue
            if target.startswith(("http://", "https://", "mailto:", "data:")):
                external += 1
                continue
            if not target.startswith("/"):
                failures.append(f"{rel}: link not rewritten to a route: {target!r}")
                continue
            if ".md" in target:
                failures.append(f"{rel}: Markdown link survived: {target!r}")
                continue
            resolved = route_to_file(root, target)
            if not resolved.exists():
                failures.append(f"{rel}: dead internal link {target!r}")
                continue
            _, separator, raw_fragment = target.partition("#")
            if separator and raw_fragment and resolved.suffix == ".html":
                target_ids = set(ID.findall(resolved.read_text(encoding="utf-8")))
                fragment = unquote(raw_fragment)
                if fragment not in target_ids:
                    failures.append(f"{rel}: dead target anchor {target!r}")
                    continue
            internal += 1

        for match in EXCERPT.finditer(text):
            checked_excerpts += 1
            source = content / match.group("source")
            if not source.exists():
                failures.append(f"{rel}: excerpt source missing: {match.group('source')}")
                continue
            lines = source.read_text(encoding="utf-8").splitlines()
            first = int(match.group("first"))
            last = int(match.group("last"))
            excerpt_ranges.add((match.group("source"), first, last))
            expected = "\n".join(lines[first - 1 : last])
            shown = html.unescape(re.sub(r"<[^>]+>", "", match.group("code")))
            if shown != expected:
                failures.append(
                    f"{rel}: excerpt does not match {match.group('source')} "
                    f"lines {first}-{last}"
                )

    required = [
        "index.html",
        "imaging/index.html",
        "assets/site.css",
        "assets/theme.js",
        ".nojekyll",
    ]
    for name in required:
        if not (root / name).exists():
            failures.append(f"missing required artifact: {name}")

    # A sticky header hides whatever a hash link scrolls to. The method
    # pointers and the landing skip link both navigate by anchor, so the
    # scroll reserve is load-bearing, not cosmetic. Keep that reserve and the
    # desktop sidebar offset on one declared clearance so future layout edits
    # cannot make the two sticky surfaces drift independently.
    stylesheet = root / "assets" / "site.css"
    if stylesheet.is_file():
        css = stylesheet.read_text(encoding="utf-8")
        sticky_header = re.search(
            r"\.topbar\s*\{[^}]*position:\s*sticky", css, re.S
        )
        if sticky_header:
            clearance = re.search(
                r"--topbar-clearance:\s*([0-9]+(?:\.[0-9]+)?)rem\s*;", css
            )
            if clearance is None:
                failures.append("sticky topbar has no shared clearance value")
            elif float(clearance.group(1)) < 4.5:
                failures.append(
                    "topbar clearance is smaller than the measured safe reserve"
                )

            html_block = re.search(r"html\s*\{(?P<body>[^}]*)\}", css, re.S)
            if html_block is None or not re.search(
                r"scroll-padding-top:\s*var\(--topbar-clearance\)",
                html_block.group("body"),
            ):
                failures.append(
                    "sticky topbar does not reserve its shared clearance for anchors"
                )

            sidebar = re.search(r"\.sidebar\s*\{(?P<body>[^}]*)\}", css, re.S)
            if sidebar is None or not re.search(
                r"top:\s*var\(--topbar-clearance\)", sidebar.group("body")
            ):
                failures.append(
                    "desktop sidebar does not use the shared topbar clearance"
                )

        # Three theme states, and the one nobody tests is the default: no
        # data-theme attribute, dark system. It cannot be forced from a
        # command line, so check the structure that produces it. The media
        # block has to exclude an explicit light choice, and it has to define
        # exactly what the explicit dark choice defines -- otherwise a reader
        # who never touches the toggle sees a different page from one who
        # picks dark, and only one of the two is ever looked at.
        def declared(block: str) -> dict[str, str]:
            # Comments first. These blocks are heavily annotated, and a note
            # that names a token as "--bg: 5.24:1" parses as a declaration
            # whose value runs to the next semicolon -- swallowing the real
            # declaration that follows it.
            block = re.sub(r"/\*.*?\*/", " ", block, flags=re.S)
            return {
                name: value.strip()
                for name, value in re.findall(
                    r"(--[a-z0-9-]+)\s*:\s*([^;]+);", block
                )
            }

        base = re.search(r"(?<!\S):root\s*\{(?P<body>[^}]*)\}", css, re.S)
        by_system = re.search(
            r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*"
            r':root:not\(\[data-theme="light"\]\)\s*\{(?P<body>[^}]*)\}',
            css,
            re.S,
        )
        by_choice = re.search(
            r':root\[data-theme="dark"\]\s*\{(?P<body>[^}]*)\}', css, re.S
        )
        if base is None:
            failures.append("stylesheet declares no base theme tokens")
        elif by_choice is None:
            failures.append("stylesheet offers no explicit dark theme")
        elif by_system is None:
            failures.append(
                "no dark rule guarded against an explicit light choice: a "
                "reader who picks light on a dark system would be overruled"
            )
        else:
            light, system, choice = (
                declared(base.group("body")),
                declared(by_system.group("body")),
                declared(by_choice.group("body")),
            )
            if system != choice:
                drifted = sorted(
                    set(system) ^ set(choice)
                    or {k for k in system if system[k] != choice.get(k)}
                )
                failures.append(
                    "the system-preference and explicit dark themes disagree "
                    f"on: {', '.join(drifted)}"
                )
            undefined = sorted(set(choice) - set(light) - {"color-scheme"})
            if undefined:
                failures.append(
                    "dark-only tokens have no light value, leaving the default "
                    f"theme undefined: {', '.join(undefined)}"
                )

            # A palette that reads well to its author can still fail a reader
            # on a bright screen. Check the ratios rather than trusting the
            # eye, in every theme -- a second palette doubles the surface for
            # this, and only one of the two is ever looked at closely.
            for theme_name, overrides in (("light", {}), ("dark", choice)):
                tokens = {**light, **overrides}
                for foreground, background in TOKEN_CONTRAST_PAIRS:
                    pair = (tokens.get(foreground), tokens.get(background))
                    if not all(value and value.startswith("#") for value in pair):
                        continue
                    ratio = contrast_ratio(*pair)
                    if ratio < CONTRAST_FLOOR:
                        failures.append(
                            f"{theme_name} theme: {foreground} on {background} "
                            f"is {ratio:.2f}:1, under the {CONTRAST_FLOOR}:1 floor"
                        )

        # A literal shadow color is a light-theme assumption in disguise: it
        # stays a faint warm gray on a near-black page, where it reads as haze.
        literal_shadows = re.findall(r"box-shadow:\s*[^;]*rgba\(", css)
        if literal_shadows:
            failures.append(
                f"{len(literal_shadows)} shadow(s) hardcode a color instead of "
                "using a theme token"
            )

    for asset in PROFILE_ASSETS.values():
        source = profile / asset.source
        published = root / "assets" / "profile" / asset.filename
        if not source.is_file():
            failures.append(f"profile source missing: {asset.source}")
        elif not published.is_file():
            failures.append(f"published profile asset missing: {asset.filename}")
        elif source.read_bytes() != published.read_bytes():
            failures.append(f"published profile asset changed: {asset.filename}")

    # Profile links are cross-repository edges, so verify them with the site.
    profile_readme = profile / "README.md"
    profile_routes = []
    if not profile_readme.is_file():
        failures.append("public profile README is missing")
    else:
        profile_routes = [
            match.group("route")
            for match in PROFILE_SITE_LINK.finditer(
                profile_readme.read_text(encoding="utf-8")
            )
        ]
        if not profile_routes:
            failures.append("public profile contains no links to the portfolio site")
        for route in profile_routes:
            if not route_to_file(root, route).exists():
                failures.append(f"public profile points at a missing site route: {route}")

    # The retired project Page maps saved single-page fragments to current
    # study routes. It lives in the imaging checkout, but the account-site
    # build is the authority that can prove those destinations still exist.
    redirect_page = content / "site" / "index.html"
    if not redirect_page.is_file():
        failures.append("legacy portfolio redirect page is missing")
    else:
        redirect_routes = [
            match.group("route")
            for match in LEGACY_REDIRECT_ROUTE.finditer(
                redirect_page.read_text(encoding="utf-8")
            )
        ]
        if not redirect_routes:
            failures.append("legacy portfolio redirect has no deep-link mappings")
        for route in redirect_routes:
            if not route_to_file(root, route).exists():
                failures.append(f"legacy redirect points at a missing site route: {route}")

    study_names = {
        spec.study: name
        for name, spec in IMAGING.excerpts.items()
        if spec.study
    }
    study_pages = sorted((root / "imaging" / "studies").glob("*/index.html"))
    built_studies = {page.parent.name for page in study_pages}
    if built_studies != set(study_names):
        failures.append(
            "study excerpt coverage does not match the published studies: "
            f"pages={sorted(built_studies)}, mappings={sorted(study_names)}"
        )
    for study_page in study_pages:
        text = study_page.read_text(encoding="utf-8")
        count = len(EXCERPT.findall(text))
        if count != 1:
            failures.append(
                f"{study_page.relative_to(root)}: expected one contextual excerpt, "
                f"got {count}"
            )
        if text.count('class="study-resources"') != 1:
            failures.append(
                f"{study_page.relative_to(root)}: expected one early resource bar"
            )
        if text.count('id="implementation"') != 1:
            failures.append(
                f"{study_page.relative_to(root)}: implementation anchor missing"
            )
        sidebar_match = re.search(
            r'<aside class="sidebar">(?P<body>.*?)</aside>', text, re.S
        )
        if sidebar_match is None:
            failures.append(f"{study_page.relative_to(root)}: sidebar missing")
        else:
            sidebar = sidebar_match.group("body")
            if sidebar.count('<details class="side-details"') != 2:
                failures.append(
                    f"{study_page.relative_to(root)}: reports and methods must "
                    "use progressive disclosure"
                )
            visible = re.sub(
                r'<details class="side-details".*?</details>',
                "",
                sidebar,
                flags=re.S,
            )
            expected_visible = len(study_pages) + 4
            if visible.count("<a ") != expected_visible:
                failures.append(
                    f"{study_page.relative_to(root)}: expected {expected_visible} "
                    "visible primary navigation links"
                )

    landing = (root / "imaging" / "index.html").read_text(encoding="utf-8")
    landing_count = len(EXCERPT.findall(landing))
    if landing_count != len(IMAGING.landing_excerpts):
        failures.append(
            "imaging landing excerpt count does not match its selected showcase: "
            f"{landing_count} != {len(IMAGING.landing_excerpts)}"
        )
    if landing.count('<figure class="landing-figure">') != len(
        IMAGING.landing_figures
    ):
        failures.append("imaging landing figure count does not match its selection")
    if landing.count('<section class="tool-feature"') != 1:
        failures.append("imaging landing must contain one standalone-tool feature")
    if f'href="{COMPARATOR_ROUTE}"' not in landing:
        failures.append("imaging landing does not link the browser calculator")
    if "https://github.com/ferazambuja/cam16-hellwig-comparator" not in landing:
        failures.append("imaging landing does not link the standalone comparator")
    if '/imaging/studies/color-model-equation-audit/' not in landing:
        failures.append("comparator feature does not link the equation study")
    if "tradeoff rather than a universal win" not in landing:
        failures.append("comparator feature does not explain the paper's mixed result")
    if "These are model calculations, not measurements or observer validation" not in landing:
        failures.append("comparator example is missing its interpretation limit")
    if "Windows, macOS, and Linux" not in landing:
        failures.append("comparator feature omits the platforms with successful public runs")
    if f'href="{COMPARATOR_CI_URL}"' not in landing:
        failures.append("comparator feature does not link current main-branch CI")
    if f"{COMPARATOR_URL}/actions/runs/" in landing:
        failures.append("comparator feature links one frozen CI run")
    if not (comparator / "cam16_compare.py").is_file():
        failures.append("standalone comparator checkout is missing its implementation")
    browser_module = comparator / "cam16_compare.mjs"
    published_module = root / "assets" / "cam16_compare.mjs"
    if not browser_module.is_file():
        failures.append("standalone comparator checkout is missing its browser module")
    elif not published_module.is_file():
        failures.append("built site is missing the comparator browser module")
    elif browser_module.read_bytes() != published_module.read_bytes():
        failures.append("published comparator browser module differs from its source")
    elif re.search(
        rb"\b(?:fetch|XMLHttpRequest|WebSocket)\b", published_module.read_bytes()
    ):
        failures.append("published comparator browser module contains a network API")
    controller = root / "assets" / "cam16-calculator.mjs"
    if not controller.is_file():
        failures.append("built site is missing the calculator controller")
    else:
        controller_text = controller.read_text(encoding="utf-8")
        if 'const EXPECTED_API = "cam16-browser-api-v1"' not in controller_text:
            failures.append("calculator controller does not pin its browser API contract")
        if re.search(r"\b(?:fetch|XMLHttpRequest|WebSocket)\b", controller_text):
            failures.append("calculator controller contains a network API")
    if (content / "code" / "python" / "cam16_compare.py").exists():
        failures.append("standalone comparator was duplicated into the imaging repository")

    calculator = route_to_file(root, COMPARATOR_ROUTE)
    if not calculator.is_file():
        failures.append("browser calculator route is missing")
    else:
        calculator_text = calculator.read_text(encoding="utf-8")
        required_calculator_text = (
            "CAM16 and Hellwig–Fairchild calculator",
            "What the models report",
            "Why viewing conditions matter",
            "Why compare the formulations",
            "JavaScript is off",
            "not display RGB",
            "not a universal replacement",
        )
        for required_text in required_calculator_text:
            if required_text not in calculator_text:
                failures.append(
                    f"browser calculator is missing reader guidance: {required_text!r}"
                )
        if calculator_text.count('data-model="') != 12:
            failures.append("browser calculator does not provide all 12 result targets")
        if '<script type="module" src="/assets/cam16-calculator.mjs"></script>' not in calculator_text:
            failures.append("browser calculator does not load its local controller")
        if any(tag in calculator_text for tag in ("<canvas", 'type="color"')):
            failures.append("browser calculator implies an unsupported color preview")
        sitemap_text = (root / "sitemap.xml").read_text(encoding="utf-8")
        if f"{SITE_URL}{COMPARATOR_ROUTE}" not in sitemap_text:
            failures.append("browser calculator is missing from the sitemap")

    for related_route in (
        "/imaging/studies/color-model-equation-audit/",
        "/imaging/reports/cam16-equation-audit/",
    ):
        related = route_to_file(root, related_route)
        if related.is_file() and f'href="{COMPARATOR_ROUTE}"' not in related.read_text(
            encoding="utf-8"
        ):
            failures.append(f"{related_route}: does not link the calculator")

    retired_comparator = route_to_file(root, COMPARATOR_LEGACY_ROUTE)
    if not retired_comparator.is_file():
        failures.append("retired comparator route has no compatibility redirect")
    else:
        redirect_text = retired_comparator.read_text(encoding="utf-8")
        if f'location.replace("{COMPARATOR_ROUTE}")' not in redirect_text:
            failures.append("retired comparator route does not reach the calculator")
        if '<meta name="robots" content="noindex,follow">' not in redirect_text:
            failures.append("retired comparator route is indexable")
        if f"{SITE_URL}{COMPARATOR_LEGACY_ROUTE}" in (
            root / "sitemap.xml"
        ).read_text(encoding="utf-8"):
            failures.append("retired comparator route remains in the sitemap")

    expected_names = set(study_names.values())
    method_pages = sorted(
        page
        for page in (root / "imaging" / "methods").glob("*/index.html")
        if page.parent.name != "cam16-hellwig-comparator"
    )
    for method_page in method_pages:
        slug = method_page.parent.name
        name = IMAGING.method_excerpt.get(slug)
        if name is None:
            failures.append(
                f"{method_page.relative_to(root)}: method has no excerpt mapping"
            )
            continue
        spec = IMAGING.excerpts[name]
        text = method_page.read_text(encoding="utf-8")
        count = len(EXCERPT.findall(text))
        if spec.study:
            if count != 0:
                failures.append(
                    f"{method_page.relative_to(root)}: duplicates its study excerpt"
                )
            pointer = f'/imaging/studies/{spec.study}/#implementation'
            if f'href="{pointer}"' not in text:
                failures.append(
                    f"{method_page.relative_to(root)}: missing contextual study pointer"
                )
        else:
            expected_names.add(name)
            if count != 1:
                failures.append(
                    f"{method_page.relative_to(root)}: expected one standalone excerpt, "
                    f"got {count}"
                )

    if len(excerpt_ranges) != len(expected_names):
        failures.append(
            "source excerpts are not distinct: "
            f"{len(excerpt_ranges)} ranges for {len(expected_names)} implementations"
        )

    hdr_assets = hdr_manifest(Path.cwd() / "site")

    # Every HDR asset must match the recorded digest in source and output.
    if not hdr_assets:
        failures.append("HDR asset manifest is missing or empty")
    for name, digest in sorted(hdr_assets.items()):
        for base, where in ((Path.cwd() / "site" / "hdr", "source"),
                            (root / "assets" / "hdr", "published")):
            asset = base / name
            if not asset.is_file():
                failures.append(f"{where} HDR asset missing: {name}")
            elif hashlib.sha256(asset.read_bytes()).hexdigest() != digest:
                failures.append(f"{where} HDR asset does not match manifest: {name}")
    published = {
        path.name
        for path in (root / "assets" / "hdr").glob("*")
        if path.is_file()
    }
    if "manifest.sha256" in published:
        failures.append("HDR asset manifest must not be published")
    for extra in sorted(published - set(hdr_assets)):
        failures.append(f"published HDR asset is not in the manifest: {extra}")

    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        print(f"\n{len(failures)} problem(s)", file=sys.stderr)
        return 1

    print(
        f"site check: {len(pages)} pages, {internal} internal links resolved, "
        f"{external} external, {len(excerpt_ranges)} distinct excerpts "
        f"({checked_excerpts} rendered instances) byte-identical to source, "
        f"{len(profile_routes)} public-profile links resolved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
