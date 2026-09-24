async (page) => {
  // Run with playwright-cli run-code against an already opened local preview.
  const origin = await page.evaluate(() => location.origin);
  const routes = ["", "pattern-behavior/", "prediction/", "renderer/", "icc/", "measurements/"];
  const results = [];
  for (const route of routes) {
    await page.goto(`${origin}/reflective-color-display/${route}`);
    const aligned = await page.evaluate(() => {
      const main = document.querySelector("main"), nav = document.querySelector(".case-nav");
      const contentLeft = main.getBoundingClientRect().left + parseFloat(getComputedStyle(main).paddingLeft);
      return Math.abs(nav.getBoundingClientRect().left - contentLeft) < 1;
    });
    if (!aligned) throw new Error(`${route || "overview"}: navigation and content margins differ`);
    await page.keyboard.press("Tab");
    const skip = await page.evaluate(() => {
      const el = document.activeElement, box = el.getBoundingClientRect();
      return el.matches("a.skip-link[href='#main-content']") && box.top >= 0 && box.bottom <= innerHeight;
    });
    if (!skip) throw new Error(`${route || "overview"}: first Tab did not reach a visible skip link`);
    await page.keyboard.press("Enter");
    const main = await page.evaluate(() => document.activeElement.matches("main#main-content"));
    if (!main) throw new Error(`${route || "overview"}: skip activation did not focus main content`);
    await page.keyboard.press("Tab");
    const next = await page.evaluate(() => {
      const el = document.activeElement;
      return {insideMain: !!el.closest("main#main-content"), insideNav: !!el.closest("nav"), label: el.textContent.trim()};
    });
    if (!next.insideMain || next.insideNav) throw new Error(`${route || "overview"}: next Tab returned to navigation`);
    results.push({route: route || "overview", skip: true, main: true, aligned, next: next.label.slice(0, 80)});
  }
  return results;
}
