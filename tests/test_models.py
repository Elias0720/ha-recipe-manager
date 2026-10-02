import importlib.util
from pathlib import Path
import sys
import types
import unittest

MODELS_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "ha_recipe_manager"
    / "models.py"
)

package = sys.modules.setdefault("ha_recipe_manager", types.ModuleType("ha_recipe_manager"))
package.__path__ = [str(MODELS_PATH.parent)]
spec = importlib.util.spec_from_file_location("ha_recipe_manager.models", MODELS_PATH)
models = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(models)

ingredient_to_shopping_item = models.ingredient_to_shopping_item
missing_ingredients = models.missing_ingredients
normalize_recipe = models.normalize_recipe


class RecipeModelTest(unittest.TestCase):
    def test_calorie_totals_manual_edits_clear_and_invalid_values(self):
        recipe = normalize_recipe({"name": "Pasta", "total_kcal": "2350"})
        self.assertEqual(recipe["total_kcal"], 2350)
        self.assertEqual(recipe["calories_source"], "manual")
        self.assertFalse(recipe["calories_stale"])
        self.assertEqual(normalize_recipe({"name": "Pasta"}, existing=recipe)["total_kcal"], 2350)
        self.assertEqual(normalize_recipe({"name": "Wasser", "total_kcal": 0})["total_kcal"], 0)
        cleared = normalize_recipe({"name": "Pasta", "total_kcal": None}, existing=recipe)
        self.assertIsNone(cleared["total_kcal"])
        self.assertEqual(cleared["calories_basis"], "")
        for value in (True, -1, "NaN", "Infinity", "2,350", "12.5", "12.0", 100000000):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_recipe({"name": "Pasta", "total_kcal": value})

    def test_calorie_staleness_uses_amounts_notes_and_instructions_not_portions(self):
        recipe = normalize_recipe({"name": "Pasta", "total_kcal": 700,
            "ingredients": [{"id": "one", "name": "Nudeln", "quantity": "200", "unit": "g"}],
            "instructions": "Kochen"})
        for changes in ({"servings": "100"}, {"name": "Neuer Name"}, {"duration_minutes": 20},
                        {"ingredients": [{**recipe["ingredients"][0], "id": "different"}]}):
            self.assertFalse(normalize_recipe({**recipe, **changes}, existing=recipe)["calories_stale"])
        changed = normalize_recipe({**recipe, "ingredients": [{**recipe["ingredients"][0], "quantity": "400"}]}, existing=recipe)
        self.assertTrue(changed["calories_stale"])
        self.assertEqual(changed["total_kcal"], 700)
        confirmed = normalize_recipe({**changed, "calories_manual": True}, existing=changed)
        self.assertFalse(confirmed["calories_stale"])
        self.assertNotEqual(confirmed["calories_revision"], changed["calories_revision"])
        self.assertTrue(normalize_recipe({**recipe, "instructions": "Abtropfen"}, existing=recipe)["calories_stale"])

    def test_optional_time_minutes_and_existing_recipes(self):
        self.assertIsNone(normalize_recipe({"name": "Pasta"})["duration_minutes"])
        recipe = normalize_recipe({"name": "Pasta", "duration_minutes": " 45 "})
        self.assertEqual(recipe["duration_minutes"], 45)
        self.assertEqual(normalize_recipe({"name": "Pasta"}, existing=recipe)["duration_minutes"], 45)
        self.assertIsNone(normalize_recipe({"name": "Pasta", "duration_minutes": ""}, existing=recipe)["duration_minutes"])
        for invalid in ("abc", "30.5", -1, 0, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_recipe({"name": "Pasta", "duration_minutes": invalid})

    def test_normalize_recipe_drops_empty_ingredients(self):
        recipe = normalize_recipe(
            {
                "name": "Pasta",
                "ingredients": [
                    {"name": "Nudeln", "quantity": "500", "unit": "g"},
                    {"name": "   "},
                ],
            },
            now="2026-09-29T10:00:00+00:00",
        )

        self.assertEqual(recipe["name"], "Pasta")
        self.assertEqual(len(recipe["ingredients"]), 1)
        self.assertEqual(recipe["ingredients"][0]["name"], "Nudeln")

    def test_missing_ingredients_uses_checked_ids_and_keeps_repeated_amounts(self):
        recipe = normalize_recipe(
            {
                "name": "Fruehstueck",
                "ingredients": [
                    {"id": "a", "name": "Milch", "quantity": "1", "unit": "l"},
                    {"id": "b", "name": "Brot"},
                    {"id": "c", "name": "Brot"},
                ],
            }
        )

        missing = missing_ingredients(recipe, {"a"})

        self.assertEqual([ingredient["name"] for ingredient in missing], ["Brot", "Brot"])

    def test_ingredient_to_shopping_item_includes_note(self):
        label = ingredient_to_shopping_item(
            {"name": "Eier", "quantity": "6", "unit": "Stk", "note": "Bio"}
        )

        self.assertEqual(label, "6 Stk Eier (Bio)")

    def test_normalize_recipe_rejects_unsafe_source_url(self):
        with self.assertRaisesRegex(ValueError, "HTTP or HTTPS"):
            normalize_recipe({"name": "Pasta", "source_url": "javascript:alert(1)"})

    def test_normalize_recipe_can_preserve_persisted_update_timestamp(self):
        recipe = normalize_recipe(
            {
                "name": "Pasta",
                "updated_at": "2026-01-02T03:04:05+00:00",
            },
            now="2026-09-29T10:00:00+00:00",
            preserve_updated_at=True,
        )

        self.assertEqual(recipe["updated_at"], "2026-01-02T03:04:05+00:00")


if __name__ == "__main__":
    unittest.main()
