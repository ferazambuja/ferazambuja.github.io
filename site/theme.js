/* Theme control.
 *
 * The stored choice is applied by a tiny inline script in <head>, before the
 * first paint, so a reader who chose dark never sees a white flash. This file
 * only builds the control and keeps it in sync, which is why it can defer.
 *
 * Absence of data-theme is meaningful: it means "follow the system", so the
 * button reads the effective theme rather than a variable of its own, and a
 * system change with no stored choice repaints the icon.
 */
(function () {
  var root = document.documentElement;
  var media = window.matchMedia("(prefers-color-scheme: dark)");

  var MOON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" ' +
    'aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
  var SUN =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="1.7" stroke-linecap="round" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="4"/><path d="M12 2.4v2.1M12 19.5v2.1M2.4 12h2.1' +
    'M19.5 12h2.1M5.2 5.2l1.5 1.5M17.3 17.3l1.5 1.5M18.8 5.2l-1.5 1.5' +
    'M6.7 17.3l-1.5 1.5"/></svg>';

  function effective() {
    return root.getAttribute("data-theme") || (media.matches ? "dark" : "light");
  }

  var button = document.createElement("button");
  button.type = "button";
  button.className = "theme-toggle";

  function paint() {
    var dark = effective() === "dark";
    var label = dark ? "Switch to the light theme" : "Switch to the dark theme";
    button.innerHTML = dark ? SUN : MOON;
    button.setAttribute("aria-label", label);
    button.setAttribute("title", label);
  }

  button.addEventListener("click", function () {
    var next = effective() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch (error) {
      /* Private browsing refuses storage; the choice still applies to this page. */
    }
    paint();
  });

  media.addEventListener("change", function () {
    if (!root.hasAttribute("data-theme")) {
      paint();
    }
  });

  paint();
  var bar = document.querySelector(".topbar-inner");
  if (bar) {
    bar.appendChild(button);
  }
})();
