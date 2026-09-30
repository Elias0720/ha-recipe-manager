const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { chromium } = require("playwright");

async function main() {
  const browser = await chromium.launch({
    executablePath: process.env.HA_RECIPE_BROWSER_PATH || undefined,
  });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const root = join(__dirname, "..");
    await page.route("http://recipes.test/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      const isPanel = path.endsWith("ha-recipe-manager-panel.js");
      const source = readFileSync(
        join(root, isPanel
          ? "custom_components/ha_recipe_manager/frontend/ha-recipe-manager-panel.js"
          : "tests/frontend_preview.html"),
        "utf8"
      );
      return route.fulfill({
        contentType: isPanel ? "text/javascript" : "text/html",
        body: isPanel ? source : source.replace(
          "const listeners = [];", "const listeners = window.recipeListeners = [];"
        ),
      });
    });
    await page.goto("http://recipes.test/");
    await page.waitForFunction(() => {
      const panel = document.querySelector("ha-recipe-manager-panel");
      return panel._loaded && window.recipeListeners.length === 1;
    });

    const checks = await page.evaluate(async () => {
      const panel = document.querySelector("ha-recipe-manager-panel");
      const query = (selector) => panel.shadowRoot.querySelector(selector);
      const check = (condition, message) => {
        if (!condition) throw new Error(message);
      };
      const input = (selector, value) => {
        const field = query(selector);
        field.value = value;
        field.dispatchEvent(new Event("input", { bubbles: true }));
        return field;
      };
      const refresh = () => window.recipeListeners[0].callback();
      const completed = [];

      query('[data-action="new"]').click();
      input("#edit-name", "Pasta mit frischen Kräutern");
      input("#edit-servings", "4");
      input("#edit-tags", "Vegetarisch, Schnell, ");
      input("#edit-source", "https://example.com/rezept");
      input('[name="quantity"]', "200");
      input('[name="unit"]', "g");
      input('[name="name"]', "Nudeln");
      input('[name="note"]', "frisch");
      input("#edit-instructions", "Wasser aufkochen.\nNudeln darin garen. ");

      const selectors = ["#edit-name", "#edit-servings", "#edit-tags", "#edit-source",
        '[name="quantity"]', '[name="unit"]', '[name="name"]', '[name="note"]',
        "#edit-instructions"];
      for (const selector of selectors) {
        const field = query(selector);
        const value = field.value;
        field.focus();
        if (field.selectionStart !== null) field.setSelectionRange(2, 5, "backward");
        const selection = [field.selectionStart, field.selectionEnd, field.selectionDirection];
        for (let update = 0; update < 3; update++) {
          panel.hass = { ...panel.hass, states: { update } };
          await refresh();
        }
        check(query(selector) === field, `${selector}: input was replaced`);
        check(field.value === value, `${selector}: input text changed`);
        check(panel.shadowRoot.activeElement === field, `${selector}: focus was lost`);
        check(field.selectionStart === selection[0] && field.selectionEnd === selection[1] &&
          field.selectionDirection === selection[2], `${selector}: selection changed`);
      }
      completed.push("All editor fields retain their nodes, exact text, focus and selection after HA and recipe events");

      const activeInstructions = query("#edit-instructions");
      await panel._addMissingToShoppingList();
      check(query("#edit-instructions") === activeInstructions &&
        panel.shadowRoot.activeElement === activeInstructions, "Shopping completion replaced or blurred the editor");
      completed.push("Shopping completion leaves an open editor intact");

      query('[data-action="add-row"]').click();
      check(query("#edit-name").value === "Pasta mit frischen Kräutern", "Adding an ingredient lost the recipe name");
      check(panel.shadowRoot.querySelectorAll("[data-ingredient-row]").length === 2, "Ingredient was not added");
      query('[data-action="remove-row"][data-index="1"]').click();
      check(query('[name="name"]').value === "Nudeln", "Removing an ingredient lost existing text");
      completed.push("Adding and removing ingredient rows preserves the form");

      input("#edit-source", "invalid-url");
      await panel._saveDraft();
      check(Boolean(query(".modal .notice.error")), "Invalid source did not show an error");
      check(query("#edit-name").value === "Pasta mit frischen Kräutern", "Validation lost the name");
      check(query("#edit-source").value === "invalid-url", "Validation lost the invalid input");

      input("#edit-source", "https://example.com/rezept");
      const connection = panel.hass.connection;
      const originalSend = connection.sendMessagePromise;
      connection.sendMessagePromise = async (message) => {
        if (message.type.endsWith("/save")) throw new Error("Test: connection interrupted");
        return originalSend(message);
      };
      input("#edit-name", "Neuer Name nach Validierung");
      await panel._saveDraft();
      check(query(".modal .notice.error").textContent.includes("connection interrupted"), "Save failure was not shown");
      check(query("#edit-name").value === "Neuer Name nach Validierung", "Save failure lost the latest text");
      completed.push("Validation and failed saves retain the latest draft");

      let saved;
      connection.sendMessagePromise = async (message) => {
        if (message.type.endsWith("/save")) {
          saved = { ...message.recipe, id: "saved-recipe" };
          return { recipe: saved };
        }
        return originalSend(message);
      };
      await panel._saveDraft();
      check(!query(".modal"), "Successful save did not close the editor");
      check(query(".main h2").textContent === saved.name, "Saved recipe was not selected");
      check(saved.ingredients[0].name === "Nudeln", "Saved recipe lost its ingredient");
      completed.push("A successful save submits the full draft and selects the recipe");
      connection.sendMessagePromise = originalSend;

      const search = input('[data-action="search"]', "Pasta");
      search.focus();
      search.setSelectionRange(1, 3);
      await refresh();
      check(query('[data-action="search"]') === search && panel.shadowRoot.activeElement === search,
        "Background refresh replaced or blurred the search input");
      check(search.selectionStart === 1 && search.selectionEnd === 3, "Background refresh changed the search selection");
      check(query(".recipe-list").textContent.includes("Pasta mit Tomatensauce"), "Recipe list did not refresh");
      check(!query(".recipe-list").textContent.includes("Gemüsecurry"), "Recipe refresh ignored the search filter");
      completed.push("Background refresh updates the filtered list while preserving the search cursor");
      return completed;
    });

    const shopping = page.locator('[data-action="add-missing"]');
    await page.mouse.move(0, 0);
    const normalColor = await shopping.evaluate((button) => getComputedStyle(button).backgroundColor);
    await shopping.hover();
    const hoverColors = await shopping.evaluate((button) => ({
      background: getComputedStyle(button).backgroundColor,
      border: getComputedStyle(button).borderTopColor,
      text: getComputedStyle(button).color,
    }));
    assert.notEqual(hoverColors.background, normalColor);
    assert.deepEqual(hoverColors, {
      background: "rgb(31, 90, 61)", border: "rgb(31, 90, 61)", text: "rgb(255, 255, 255)",
    });
    checks.push("Shopping button hovers dark green with a matching border and white text");
    await page.evaluate(() => {
      const panel = document.querySelector("ha-recipe-manager-panel");
      let unchecked;
      while ((unchecked = panel.shadowRoot.querySelector('[data-action="toggle-ingredient"]:not(:checked)'))) {
        unchecked.click();
      }
    });
    await page.mouse.move(0, 0);
    const disabledColor = await shopping.evaluate((button) => {
      if (!button.disabled) throw new Error("Shopping button did not disable when all ingredients were checked");
      return getComputedStyle(button).backgroundColor;
    });
    const shoppingBounds = await shopping.boundingBox();
    await page.mouse.move(shoppingBounds.x + shoppingBounds.width / 2, shoppingBounds.y + shoppingBounds.height / 2);
    assert.equal(await shopping.evaluate((button) => getComputedStyle(button).backgroundColor), disabledColor);
    checks.push("Disabled shopping button retains its background on hover");
    assert.deepEqual(errors, []);
    for (const check of checks) console.log(`PASS: ${check}`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
