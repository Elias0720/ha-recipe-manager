import asyncio
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
shopping_items = _install_module("custom_components.ha_recipe_manager.shopping_items", "shopping_items.py")
shopping = _install_module("custom_components.ha_recipe_manager.shopping", "shopping.py")


class FakeServices:
    def __init__(self, available=True):
        self.available = available
        self.calls = []
        self.shopping_data = None

    def has_service(self, domain, service):
        return self.available and domain == "shopping_list" and service == "add_item"

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, data, blocking))
        await asyncio.sleep(0)
        self.shopping_data.items.append({
            "id": f"added-{len(self.calls)}", "name": data["name"], "complete": False,
        })


class FakeShoppingData:
    def __init__(self, items=()):
        self.items = [dict(item) for item in items]
        self.updates = []
        self.removed = []

    async def async_update(self, item_id, info):
        await asyncio.sleep(0)
        item = next(item for item in self.items if item["id"] == item_id)
        item.update(info)
        self.updates.append((item_id, info))
        return item

    async def async_remove(self, item_id):
        self.items = [item for item in self.items if item["id"] != item_id]
        self.removed.append(item_id)


class FakeHass:
    def __init__(self, recipe_store, services=None, items=(), runtime_data=False):
        shopping_data = FakeShoppingData(items)
        self.data = {const.DOMAIN: {const.DATA_STORE: recipe_store}}
        if not runtime_data:
            self.data["shopping_list"] = shopping_data
        self.config_entries = types.SimpleNamespace(async_entries=lambda domain: [
            types.SimpleNamespace(runtime_data=shopping_data)
        ] if runtime_data else [])
        self.services = services or FakeServices()
        self.services.shopping_data = shopping_data


