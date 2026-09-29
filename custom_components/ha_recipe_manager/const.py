"""Constants for HA Recipe Manager."""

DOMAIN = "ha_recipe_manager"
NAME = "HA Recipe Manager"

DATA_STORE = "store"
DATA_WEBSOCKET_REGISTERED = "websocket_registered"
DATA_FRONTEND_REGISTERED = "frontend_registered"

EVENT_RECIPES_UPDATED = f"{DOMAIN}_recipes_updated"
EVENT_SHOPPING_LIST_FILLED = f"{DOMAIN}_shopping_list_filled"

FRONTEND_BASE = f"/{DOMAIN}_static"
PANEL_URL_PATH = "recipes"
PANEL_MODULE_URL = f"{FRONTEND_BASE}/ha-recipe-manager-panel.js"
CARD_MODULE_URL = f"{FRONTEND_BASE}/recipe-guide-card.js"

PANEL_NAME = "ha-recipe-manager-panel"
PANEL_TITLE = "Rezepte"
PANEL_ICON = "mdi:chef-hat"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

SERVICE_ADD_MISSING = "add_missing_to_shopping_list"
