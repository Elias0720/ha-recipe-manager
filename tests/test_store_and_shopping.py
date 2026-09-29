import importlib.util
from pathlib import Path
import sys
import types
import unittest


COMPONENT_PATH = (
    Path(__file__).resolve().parents[1] / "custom_components" / "ha_recipe_manager"
)


class HomeAssistantError(Exception):
    pass


class FakePersistentStore:
    def __init__(self, _hass, _version, _key):
        self.data = None
        self.saved = []

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.saved.append(data)


def _install_module(full_name, file_name):
    spec = importlib.util.spec_from_file_location(full_name, COMPONENT_PATH / file_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


homeassistant = types.ModuleType("homeassistant")
homeassistant.__path__ = []
homeassistant_core = types.ModuleType("homeassistant.core")
homeassistant_core.HomeAssistant = object
homeassistant_exceptions = types.ModuleType("homeassistant.exceptions")
homeassistant_exceptions.HomeAssistantError = HomeAssistantError
homeassistant_helpers = types.ModuleType("homeassistant.helpers")
homeassistant_helpers.__path__ = []
homeassistant_storage = types.ModuleType("homeassistant.helpers.storage")
homeassistant_storage.Store = FakePersistentStore

sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.core", homeassistant_core)
sys.modules.setdefault("homeassistant.exceptions", homeassistant_exceptions)
sys.modules.setdefault("homeassistant.helpers", homeassistant_helpers)
sys.modules.setdefault("homeassistant.helpers.storage", homeassistant_storage)

custom_components = sys.modules.setdefault(
    "custom_components", types.ModuleType("custom_components")
)
custom_components.__path__ = [str(COMPONENT_PATH.parent)]
component_package = types.ModuleType("custom_components.ha_recipe_manager")
component_package.__path__ = [str(COMPONENT_PATH)]
sys.modules["custom_components.ha_recipe_manager"] = component_package

const = _install_module("custom_components.ha_recipe_manager.const", "const.py")
models = _install_module("custom_components.ha_recipe_manager.models", "models.py")
store_module = _install_module("custom_components.ha_recipe_manager.store", "store.py")
shopping = _install_module("custom_components.ha_recipe_manager.shopping", "shopping.py")


class FakeServices:
    def __init__(self, available=True):
        self.available = available
        self.calls = []

    def has_service(self, domain, service):
        return self.available and domain == "shopping_list" and service == "add_item"

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, data, blocking))


class FakeHass:
    def __init__(self, recipe_store, services=None):
        self.data = {const.DOMAIN: {const.DATA_STORE: recipe_store}}
        self.services = services or FakeServices()


class RecipeStoreTest(unittest.IsolatedAsyncioTestCase):
    async def test_load_keeps_persisted_timestamps(self):
        recipe_store = store_module.RecipeStore(object())
        recipe_store._store.data = {
            "recipes": [
                {
                    "id": "pasta",
                    "name": "Pasta",
                    "created_at": "2026-01-01T10:00:00+00:00",
                    "updated_at": "2026-01-02T10:00:00+00:00",
                    "ingredients": [],
                }
            ]
        }

        await recipe_store.async_load()

        recipe = recipe_store.get_recipe("pasta")
        self.assertEqual(recipe["updated_at"], "2026-01-02T10:00:00+00:00")

    async def test_save_persists_normalized_recipe(self):
        recipe_store = store_module.RecipeStore(object())

        recipe = await recipe_store.async_save_recipe(
            {
                "name": "Pasta",
                "ingredients": [{"name": "Nudeln", "quantity": "500", "unit": "g"}],
            }
        )

        self.assertEqual(recipe_store._store.saved[-1]["recipes"][0]["id"], recipe["id"])
        self.assertEqual(recipe_store._store.saved[-1]["recipes"][0]["name"], "Pasta")


class ShoppingListTest(unittest.IsolatedAsyncioTestCase):
    async def test_only_unchecked_unique_ingredients_are_added(self):
        recipe_store = store_module.RecipeStore(object())
        recipe = await recipe_store.async_save_recipe(
            {
                "id": "breakfast",
                "name": "Frühstück",
                "ingredients": [
                    {"id": "milk", "name": "Milch", "quantity": "1", "unit": "l"},
                    {"id": "bread-a", "name": "Brot"},
                    {"id": "bread-b", "name": "Brot"},
                ],
            }
        )
        services = FakeServices()
        hass = FakeHass(recipe_store, services)

        labels = await shopping.async_add_missing_to_shopping_list(
            hass, recipe["id"], ["milk"]
        )

        self.assertEqual(labels, ["Brot"])
        self.assertEqual(
            services.calls,
            [("shopping_list", "add_item", {"name": "Brot"}, True)],
        )

    async def test_missing_shopping_list_service_is_reported(self):
        recipe_store = store_module.RecipeStore(object())
        hass = FakeHass(recipe_store, FakeServices(available=False))

        with self.assertRaisesRegex(HomeAssistantError, "not available"):
            await shopping.async_add_missing_to_shopping_list(hass, "unknown")


if __name__ == "__main__":
    unittest.main()
