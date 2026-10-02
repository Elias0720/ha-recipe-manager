const assert = require("node:assert/strict");
const { readFileSync, mkdirSync } = require("node:fs");
const { join } = require("node:path");
const { chromium } = require("playwright");

async function main() {
  const browser = await chromium.launch({ executablePath: process.env.HA_RECIPE_BROWSER_PATH || undefined });
  try {
    const root = join(__dirname, "..");
    const recipes = [
      { id: "pizza", name: "Pizza", duration_minutes: 35 },
      { id: "bolognese", name: "Bolognese", duration_minutes: 60 },
      { id: "lasagne", name: "Lasagne", duration_minutes: 90 },
      { id: "salat", name: "Salat <frisch>", duration_minutes: null },
    ].map(recipe => ({ ...recipe, servings: "2", tags: [], ingredients: [], instructions: "Kochen." }));
    const rankings = { taste: recipes.map(recipe => recipe.id), effort: ["salat", "pizza", "bolognese", "lasagne"] };
    let failNext = false;
    let releaseSave;
    let holdSave = false;
    const calls = [];
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, hasTouch: true });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.exposeFunction("previewSend", async message => {
      if (message.type.endsWith("/list")) return { recipes, rankings };
      if (message.type.endsWith("/save_ranking")) {
        calls.push(message);
        assert.equal(new Set(message.recipe_ids).size, recipes.length);
        if (failNext) { failNext = false; throw new Error("Test: save interrupted"); }
        if (holdSave) await new Promise(resolve => { releaseSave = resolve; });
        rankings[message.kind] = [...message.recipe_ids];
        return { rankings };
      }
      if (message.type.endsWith("/save")) {
        const recipe = { ...message.recipe, duration_minutes: Number(message.recipe.duration_minutes) || null };
        recipes[recipes.findIndex(existing => existing.id === recipe.id)] = recipe;
        return { recipe };
      }
      return {};
    });
    await page.route("http://rankings.test/**", route => {
      const isPanel = new URL(route.request().url()).pathname.endsWith("ha-recipe-manager-panel.js");
      let source = readFileSync(join(root, isPanel
        ? "custom_components/ha_recipe_manager/frontend/ha-recipe-manager-panel.js"
        : "tests/frontend_preview.html"), "utf8");
      if (!isPanel) source = source.replace("const listeners = [];", "const listeners = window.recipeListeners = [];")
        .replace(/const connection = \{[\s\S]*?\n      \};/, `const connection = {
          sendMessagePromise: message => window.previewSend(message),
          async subscribeEvents(callback, eventType) { listeners.push({ callback, eventType }); return () => {}; }
        };`);
      return route.fulfill({ contentType: isPanel ? "text/javascript" : "text/html", body: source });
    });
    const panel = () => page.locator("ha-recipe-manager-panel");
    const order = kind => page.locator(`.ranking-list[data-kind="${kind}"] .ranking-item`).evaluateAll(rows => rows.map(row => row.dataset.id));
    const saved = () => page.waitForFunction(() => !document.querySelector("ha-recipe-manager-panel")._rankingSaving);
    await page.goto("http://rankings.test/");
    await page.waitForFunction(() => document.querySelector("ha-recipe-manager-panel")._loaded);
    await page.locator('[data-action="edit"]').click();
    assert.equal(await page.locator("#edit-duration").inputValue(), "35");
    await page.locator("#edit-duration").fill("0");
    await page.locator('[data-action="save"]').click();
    assert.match(await page.locator(".modal .notice.error").textContent(), /ganzen Minuten/);
    await page.locator("#edit-duration").fill("40");
    await page.locator('[data-action="save"]').click();
    await page.waitForFunction(() => !document.querySelector("ha-recipe-manager-panel")._draft);
    assert.equal(recipes[0].duration_minutes, 40);
    assert.match(await page.locator(".main").textContent(), /ca\. 40 Min\./);
    await page.locator('[data-action="tab"][data-tab="rankings"]').click();
    assert.deepEqual(await order("taste"), ["pizza", "bolognese", "lasagne", "salat"]);
    assert.deepEqual(await order("effort"), ["salat", "pizza", "bolognese", "lasagne"]);
    const handle = page.locator('[data-action="drag-ranking"][data-kind="taste"][data-id="pizza"]');
    const from = await handle.boundingBox();
    const to = await page.locator('.ranking-item[data-kind="taste"][data-id="lasagne"]').boundingBox();
    await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
    await page.mouse.down();
    await page.evaluate(() => window.recipeListeners[0].callback());
    assert.equal(await panel().evaluate(element => Boolean(element._rankingDrag)), true);
    await page.mouse.move(to.x + to.width / 2, to.y + to.height - 10, { steps: 12 });
    await page.waitForFunction(() => document.querySelector("ha-recipe-manager-panel")._rankingDrag?.targetId === "lasagne");
    await page.mouse.up();
    await saved();
    assert.deepEqual(await order("taste"), ["bolognese", "lasagne", "pizza", "salat"]);
    assert.deepEqual(await order("effort"), ["salat", "pizza", "bolognese", "lasagne"]);
    assert.deepEqual(rankings.taste, ["bolognese", "lasagne", "pizza", "salat"]);
    console.log("PASS: Time estimates validate, save and display; dragging reorders only the chosen ranking and tolerates background refresh");

    await page.locator('[data-action="drag-ranking"][data-kind="effort"][data-id="lasagne"]').focus();
    await page.keyboard.press("Home");
    await saved();
    assert.deepEqual(await order("effort"), ["lasagne", "salat", "pizza", "bolognese"]);
    assert.equal(await panel().evaluate(element => element.shadowRoot.activeElement.dataset.id), "lasagne");
    await page.keyboard.press("ArrowDown");
    await saved();
    assert.deepEqual(await order("effort"), ["salat", "lasagne", "pizza", "bolognese"]);
    console.log("PASS: Keyboard reordering saves independently and preserves focus for repeated moves");

    const graph = await panel().evaluate(element => element._rankingChartData());
    assert.deepEqual(graph.points.map(point => [point.recipe.id, point.effort, point.taste]), [
      ["bolognese", 4, 1], ["lasagne", 2, 2], ["pizza", 3, 3], ["salat", 1, 4],
    ]);
    assert.ok(Math.abs(graph.trend.slope + 0.8) < 1e-12);
    assert.ok(Math.abs(graph.trend.intercept - 4.5) < 1e-12);
    assert.equal(await page.locator(".plot-trend").count(), 1);
    assert.equal(await page.locator(".chart-point").count(), 4);
    assert.match(await page.locator('.chart-point[data-id="salat"]').getAttribute("aria-label"), /Salat <frisch>/);
    assert.equal(await page.locator(".ranking-chart frisch").count(), 0);
    console.log("PASS: Recipe points map to both independent ranks; least-squares trend is numerically correct and names are escaped");

    failNext = true;
    const beforeFailure = [...rankings.taste];
    await page.locator('[data-action="move-ranking"][data-kind="taste"][data-id="pizza"][data-direction="-1"]').click();
    await saved();
    assert.deepEqual(rankings.taste, beforeFailure);
    assert.deepEqual(await order("taste"), ["bolognese", "pizza", "lasagne", "salat"]);
    assert.match(await page.locator(".notice.error").textContent(), /save interrupted/);
    await page.evaluate(() => window.recipeListeners[0].callback());
    assert.deepEqual(await order("taste"), ["bolognese", "pizza", "lasagne", "salat"]);
    await page.locator('[data-action="move-ranking"][data-kind="effort"][data-id="bolognese"][data-direction="-1"]').click();
    await saved();
    assert.match(await page.locator(".notice.error").textContent(), /Geschmack/);
    await page.locator('[data-action="move-ranking"][data-kind="effort"][data-id="bolognese"][data-direction="1"]').click();
    await saved();
    await page.locator('[data-action="retry-ranking"]').click();
    await saved();
    assert.deepEqual(rankings.taste, ["bolognese", "pizza", "lasagne", "salat"]);
    console.log("PASS: Failed saves retain the unsaved order through refresh and can be retried");

    holdSave = true;
    await page.locator('[data-action="move-ranking"][data-kind="taste"][data-id="pizza"][data-direction="-1"]').click();
    await page.waitForFunction(() => document.querySelector("ha-recipe-manager-panel")._rankingSaving);
    assert.equal(await page.locator('[data-action="drag-ranking"]:not(:disabled)').count(), 0);
    assert.equal(await page.locator('[data-action="move-ranking"]:not(:disabled)').count(), 0);
    assert.equal(typeof releaseSave, "function");
    holdSave = false;
    releaseSave();
    await saved();
    await page.reload();
    await page.waitForFunction(() => document.querySelector("ha-recipe-manager-panel")._loaded);
    await page.locator('[data-action="tab"][data-tab="rankings"]').click();
    assert.deepEqual(await order("taste"), rankings.taste);
    assert.deepEqual(await order("effort"), rankings.effort);
    console.log("PASS: Pending saves prevent overlapping moves; reloading retrieves both saved rankings");

    await page.locator('.chart-point[data-id="pizza"]').focus();
    await page.keyboard.press("Enter");
    assert.match(await page.locator(".main h2").textContent(), /Pizza/);
    await page.locator('[data-action="tab"][data-tab="rankings"]').click();
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const touchHandle = page.locator('[data-action="drag-ranking"][data-kind="effort"][data-id="salat"]');
    await touchHandle.scrollIntoViewIfNeeded();
    const touchFrom = await touchHandle.boundingBox();
    const touchTo = await page.locator('.ranking-item[data-kind="effort"][data-id="lasagne"]').boundingBox();
    const session = await page.context().newCDPSession(page);
    const touchX = touchFrom.x + touchFrom.width / 2;
    const startY = touchFrom.y + touchFrom.height / 2;
    const endY = touchTo.y + touchTo.height - 12;
    await session.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: touchX, y: startY }] });
    for (let step = 1; step <= 6; step++) {
      await session.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: touchX, y: startY + (endY - startY) * step / 6 }] });
    }
    await page.waitForFunction(() => document.querySelector("ha-recipe-manager-panel")._rankingDrag?.targetId === "lasagne");
    await session.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await saved();
    assert.deepEqual(await order("effort"), ["lasagne", "salat", "pizza", "bolognese"]);
    await session.detach();
    console.log("PASS: Real touch input can drag and save a ranking on a phone-sized viewport");
    const outputDir = process.env.HA_RECIPE_QA_DIR;
    if (outputDir) {
      mkdirSync(outputDir, { recursive: true });
      await page.screenshot({ path: join(outputDir, "rankings-mobile.png"), fullPage: true });
      await page.setViewportSize({ width: 1440, height: 1100 });
      await page.evaluate(() => {
        for (const [name, value] of Object.entries({
          "primary-color": "#009ac7", "primary-text-color": "#e8e8e8", "secondary-text-color": "#b0b0b0",
          "primary-background-color": "#111", "secondary-background-color": "#282828", "card-background-color": "#1c1c1c", "divider-color": "#454545",
        })) document.documentElement.style.setProperty(`--${name}`, value);
      });
      await page.screenshot({ path: join(outputDir, "rankings-dark.png"), fullPage: true });
    }
    const { points, trend } = await panel().evaluate(element => {
      element._recipes = [element._recipes[0]];
      element._syncRankings();
      element._render();
      return element._rankingChartData();
    });
    assert.equal(points.length, 1);
    assert.equal(trend, null);
    assert.equal(await page.locator(".plot-trend").count(), 0);
    await panel().evaluate(element => { element._recipes = []; element._syncRankings(); element._render(); });
    assert.equal(await page.locator(".ranking-chart").count(), 0);
    assert.deepEqual(errors, []);
    console.log("PASS: Chart points open recipes; mobile layout fits; zero and one recipe are handled without invalid trend lines");

    const cardPage = await browser.newPage();
    await cardPage.route("http://card.test/**", route => {
      const isScript = new URL(route.request().url()).pathname.endsWith("recipe-guide-card.js");
      const source = readFileSync(join(root, isScript
        ? "custom_components/ha_recipe_manager/frontend/recipe-guide-card.js" : "tests/card_preview.html"), "utf8");
      return route.fulfill({ contentType: isScript ? "text/javascript" : "text/html",
        body: isScript ? source : source.replace('servings: "4",', 'servings: "4", duration_minutes: 30,') });
    });
    await cardPage.goto("http://card.test/");
    await cardPage.waitForFunction(() => document.querySelector("ha-recipe-guide-card")._loaded);
    assert.match(await cardPage.locator(".card .muted").textContent(), /4 Portionen · ca\. 30 Min\. · Schnell, Vegetarisch/);
    assert.match(await cardPage.locator(".card").textContent(), /ca\. 2[.\s]350 kcal gesamt/);
    assert.match(await cardPage.locator('[data-nutrient="total_protein_g"]').textContent(), /Protein.*80,5 g/);
    assert.match(await cardPage.locator('[data-nutrient="total_fat_g"]').textContent(), /Fett.*20,2 g/);
    assert.match(await cardPage.locator('[data-nutrient="total_sugar_g"]').textContent(), /Zucker.*32,6 g/);
    await cardPage.evaluate(() => {
      const card = document.querySelector("ha-recipe-guide-card");
      card._selectedRecipe().calories_stale = true;
      card._render();
    });
    assert.match(await cardPage.locator(".card").textContent(), /Nährwerte veraltet/);
    await cardPage.setViewportSize({ width: 390, height: 844 });
    assert.equal(await cardPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await cardPage.close();
    console.log("PASS: Dashboard card shows time, whole-recipe calories and stale estimates, and fits on mobile");
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
