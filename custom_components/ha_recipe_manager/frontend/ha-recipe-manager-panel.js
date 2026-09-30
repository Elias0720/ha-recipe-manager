const DOMAIN = "ha_recipe_manager";

const emptyIngredient = () => ({
  id: "",
  quantity: "",
  unit: "",
  name: "",
  note: "",
});

const emptyRecipe = () => ({
  id: "",
  name: "",
  servings: "",
  source_url: "",
  tags: [],
  ingredients: [emptyIngredient()],
  instructions: "",
});

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const cloneRecipe = (recipe) => JSON.parse(JSON.stringify(recipe || emptyRecipe()));

const ingredientLabel = (ingredient) => {
  const prefix = [ingredient.quantity, ingredient.unit].filter(Boolean).join(" ");
  const label = `${prefix} ${ingredient.name || ""}`.trim();
  return ingredient.note ? `${label} (${ingredient.note})` : label;
};

const safeExternalUrl = (value) => {
  try {
    const url = new URL(String(value || ""));
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch (_err) {
    return "";
  }
};

class HaRecipeManagerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = undefined;
    this._loaded = false;
    this._loading = false;
    this._recipes = [];
    this._selectedId = undefined;
    this._checked = new Set();
    this._view = "prep";
    this._query = "";
    this._message = "";
    this._error = "";
    this._draft = undefined;
    this._editorError = "";
    this._unsubscribeRecipes = undefined;
    this._subscriptionPending = false;

    this.shadowRoot.addEventListener("click", (event) => this._handleClick(event));
    this.shadowRoot.addEventListener("input", (event) => this._handleInput(event));
    this.shadowRoot.addEventListener("change", (event) => this._handleChange(event));
  }

  set hass(hass) {
    this._hass = hass;
    this._subscribeRecipeUpdates();
    if (!this._loaded && hass?.connection) {
      this._loadRecipes();
    }
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this._subscribeRecipeUpdates();
    this._render();
  }

  disconnectedCallback() {
    this._unsubscribeRecipes?.();
    this._unsubscribeRecipes = undefined;
  }

  async _api(command, payload = {}) {
    return this._hass.connection.sendMessagePromise({
      type: `${DOMAIN}/${command}`,
      ...payload,
    });
  }

  async _loadRecipes() {
    if (!this._hass || this._loading) {
      return;
    }
    this._loading = true;
    this._error = "";
    this._render({ updateEditor: false });

    try {
      const response = await this._api("list");
      this._recipes = response.recipes || [];
      this._loaded = true;
      if (!this._selectedRecipe() && this._recipes.length > 0) {
        this._selectRecipe(this._recipes[0].id);
      }
    } catch (err) {
      this._error = err?.message || "Rezepte konnten nicht geladen werden.";
    } finally {
      this._loading = false;
      this._render({ updateEditor: false });
    }
  }

  async _subscribeRecipeUpdates() {
    if (
      !this.isConnected ||
      !this._hass?.connection ||
      this._unsubscribeRecipes ||
      this._subscriptionPending
    ) {
      return;
    }

    this._subscriptionPending = true;
    try {
      const unsubscribe = await this._hass.connection.subscribeEvents(
        () => this._loadRecipes(),
        `${DOMAIN}_recipes_updated`
      );
      if (this.isConnected) {
        this._unsubscribeRecipes = unsubscribe;
      } else {
        unsubscribe();
      }
    } catch (_err) {
      // Initial loading still works when event subscriptions are unavailable.
    } finally {
      this._subscriptionPending = false;
    }
  }

  _selectedRecipe() {
    return this._recipes.find((recipe) => recipe.id === this._selectedId);
  }

  _selectRecipe(recipeId) {
    this._selectedId = recipeId;
    this._checked = new Set();
    this._message = "";
    this._error = "";
  }

  _filteredRecipes() {
    const query = this._query.trim().toLowerCase();
    if (!query) {
      return this._recipes;
    }
    return this._recipes.filter((recipe) => {
      const haystack = [recipe.name, recipe.tags?.join(" "), recipe.instructions]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }

  _renderRecipeListContents() {
    const filteredRecipes = this._filteredRecipes();
    if (!filteredRecipes.length) {
      return `<div class="empty">Noch kein passendes Rezept.</div>`;
    }

    return filteredRecipes
      .map(
        (item) => `
          <button class="recipe-button ${
            item.id === this._selectedId ? "active" : ""
          }" data-action="select" data-id="${escapeHtml(item.id)}" aria-pressed="${item.id === this._selectedId}">
            <ha-icon icon="mdi:silverware-fork-knife"></ha-icon>
            <span class="recipe-title">
              <strong>${escapeHtml(item.name)}</strong><br>
              <span class="muted">${item.ingredients.length} Zutaten</span>
            </span>
          </button>`
      )
      .join("");
  }

  async _saveDraft() {
    const recipe = this._collectDraftFromForm();
    if (!recipe) {
      return;
    }
    this._draft = recipe;
    if (!recipe.name) {
      this._editorError = "Bitte gib dem Rezept einen Namen.";
      this._render();
      return;
    }
    if (recipe.source_url && !safeExternalUrl(recipe.source_url)) {
      this._editorError = "Die Quelle muss eine vollständige HTTP- oder HTTPS-Adresse sein.";
      this._render();
      return;
    }

    try {
      const response = await this._api("save", { recipe });
      const saved = response.recipe;
      this._recipes = [...this._recipes.filter((item) => item.id !== saved.id), saved].sort(
        (a, b) => a.name.localeCompare(b.name)
      );
      this._selectedId = saved.id;
      this._draft = undefined;
      this._editorError = "";
      this._message = "Rezept gespeichert.";
      this._checked = new Set();
    } catch (err) {
      this._editorError = err?.message || "Rezept konnte nicht gespeichert werden.";
    }
    this._render();
  }

  async _deleteSelectedRecipe() {
    const recipe = this._selectedRecipe();
    if (!recipe || !confirm(`Rezept "${recipe.name}" wirklich löschen?`)) {
      return;
    }

    try {
      await this._api("delete", { recipe_id: recipe.id });
      this._recipes = this._recipes.filter((item) => item.id !== recipe.id);
      this._selectedId = this._recipes[0]?.id;
      this._checked = new Set();
      this._message = "Rezept gelöscht.";
    } catch (err) {
      this._error = err?.message || "Rezept konnte nicht gelöscht werden.";
    }
    this._render({ updateEditor: false });
  }

  async _addMissingToShoppingList() {
    const recipe = this._selectedRecipe();
    if (!recipe) {
      return;
    }

    this._message = "";
    this._error = "";
    this._render({ updateEditor: false });

    try {
      const response = await this._api("add_to_shopping_list", {
        recipe_id: recipe.id,
        checked_ingredient_ids: [...this._checked],
      });
      this._message =
        response.count === 0
          ? "Alle Zutaten waren abgehakt."
          : `Einkaufsliste aktualisiert: ${response.count} Zutaten übernommen.`;
    } catch (err) {
      this._error = err?.message || "Einkaufsliste konnte nicht aktualisiert werden.";
    }
    this._render({ updateEditor: false });
  }

  async _copySelectedRecipeId() {
    const recipe = this._selectedRecipe();
    if (!recipe) {
      return;
    }

    this._error = "";
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API unavailable");
      }
      await navigator.clipboard.writeText(recipe.id);
      this._message = "Rezept-ID kopiert.";
      this._error = "";
    } catch (_err) {
      this._message = `Rezept-ID: ${recipe.id}`;
    }
    this._render({ updateEditor: false });
  }

  _collectDraftFromForm() {
    if (!this._draft) {
      return undefined;
    }

    const value = (selector) => this.shadowRoot.querySelector(selector)?.value?.trim() || "";
    const ingredients = [...this.shadowRoot.querySelectorAll("[data-ingredient-row]")].map(
      (row) => ({
        id: row.dataset.id || "",
        quantity: row.querySelector('[name="quantity"]')?.value.trim() || "",
        unit: row.querySelector('[name="unit"]')?.value.trim() || "",
        name: row.querySelector('[name="name"]')?.value.trim() || "",
        note: row.querySelector('[name="note"]')?.value.trim() || "",
      })
    );

    return {
      ...this._draft,
      name: value("#edit-name"),
      servings: value("#edit-servings"),
      source_url: value("#edit-source"),
      tags: value("#edit-tags")
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      ingredients,
      instructions: this.shadowRoot.querySelector("#edit-instructions")?.value.trim() || "",
    };
  }

  _syncDraftFromForm() {
    const draft = this._collectDraftFromForm();
    if (draft) {
      this._draft = draft;
    }
  }

  _handleClick(event) {
    const target = event.target.closest("[data-action]");
    if (!target) {
      return;
    }

    const action = target.dataset.action;

    if (action === "select") {
      this._selectRecipe(target.dataset.id);
      this._render();
      return;
    }

    if (action === "new") {
      this._draft = emptyRecipe();
      this._editorError = "";
      this._render();
      return;
    }

    if (action === "edit") {
      this._draft = cloneRecipe(this._selectedRecipe());
      this._editorError = "";
      this._render();
      return;
    }

    if (action === "close-editor") {
      this._draft = undefined;
      this._editorError = "";
      this._render();
      return;
    }

    if (action === "save") {
      this._saveDraft();
      return;
    }

    if (action === "delete") {
      this._deleteSelectedRecipe();
      return;
    }

    if (action === "copy-id") {
      this._copySelectedRecipeId();
      return;
    }

    if (action === "add-row") {
      this._syncDraftFromForm();
      this._draft.ingredients.push(emptyIngredient());
      this._render();
      return;
    }

    if (action === "remove-row") {
      this._syncDraftFromForm();
      this._draft.ingredients.splice(Number(target.dataset.index), 1);
      if (this._draft.ingredients.length === 0) {
        this._draft.ingredients.push(emptyIngredient());
      }
      this._render();
      return;
    }

    if (action === "add-missing") {
      this._addMissingToShoppingList();
      return;
    }

    if (action === "view") {
      this._view = target.dataset.view;
      this._render();
      return;
    }

  }

  _handleInput(event) {
    if (event.target?.dataset?.action === "search") {
      this._query = event.target.value;
      const recipeList = this.shadowRoot.querySelector(".recipe-list");
      if (recipeList) {
        recipeList.innerHTML = this._renderRecipeListContents();
      }
    }
  }

  _handleChange(event) {
    const target = event.target;
    if (target?.dataset?.action !== "toggle-ingredient") {
      return;
    }

    if (target.checked) {
      this._checked.add(target.dataset.id);
    } else {
      this._checked.delete(target.dataset.id);
    }
    this._render();
  }

  _render({ updateEditor = true } = {}) {
    const recipe = this._selectedRecipe();

    const content = `
      <style>
        :host {
          display: block;
          min-height: 100vh;
          color: var(--primary-text-color, #1f2933);
          background: var(--primary-background-color, #f7f8fa);
          font-family: var(--paper-font-body1_-_font-family, Roboto, Arial, sans-serif);
          color-scheme: var(--ha-color-scheme, light dark);
          --recipe-selection-background: color-mix(in srgb, var(--primary-color, #2f7d5b) 18%, var(--card-background-color, #fff));
        }

        * {
          box-sizing: border-box;
        }

        button,
        input,
        textarea {
          font: inherit;
        }

        button {
          border: 1px solid var(--divider-color, #d9dee4);
          border-radius: 8px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #1f2933);
          min-height: 40px;
          padding: 0 12px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          cursor: pointer;
          white-space: nowrap;
        }

        button:hover:not(:disabled) {
          background: var(--secondary-background-color, #eef2f5);
        }

        button:focus-visible,
        input:focus-visible,
        textarea:focus-visible,
        a:focus-visible {
          outline: 2px solid var(--primary-color, #2f7d5b);
          outline-offset: 3px;
        }

        ::selection {
          background: #1f5a3d;
          color: #fff;
        }

        a {
          color: var(--link-text-color, var(--primary-color, #2f7d5b));
        }

        button:disabled {
          cursor: default;
          opacity: 0.55;
        }

        .primary {
          background: #2f7d5b;
          border-color: #2f7d5b;
          color: #fff;
        }

        .primary:hover:not(:disabled) {
          background: #1f5a3d;
          border-color: #1f5a3d;
          color: #fff;
        }

        .danger {
          color: var(--error-color, #b3261e);
        }

        .shell {
          display: grid;
          grid-template-columns: minmax(260px, 330px) minmax(0, 1fr);
          min-height: 100vh;
        }

        .sidebar {
          border-right: 1px solid var(--divider-color, #d9dee4);
          background: var(--card-background-color, #fff);
          padding: 18px;
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .sidebar-header,
        .title-row,
        .toolbar,
        .status-row,
        .ingredient-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .sidebar-header,
        .title-row,
        .status-row {
          justify-content: space-between;
        }

        h1,
        h2,
        h3,
        p {
          margin: 0;
        }

        h1 {
          font-size: 22px;
          font-weight: 600;
          letter-spacing: 0;
        }

        h2 {
          font-size: 28px;
          line-height: 1.2;
          letter-spacing: 0;
        }

        h3 {
          font-size: 16px;
          font-weight: 600;
        }

        .search,
        .field input,
        .field textarea,
        .ingredient-row input {
          width: 100%;
          border: 1px solid var(--divider-color, #d9dee4);
          border-radius: 8px;
          padding: 10px 12px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #1f2933);
          caret-color: var(--primary-text-color, #1f2933);
        }

        input::placeholder,
        textarea::placeholder {
          color: var(--secondary-text-color, #64707d);
          opacity: 1;
        }

        .recipe-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          overflow: auto;
        }

        .recipe-button {
          width: 100%;
          min-height: 56px;
          justify-content: flex-start;
          text-align: left;
        }

        .recipe-button.active {
          border-color: var(--primary-color, #2f7d5b);
          background: var(--recipe-selection-background);
          color: var(--primary-text-color, #1f2933);
          box-shadow: inset 3px 0 0 var(--primary-color, #2f7d5b);
        }

        .recipe-title {
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .muted {
          color: var(--secondary-text-color, #64707d);
          font-size: 13px;
        }

        .recipe-button.active .muted {
          color: var(--primary-text-color, #1f2933);
        }

        .main {
          padding: 24px;
          min-width: 0;
        }

        .panel {
          max-width: 980px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: 18px;
        }

        .toolbar {
          flex-wrap: wrap;
        }

        .segment button {
          border-radius: 0;
        }

        .segment button:first-child {
          border-radius: 8px 0 0 8px;
        }

        .segment button:last-child {
          border-radius: 0 8px 8px 0;
        }

        .segment .active {
          border-color: var(--primary-color, #2f7d5b);
          background: var(--recipe-selection-background);
          color: var(--primary-text-color, #1f2933);
          box-shadow: inset 0 -3px 0 var(--primary-color, #2f7d5b);
        }

        .recipe-button.active:hover,
        .segment .active:hover {
          background: color-mix(in srgb, var(--primary-color, #2f7d5b) 24%, var(--card-background-color, #fff));
        }

        .stats {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 10px;
        }

        .stat,
        .notice,
        .empty,
        .section {
          background: var(--card-background-color, #fff);
          border: 1px solid var(--divider-color, #d9dee4);
          border-radius: 8px;
        }

        .stat {
          padding: 12px;
        }

        .stat strong {
          display: block;
          font-size: 22px;
        }

        .section {
          padding: 18px;
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .ingredient-list {
          display: grid;
          gap: 8px;
        }

        .ingredient {
          display: grid;
          grid-template-columns: 24px minmax(0, 1fr);
          gap: 10px;
          align-items: center;
          min-height: 44px;
          padding: 8px;
          border: 1px solid var(--divider-color, #d9dee4);
          border-radius: 8px;
        }

        .ingredient input {
          width: 18px;
          height: 18px;
          accent-color: #2f7d5b;
        }

        .ingredient.checked {
          background: var(--recipe-selection-background);
          border-color: var(--primary-color, #2f7d5b);
        }

        .ingredient.checked span {
          color: var(--primary-text-color, #1f2933);
          text-decoration: line-through;
        }

        .instructions {
          white-space: pre-wrap;
          line-height: 1.55;
        }

        .notice,
        .empty {
          padding: 14px;
        }

        .notice.error {
          border-color: var(--error-color, #b3261e);
          color: var(--error-color, #b3261e);
        }

        .modal-backdrop {
          position: fixed;
          inset: 0;
          z-index: 10;
          background: rgba(0, 0, 0, 0.34);
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 18px;
        }

        .modal {
          width: min(900px, 100%);
          max-height: min(900px, calc(100vh - 36px));
          overflow: auto;
          background: var(--card-background-color, #fff);
          border-radius: 8px;
          box-shadow: var(--ha-card-box-shadow, 0 10px 30px rgba(0, 0, 0, 0.28));
          padding: 20px;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .form-grid {
          display: grid;
          grid-template-columns: 1fr 160px;
          gap: 12px;
        }

        .field {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .field label {
          font-size: 13px;
          color: var(--secondary-text-color, #64707d);
        }

        textarea {
          min-height: 170px;
          resize: vertical;
        }

        .ingredient-editor {
          display: grid;
          gap: 8px;
        }

        .ingredient-row {
          display: grid;
          grid-template-columns: 90px 90px minmax(150px, 1fr) minmax(120px, 0.7fr) 44px;
          gap: 8px;
          align-items: center;
        }

        .ingredient-row input {
          width: 100%;
          border: 1px solid var(--divider-color, #d9dee4);
          border-radius: 8px;
          min-height: 40px;
          padding: 8px;
        }

        @media (max-width: 820px) {
          .shell {
            grid-template-columns: 1fr;
          }

          .sidebar {
            border-right: 0;
            border-bottom: 1px solid var(--divider-color, #d9dee4);
            max-height: 48vh;
          }

          .main {
            padding: 16px;
          }

          .title-row,
          .status-row {
            align-items: flex-start;
            flex-direction: column;
          }

          .stats,
          .form-grid,
          .ingredient-row {
            grid-template-columns: 1fr;
          }

          .ingredient-row button {
            width: 44px;
          }
        }
      </style>
      <div class="shell">
        <aside class="sidebar">
          <div class="sidebar-header">
            <h1>Rezepte</h1>
            <button class="primary" data-action="new" title="Neues Rezept">
              <ha-icon icon="mdi:plus"></ha-icon>
            </button>
          </div>
          <input class="search" data-action="search" value="${escapeHtml(
            this._query
          )}" placeholder="Suchen">
          <div class="recipe-list">
            ${this._renderRecipeListContents()}
          </div>
        </aside>
        <main class="main">
          ${this._loading ? `<div class="empty">Rezepte werden geladen ...</div>` : ""}
          ${this._error ? `<div class="notice error">${escapeHtml(this._error)}</div>` : ""}
          ${this._message ? `<div class="notice">${escapeHtml(this._message)}</div>` : ""}
          ${recipe ? this._renderRecipe(recipe) : this._renderEmptyState()}
        </main>
      </div>
      ${this._draft ? this._renderEditor() : ""}
    `;

    if (!updateEditor && this.shadowRoot.querySelector(".shell")) {
      // Keep editor and search inputs mounted during background recipe updates.
      const template = document.createElement("template");
      template.innerHTML = content;
      for (const selector of [".main", ".recipe-list"]) {
        this.shadowRoot.querySelector(selector).replaceWith(template.content.querySelector(selector));
      }
    } else {
      this.shadowRoot.innerHTML = content;
    }
  }

  _renderEmptyState() {
    return `
      <div class="panel">
        <div class="empty">
          <h2>Keine Rezepte vorhanden</h2>
          <p class="muted">Lege dein erstes Rezept an, dann kannst du Zutaten abhaken und die fehlenden Einträge auf die Einkaufsliste setzen.</p>
        </div>
      </div>
    `;
  }

  _renderRecipe(recipe) {
    const checkedCount = recipe.ingredients.filter((ingredient) =>
      this._checked.has(ingredient.id)
    ).length;
    const missingCount = Math.max(recipe.ingredients.length - checkedCount, 0);

    return `
      <div class="panel">
        <div class="title-row">
          <div>
            <h2>${escapeHtml(recipe.name)}</h2>
            <p class="muted">
              ${recipe.servings ? `${escapeHtml(recipe.servings)} Portionen · ` : ""}
              ${recipe.tags?.map((tag) => escapeHtml(tag)).join(", ") || "Ohne Kategorie"}
            </p>
          </div>
          <div class="toolbar">
            <button data-action="edit" title="Rezept bearbeiten"><ha-icon icon="mdi:pencil"></ha-icon>Bearbeiten</button>
            <button data-action="copy-id" title="Rezept-ID kopieren" aria-label="Rezept-ID kopieren"><ha-icon icon="mdi:identifier"></ha-icon></button>
            <button class="danger" data-action="delete" title="Rezept löschen" aria-label="Rezept löschen"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>
          </div>
        </div>

        <div class="toolbar segment">
          <button class="${this._view === "prep" ? "active" : ""}" data-action="view" data-view="prep" aria-pressed="${this._view === "prep"}">
            <ha-icon icon="mdi:checkbox-marked-outline"></ha-icon>Zutaten
          </button>
          <button class="${this._view === "guide" ? "active" : ""}" data-action="view" data-view="guide" aria-pressed="${this._view === "guide"}">
            <ha-icon icon="mdi:book-open-page-variant-outline"></ha-icon>Anleitung
          </button>
        </div>

        <div class="stats">
          <div class="stat"><strong>${recipe.ingredients.length}</strong><span class="muted">Zutaten</span></div>
          <div class="stat"><strong>${checkedCount}</strong><span class="muted">vorhanden</span></div>
          <div class="stat"><strong>${missingCount}</strong><span class="muted">fehlen</span></div>
        </div>

        ${this._view === "prep" ? this._renderIngredients(recipe, missingCount) : this._renderGuide(recipe)}
      </div>
    `;
  }

  _renderIngredients(recipe, missingCount) {
    return `
      <div class="section">
        <div class="status-row">
          <h3>Zutatencheck</h3>
          <button class="primary" data-action="add-missing" ${missingCount === 0 ? "disabled" : ""}>
            <ha-icon icon="mdi:cart-plus"></ha-icon>Fehlende auf Einkaufsliste
          </button>
        </div>
        <div class="ingredient-list">
          ${
            recipe.ingredients.length
              ? recipe.ingredients
                  .map(
                    (ingredient) => `
                      <label class="ingredient ${
                        this._checked.has(ingredient.id) ? "checked" : ""
                      }">
                        <input type="checkbox" data-action="toggle-ingredient" data-id="${escapeHtml(
                          ingredient.id
                        )}" ${this._checked.has(ingredient.id) ? "checked" : ""}>
                        <span>${escapeHtml(ingredientLabel(ingredient))}</span>
                      </label>`
                  )
                  .join("")
              : `<p class="muted">Dieses Rezept hat noch keine Zutaten.</p>`
          }
        </div>
      </div>
    `;
  }

  _renderGuide(recipe) {
    const sourceUrl = safeExternalUrl(recipe.source_url);
    return `
      <div class="section">
        <div class="status-row">
          <h3>Anleitung</h3>
          ${
            sourceUrl
              ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noreferrer">Quelle</a>`
              : ""
          }
        </div>
        <div class="instructions">${
          recipe.instructions
            ? escapeHtml(recipe.instructions)
            : "Noch keine Anleitung eingetragen."
        }</div>
      </div>
    `;
  }

  _renderEditor() {
    const recipe = this._draft;
    return `
      <div class="modal-backdrop" role="dialog" aria-modal="true">
        <div class="modal">
          <div class="title-row">
            <h2>${recipe.id ? "Rezept bearbeiten" : "Neues Rezept"}</h2>
            <button data-action="close-editor" title="Schließen" aria-label="Editor schließen"><ha-icon icon="mdi:close"></ha-icon></button>
          </div>
          ${this._editorError ? `<div class="notice error">${escapeHtml(this._editorError)}</div>` : ""}
          <div class="form-grid">
            <div class="field">
              <label for="edit-name">Name</label>
              <input id="edit-name" value="${escapeHtml(recipe.name)}" autocomplete="off">
            </div>
            <div class="field">
              <label for="edit-servings">Portionen</label>
              <input id="edit-servings" value="${escapeHtml(recipe.servings)}" autocomplete="off">
            </div>
          </div>
          <div class="form-grid">
            <div class="field">
              <label for="edit-tags">Kategorien</label>
              <input id="edit-tags" value="${escapeHtml((recipe.tags || []).join(", "))}" autocomplete="off">
            </div>
            <div class="field">
              <label for="edit-source">Quelle</label>
              <input id="edit-source" type="url" inputmode="url" value="${escapeHtml(
                recipe.source_url
              )}" autocomplete="off" placeholder="https://…">
            </div>
          </div>
          <div class="section">
            <div class="status-row">
              <h3>Zutaten</h3>
              <button data-action="add-row"><ha-icon icon="mdi:plus"></ha-icon>Zutat</button>
            </div>
            <div class="ingredient-editor">
              ${(recipe.ingredients || [emptyIngredient()])
                .map(
                  (ingredient, index) => `
                    <div class="ingredient-row" data-ingredient-row data-id="${escapeHtml(
                      ingredient.id
                    )}">
                      <input name="quantity" value="${escapeHtml(
                        ingredient.quantity
                      )}" placeholder="Menge">
                      <input name="unit" value="${escapeHtml(ingredient.unit)}" placeholder="Einheit">
                      <input name="name" value="${escapeHtml(ingredient.name)}" placeholder="Zutat">
                      <input name="note" value="${escapeHtml(ingredient.note)}" placeholder="Notiz">
                      <button class="danger" data-action="remove-row" data-index="${index}" title="Zutat entfernen">
                        <ha-icon icon="mdi:minus"></ha-icon>
                      </button>
                    </div>`
                )
                .join("")}
            </div>
          </div>
          <div class="field">
            <label for="edit-instructions">Anleitung</label>
            <textarea id="edit-instructions">${escapeHtml(recipe.instructions)}</textarea>
          </div>
          <div class="toolbar">
            <button class="primary" data-action="save"><ha-icon icon="mdi:content-save-outline"></ha-icon>Speichern</button>
            <button data-action="close-editor">Abbrechen</button>
          </div>
        </div>
      </div>
    `;
  }
}

if (!customElements.get("ha-recipe-manager-panel")) {
  customElements.define("ha-recipe-manager-panel", HaRecipeManagerPanel);
}