class RecipeStoreTest(unittest.IsolatedAsyncioTestCase):
    async def _ranked_store(self):
        recipe_store = store_module.RecipeStore(object())
        for recipe_id in ("pizza", "bolognese", "lasagne"):
            await recipe_store.async_save_recipe({"id": recipe_id, "name": recipe_id.title()})
        await recipe_store.async_save_ranking("taste", ["pizza", "bolognese", "lasagne"])
        await recipe_store.async_save_ranking("effort", ["bolognese", "lasagne", "pizza"])
        return recipe_store

    async def test_rankings_persist_independently_and_survive_reload(self):
        recipe_store = await self._ranked_store()
        saved = recipe_store._store.saved[-1]
        reloaded = store_module.RecipeStore(object())
        reloaded._store.data = saved
        await reloaded.async_load()
        self.assertEqual(reloaded.get_rankings(), {
            "taste": ["pizza", "bolognese", "lasagne"],
            "effort": ["bolognese", "lasagne", "pizza"],
        })
        returned = reloaded.get_rankings()
        returned["taste"].clear()
        self.assertEqual(len(reloaded.get_rankings()["taste"]), 3)

    async def test_old_storage_is_loaded_and_stale_ranks_are_repaired(self):
        recipe_store = store_module.RecipeStore(object())
        recipe_store._store.data = {"recipes": [
            {"id": "b", "name": "Bolognese"}, {"id": "a", "name": "Lasagne"},
        ]}
        await recipe_store.async_load()
        self.assertEqual(recipe_store.get_rankings(), {"taste": ["b", "a"], "effort": ["b", "a"]})
        recipe_store._store.data["rankings"] = {"taste": ["a", "a", "deleted", None], "effort": "bad"}
        await recipe_store.async_load()
        self.assertEqual(recipe_store.get_rankings(), {"taste": ["a", "b"], "effort": ["b", "a"]})

    async def test_recipe_creation_edit_and_deletion_preserve_other_ranks(self):
        recipe_store = await self._ranked_store()
        await recipe_store.async_save_recipe({"id": "apfel", "name": "Apfelstrudel", "duration_minutes": "70"})
        self.assertEqual(recipe_store.get_rankings()["taste"], ["pizza", "bolognese", "lasagne", "apfel"])
        await recipe_store.async_save_recipe({"id": "pizza", "name": "Neue Pizza", "duration_minutes": 25})
        self.assertEqual(recipe_store.get_rankings()["effort"], ["bolognese", "lasagne", "pizza", "apfel"])
        await recipe_store.async_delete_recipe("bolognese")
        self.assertEqual(recipe_store.get_rankings()["taste"], ["pizza", "lasagne", "apfel"])
        self.assertEqual(recipe_store.get_recipe("pizza")["duration_minutes"], 25)

    async def test_invalid_or_stale_ranking_never_changes_saved_order(self):
        recipe_store = await self._ranked_store()
        expected = recipe_store.get_rankings()
        for kind, order in [("unknown", ["pizza", "bolognese", "lasagne"]),
                            ("taste", ["pizza", "pizza", "lasagne"]),
                            ("taste", ["pizza", "lasagne"]),
                            ("taste", ["pizza", "lasagne", "missing"])]:
            with self.subTest(kind=kind, order=order), self.assertRaises(ValueError):
                await recipe_store.async_save_ranking(kind, order)
            self.assertEqual(recipe_store.get_rankings(), expected)

    async def test_failed_persistence_keeps_previous_rankings_and_recipes(self):
        recipe_store = await self._ranked_store()
        expected = recipe_store.get_rankings()
        async def fail(_data):
            raise OSError("Disk unavailable")
        recipe_store._store.async_save = fail
        with self.assertRaises(OSError):
            await recipe_store.async_save_ranking("taste", ["lasagne", "bolognese", "pizza"])
        with self.assertRaises(OSError):
            await recipe_store.async_save_recipe({"id": "new", "name": "New"})
        with self.assertRaises(OSError):
            await recipe_store.async_delete_recipe("pizza")
        self.assertEqual(recipe_store.get_rankings(), expected)
        self.assertIsNone(recipe_store.get_recipe("new"))
        self.assertIsNotNone(recipe_store.get_recipe("pizza"))

    async def test_simultaneous_ranking_updates_keep_both_orders(self):
        recipe_store = await self._ranked_store()
        await asyncio.gather(
            recipe_store.async_save_ranking("taste", ["lasagne", "pizza", "bolognese"]),
            recipe_store.async_save_ranking("effort", ["pizza", "lasagne", "bolognese"]),
        )
        self.assertEqual(recipe_store.get_rankings(), {
            "taste": ["lasagne", "pizza", "bolognese"], "effort": ["pizza", "lasagne", "bolognese"],
        })

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
    async def test_only_unchecked_ingredients_are_added_and_repeats_are_counted(self):
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

        self.assertEqual(labels, ["2x Brot"])
        self.assertEqual(
            services.calls,
            [("shopping_list", "add_item", {"name": "Brot"}, True)],
        )
        self.assertEqual(services.shopping_data.items[0]["name"], "2x Brot")

    async def _add(self, ingredients, items=(), runtime_data=False):
        recipe_store = store_module.RecipeStore(object())
        recipe = await recipe_store.async_save_recipe({"name": "Test", "ingredients": ingredients})
        hass = FakeHass(recipe_store, items=items, runtime_data=runtime_data)
        labels = await shopping.async_add_missing_to_shopping_list(hass, recipe["id"])
        return labels, hass

    async def test_200g_and_300g_carrots_are_500g_with_same_item_id(self):
        labels, hass = await self._add(
            [{"name": "Karotten", "quantity": "300", "unit": "g"}],
            [{"id": "carrots", "name": "200g Karotten", "complete": False}],
        )
        self.assertEqual(labels, ["500 g Karotten"])
        self.assertEqual(hass.services.calls, [])
        self.assertEqual(hass.services.shopping_data.items, [
            {"id": "carrots", "name": "500 g Karotten", "complete": False}
        ])

    async def test_unitless_onions_and_celery_are_counted_across_recipes(self):
        labels, hass = await self._add(
            [{"name": "Zwiebeln"}, {"name": "Sellerie"}, {"name": "Zwiebel"}],
            [{"id": "onion", "name": "Zwiebel", "complete": False},
             {"id": "celery", "name": "Sellerie", "complete": False}],
        )
        self.assertEqual(labels, ["3x Zwiebel", "2x Sellerie"])
        self.assertEqual(len(hass.services.shopping_data.items), 2)

    async def test_compatible_units_case_and_decimal_commas(self):
        for existing, ingredient, expected in [
            ("200 Gramm KAROTTEN", {"name": "Karotte", "quantity": "0,3", "unit": "kg"}, "500 g KAROTTEN"),
            ("0,2 kg Karotten", {"name": "Karotten", "quantity": "30", "unit": "dag"}, "0,5 kg Karotten"),
            ("500 ml Milch", {"name": "Milch", "quantity": "1/2", "unit": "Liter"}, "1000 ml Milch"),
            ("2 Stk. Zwiebeln", {"name": "Zwiebel"}, "3x Zwiebeln"),
            ("2 x Sellerie", {"name": "Sellerie"}, "3x Sellerie"),
            ("1 Dose Tomaten", {"name": "Tomaten", "quantity": "2", "unit": "Dosen"}, "3 Dose Tomaten"),
        ]:
            with self.subTest(existing=existing):
                labels, _ = await self._add([ingredient], [{"id": "one", "name": existing, "complete": False}])
                self.assertEqual(labels, [expected])

    async def test_existing_duplicate_open_rows_are_consolidated(self):
        labels, hass = await self._add(
            [{"name": "Karotten", "quantity": "100", "unit": "g"}],
            [{"id": "a", "name": "200 g Karotten", "complete": False},
             {"id": "b", "name": "0,3 kg Karotten", "complete": False},
             {"id": "done", "name": "500 g Karotten", "complete": True}],
        )
        self.assertEqual(labels, ["600 g Karotten"])
        self.assertEqual(hass.services.shopping_data.removed, ["b"])
        self.assertEqual(hass.services.shopping_data.items[-1]["name"], "500 g Karotten")

    async def test_completed_items_are_not_reopened_or_counted(self):
        labels, hass = await self._add(
            [{"name": "Sellerie"}], [{"id": "done", "name": "Sellerie", "complete": True}],
        )
        self.assertEqual(labels, ["Sellerie"])
        self.assertEqual(len(hass.services.shopping_data.items), 2)
        self.assertTrue(hass.services.shopping_data.items[0]["complete"])

    async def test_different_units_names_notes_and_unknown_amounts_stay_separate(self):
        for existing, ingredient in [
            ("200 g Karotten", {"name": "Karotten", "quantity": "2", "unit": "Stk"}),
            ("Zwiebel", {"name": "Frühlingszwiebel"}),
            ("Sellerie", {"name": "Selleriesalz"}),
            ("200 g Karotten (Bio)", {"name": "Karotten", "quantity": "300", "unit": "g"}),
            ("1-2 Zwiebeln", {"name": "Zwiebel"}),
            ("200 g Karotten", {"name": "Karotten", "quantity": "nach Bedarf", "unit": "g"}),
            ("200 g Karotten", {"name": "Karotten", "quantity": "0", "unit": "g"}),
        ]:
            with self.subTest(existing=existing, ingredient=ingredient):
                _, hass = await self._add([ingredient], [{"id": "one", "name": existing, "complete": False}])
                self.assertEqual(len(hass.services.shopping_data.items), 2)
                self.assertEqual(hass.services.shopping_data.items[0]["name"], existing)

    async def test_matching_notes_and_repeated_recipe_quantities_are_combined(self):
        labels, hass = await self._add([
            {"name": "Karotten", "quantity": "200", "unit": "g", "note": "Bio"},
            {"name": "Karotten", "quantity": "200", "unit": "g", "note": "Bio"},
        ])
        self.assertEqual(labels, ["400 g Karotten (Bio)"])
        self.assertEqual(len(hass.services.shopping_data.items), 1)

    async def test_config_entry_runtime_data_is_supported(self):
        labels, _ = await self._add(
            [{"name": "Sellerie"}], [{"id": "a", "name": "Sellerie", "complete": False}],
            runtime_data=True,
        )
        self.assertEqual(labels, ["2x Sellerie"])

    async def test_simultaneous_recipe_additions_do_not_lose_quantities(self):
        recipe_store = store_module.RecipeStore(object())
        recipes = [await recipe_store.async_save_recipe({
            "name": f"Rezept {quantity}",
            "ingredients": [{"name": "Karotten", "quantity": quantity, "unit": "g"}],
        }) for quantity in ("200", "300")]
        hass = FakeHass(recipe_store)
        await asyncio.gather(*(shopping.async_add_missing_to_shopping_list(hass, recipe["id"]) for recipe in recipes))
        self.assertEqual([item["name"] for item in hass.services.shopping_data.items], ["500 g Karotten"])

    async def test_all_checked_does_not_touch_shopping_list(self):
        recipe_store = store_module.RecipeStore(object())
        recipe = await recipe_store.async_save_recipe({"name": "Test", "ingredients": [{"id": "one", "name": "Sellerie"}]})
        hass = FakeHass(recipe_store)
        self.assertEqual(await shopping.async_add_missing_to_shopping_list(hass, recipe["id"], ["one"]), [])
        self.assertEqual(hass.services.calls, [])

    async def test_missing_shopping_list_service_is_reported(self):
        recipe_store = store_module.RecipeStore(object())
        hass = FakeHass(recipe_store, FakeServices(available=False))

        with self.assertRaisesRegex(HomeAssistantError, "not available"):
            await shopping.async_add_missing_to_shopping_list(hass, "unknown")


if __name__ == "__main__":
    unittest.main()
