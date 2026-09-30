const RECIPE_CARD_DOMAIN = "ha_recipe_manager";

const recipeCardEscape = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const recipeCardIngredientLabel = (ingredient) => {
  const prefix = [ingredient.quantity, ingredient.unit].filter(Boolean).join(" ");
  const label = `${prefix} ${ingredient.name || ""}`.trim();
  return ingredient.note ? `${label} (${ingredient.note})` : label;
};

class HaRecipeGuideCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = undefined;
    this._recipes = [];
    this._selectedId = undefined;
    this._loaded = false;
    this._unsubscribeRecipes = undefined;
    this._subscriptionPending = false;

    this.shadowRoot.addEventListener("change", (event) => {
      if (event.target?.dataset?.action === "select-recipe") {
        this._selectedId = event.target.value;
        this._render();
      }
    });
  }

  setConfig(config) {
    this._config = config || {};
    this._selectedId = this._config.recipe_id;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._subscribeRecipeUpdates();
    if (!this._loaded && hass?.connection) {
      this._loadRecipes();
    } else {
      this._render();
    }
  }

  getCardSize() {
    return 5;
  }

  connectedCallback() {
    this._subscribeRecipeUpdates();
  }

  disconnectedCallback() {
    this._unsubscribeRecipes?.();
    this._unsubscribeRecipes = undefined;
  }

  async _loadRecipes() {
    try {
      const response = await this._hass.connection.sendMessagePromise({
        type: `${RECIPE_CARD_DOMAIN}/list`,
      });
      this._recipes = response.recipes || [];
      this._loaded = true;
      if (!this._selectedRecipe() && !this._config.recipe_id && this._recipes.length) {
        this._selectedId = this._recipes[0].id;
      }
    } catch (_err) {
      this._recipes = [];
    }
    this._render();
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
        `${RECIPE_CARD_DOMAIN}_recipes_updated`
      );
      if (this.isConnected) {
        this._unsubscribeRecipes = unsubscribe;
      } else {
        unsubscribe();
      }
    } catch (_err) {
      // The card remains usable even if event subscriptions are unavailable.
    } finally {
      this._subscriptionPending = false;
    }
  }

  _selectedRecipe() {
    return this._recipes.find((recipe) => recipe.id === this._selectedId);
  }

  _render() {
    const recipe = this._selectedRecipe();
    const title = this._config.title || recipe?.name || "Rezept";

    this.shadowRoot.innerHTML = `
      <style>
        ha-card {
          overflow: hidden;
        }

        .card {
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        h2,
        h3,
        p {
          margin: 0;
        }

        h2 {
          font-size: 20px;
          line-height: 1.25;
          letter-spacing: 0;
        }

        h3 {
          font-size: 14px;
          letter-spacing: 0;
          color: var(--secondary-text-color);
        }

        select {
          width: 100%;
          min-height: 40px;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 8px 10px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          font: inherit;
        }

        ul {
          margin: 0;
          padding-left: 20px;
          line-height: 1.45;
        }

        .instructions {
          white-space: pre-wrap;
          line-height: 1.55;
        }

        .muted {
          color: var(--secondary-text-color);
        }
      </style>
      <ha-card>
        <div class="card">
          <h2>${recipeCardEscape(title)}</h2>
          ${this._renderSelector()}
          ${recipe ? this._renderRecipe(recipe) : `<p class="muted">Keine Rezepte gefunden.</p>`}
        </div>
      </ha-card>
    `;
  }

  _renderSelector() {
    if (this._config.recipe_id || this._recipes.length <= 1) {
      return "";
    }

    return `
      <select data-action="select-recipe">
        ${this._recipes
          .map(
            (recipe) =>
              `<option value="${recipeCardEscape(recipe.id)}" ${
                recipe.id === this._selectedId ? "selected" : ""
              }>${recipeCardEscape(recipe.name)}</option>`
          )
          .join("")}
      </select>
    `;
  }

  _renderRecipe(recipe) {
    const showIngredients = this._config.show_ingredients !== false;
    return `
      ${
        recipe.servings || recipe.duration_minutes || recipe.tags?.length
          ? `<p class="muted">${
              recipe.servings ? `${recipeCardEscape(recipe.servings)} Portionen` : ""
            }${recipe.servings && recipe.duration_minutes ? " · " : ""}${recipe.duration_minutes ? `ca. ${recipeCardEscape(recipe.duration_minutes)} Min.` : ""}${(recipe.servings || recipe.duration_minutes) && recipe.tags?.length ? " · " : ""}${recipe.tags?.map((tag) => recipeCardEscape(tag)).join(", ") || ""}</p>`
          : ""
      }
      ${
        showIngredients
          ? `<section>
              <h3>Zutaten</h3>
              <ul>
                ${recipe.ingredients
                  .map(
                    (ingredient) =>
                      `<li>${recipeCardEscape(recipeCardIngredientLabel(ingredient))}</li>`
                  )
                  .join("")}
              </ul>
            </section>`
          : ""
      }
      <section>
        <h3>Anleitung</h3>
        <div class="instructions">${
          recipe.instructions
            ? recipeCardEscape(recipe.instructions)
            : "Noch keine Anleitung eingetragen."
        }</div>
      </section>
    `;
  }
}

if (!customElements.get("ha-recipe-guide-card")) {
  customElements.define("ha-recipe-guide-card", HaRecipeGuideCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "ha-recipe-guide-card")) {
  window.customCards.push({
    type: "ha-recipe-guide-card",
    name: "Recipe Guide Card",
    description: "Displays saved HA Recipe Manager recipes on dashboards.",
  });
}
