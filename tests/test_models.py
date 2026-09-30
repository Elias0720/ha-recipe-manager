import importlib.util
from pathlib import Path
import unittest

MODELS_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "ha_recipe_manager"
    / "models.py"
)

spec = importlib.util.spec_from_file_location("ha_recipe_manager_models", MODELS_PATH)
models = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(models)

ingredient_to_shopping_item = models.ingredient_to_shopping_item
missing_ingredients = models.missing_ingredients
normalize_recipe = models.normalize_recipe


class RecipeModelTest(unittest.TestCase):
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
