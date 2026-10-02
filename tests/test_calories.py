"""Calorie estimation with an HA service double; never calls a paid provider."""

import asyncio
import json
import types
import unittest
from unittest.mock import patch

from test_store_and_shopping import (
    FakeHass, HomeAssistantError, _install_module, const, models, store_module,
)

calories = _install_module("custom_components.ha_recipe_manager.calories", "calories.py")


class FakeConversationServices:
    def __init__(self, text=None, hook=None, error=None, response=None):
        self.text = text if text is not None else json.dumps({
            "total_kcal": 2350, "total_protein_g": 80.5, "total_fat_g": 20.2, "total_sugar_g": 32.6,
            "assumptions": "Nudeln trocken; Zwiebel ca. 100 g.",
            "sources": [{"title": "Quelle", "url": "https://example.com/nutrients"}],
        })
        self.hook = hook
        self.error = error
        self.response = response
        self.calls = []

    def has_service(self, domain, service):
        return (domain, service) == ("conversation", "process")

    async def async_call(self, domain, service, data, **kwargs):
        self.calls.append((domain, service, data, kwargs))
        if self.hook:
            await self.hook()
        if self.error:
            raise self.error
        if self.response is not None:
            return {"response": self.response}
        return {"response": {"response_type": "action_done", "speech": {"plain": {"speech": self.text}}}}


class CalorieResponseTest(unittest.TestCase):
    def test_error_details_are_bounded_and_google_api_keys_redacted(self):
        key = "AIza" + "a" * 35
        message = calories.calorie_error_message(f"API key invalid: {key}", "unknown")
        self.assertNotIn(key, message)
        self.assertIn("[API-Schlüssel entfernt]", message)
        self.assertIn("unknown", message)
        self.assertIn("Protokolle", message)
        self.assertLess(len(calories.calorie_error_message("x" * 10000)), 2400)

    def test_fenced_json_sources_and_zero(self):
        value = calories.parse_calorie_response('```json\n{"total_kcal":0,"total_protein_g":0,"total_fat_g":0,"total_sugar_g":0,"assumptions":["Wasser"],"sources":[{"url":"javascript:alert(1)"},{"url":"https://example.com/x","title":"X"}]}\n``` [1]')
        self.assertEqual(value["total_kcal"], 0)
        self.assertEqual(value["calories_notes"], "Wasser")
        self.assertEqual(value["calories_sources"], [{"title": "X", "url": "https://example.com/x"}])

    def test_unusable_or_ambiguous_answers_rejected(self):
        for text in ('2350 kcal', '{}', '{"total_kcal":null}', '{"total_kcal":true}',
                     '{"total_kcal":-1}', '{"total_kcal":NaN}', '{"total_kcal":12.5}',
                     '{"total_kcal":10}{"total_kcal":20}', '{"total_kcal":Infinity}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                calories.parse_calorie_response(text)

    def test_incomplete_or_invalid_nutrients_are_rejected(self):
        valid = {"total_kcal": 700, "total_protein_g": 10.25, "total_fat_g": 5, "total_sugar_g": 0}
        self.assertEqual(calories.parse_calorie_response(json.dumps(valid))["total_protein_g"], 10.3)
        for key in ("total_protein_g", "total_fat_g", "total_sugar_g"):
            missing = {name: value for name, value in valid.items() if name != key}
            with self.subTest(key=key, missing=True), self.assertRaisesRegex(ValueError, "vollständigen"):
                calories.parse_calorie_response(json.dumps(missing))
            for value in (None, True, -1, "NaN", "Infinity"):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    calories.parse_calorie_response(json.dumps({**valid, key: value}))


class CalorieServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = store_module.RecipeStore(object())
        self.recipe = await self.store.async_save_recipe({"id": "pasta", "name": "Pasta", "servings": "4",
            "ingredients": [{"name": "Nudeln", "quantity": "500", "unit": "g"},
                            {"name": "Zwiebel", "quantity": "1", "unit": "Stk"}]})

    def hass(self, services=None):
        hass = FakeHass(self.store, services=services or FakeConversationServices())
        hass.states = types.SimpleNamespace(get=lambda _id: object())
        return hass

    async def test_estimate_persists_total_sources_and_survives_reload(self):
        hass = self.hass()
        result = await calories.async_estimate_calories(hass, "pasta", context="user-context")
        self.assertEqual(result["total_kcal"], 2350)
        self.assertEqual(result["total_protein_g"], 80.5)
        self.assertEqual(result["total_fat_g"], 20.2)
        self.assertEqual(result["total_sugar_g"], 32.6)
        self.assertEqual(len(hass.services.calls), 1)
        self.assertEqual(result["calories_source"], "ai")
        self.assertFalse(result["calories_stale"])
        call = hass.services.calls[0]
        self.assertEqual(call[2]["agent_id"], "conversation.google_ai_conversation_2")
        self.assertEqual(call[3], {"blocking": True, "return_response": True, "context": "user-context"})
        prompt_data = json.loads(call[2]["text"].split("Rezeptdaten:\n")[1])
        self.assertEqual(len(prompt_data["ingredients"]), 2)
        self.assertNotIn("servings", prompt_data)
        reloaded = store_module.RecipeStore(object())
        reloaded._store.data = self.store._store.saved[-1]
        await reloaded.async_load()
        self.assertEqual(reloaded.get_recipe("pasta")["calories_sources"], result["calories_sources"])
        self.assertEqual(reloaded.get_recipe("pasta")["calories_source"], "ai")
        self.assertFalse(reloaded.get_recipe("pasta")["calories_stale"])
        self.assertEqual(reloaded.get_recipe("pasta")["total_sugar_g"], 32.6)

    async def test_ingredient_edit_during_request_is_kept(self):
        async def edit():
            await self.store.async_save_recipe({**self.recipe, "ingredients": [{"name": "Reis", "quantity": "100", "unit": "g"}]})
        with self.assertRaisesRegex(HomeAssistantError, "geändert"):
            await calories.async_estimate_calories(self.hass(FakeConversationServices(hook=edit)), "pasta")
        self.assertEqual(self.store.get_recipe("pasta")["ingredients"][0]["name"], "Reis")
        self.assertIsNone(self.store.get_recipe("pasta")["total_kcal"])

    async def test_same_value_manual_confirmation_during_request_is_kept(self):
        self.recipe = await self.store.async_save_recipe({**self.recipe, "total_kcal": 1500})
        async def edit():
            await self.store.async_save_recipe({**self.recipe, "calories_manual": True})
        with self.assertRaisesRegex(HomeAssistantError, "geändert"):
            await calories.async_estimate_calories(self.hass(FakeConversationServices(hook=edit)), "pasta")
        self.assertEqual(self.store.get_recipe("pasta")["total_kcal"], 1500)
        self.assertEqual(self.store.get_recipe("pasta")["calories_source"], "manual")

    async def test_unrelated_edit_during_request_is_preserved_with_result(self):
        async def edit():
            await self.store.async_save_recipe({**self.recipe, "name": "Neu", "servings": "8"})
        result = await calories.async_estimate_calories(self.hass(FakeConversationServices(hook=edit)), "pasta")
        self.assertEqual(result["name"], "Neu")
        self.assertEqual(result["servings"], "8")
        self.assertEqual(result["total_kcal"], 2350)

    async def test_manual_protein_confirmation_during_request_is_kept(self):
        self.recipe = await self.store.async_save_recipe({**self.recipe, "total_kcal": 1500, "total_protein_g": 40})
        async def edit():
            await self.store.async_save_recipe({**self.recipe, "nutrition_manual_fields": ["total_protein_g"]})
        with self.assertRaisesRegex(HomeAssistantError, "geändert"):
            await calories.async_estimate_calories(self.hass(FakeConversationServices(hook=edit)), "pasta")
        self.assertEqual(self.store.get_recipe("pasta")["total_kcal"], 1500)
        self.assertEqual(self.store.get_recipe("pasta")["total_protein_g"], 40)

    async def test_incomplete_estimate_keeps_all_previous_nutrients(self):
        self.recipe = await self.store.async_save_recipe({**self.recipe, "total_kcal": 1500,
            "total_protein_g": 40, "total_fat_g": 5, "total_sugar_g": 0})
        hass = self.hass(FakeConversationServices(text=json.dumps({"total_kcal": 2350, "total_protein_g": 80})))
        with self.assertRaisesRegex(HomeAssistantError, "vollständigen"):
            await calories.async_estimate_calories(hass, "pasta")
        for key in models.NUTRIENT_FIELDS:
            self.assertEqual(self.store.get_recipe("pasta")[key], self.recipe[key])

    async def test_deleted_recipe_not_recreated(self):
        async def delete():
            await self.store.async_delete_recipe("pasta")
        with self.assertRaisesRegex(HomeAssistantError, "gelöscht"):
            await calories.async_estimate_calories(self.hass(FakeConversationServices(hook=delete)), "pasta")
        self.assertIsNone(self.store.get_recipe("pasta"))

    async def test_provider_errors_and_bad_output_leave_old_total_and_allow_retry(self):
        self.recipe = await self.store.async_save_recipe({**self.recipe, "total_kcal": 1500})
        for services in (FakeConversationServices(error=HomeAssistantError("quota")),
                         FakeConversationServices(text="no JSON"), FakeConversationServices(text="")):
            hass = self.hass(services)
            with self.assertRaises(HomeAssistantError):
                await calories.async_estimate_calories(hass, "pasta")
            self.assertEqual(self.store.get_recipe("pasta")["total_kcal"], 1500)
            self.assertEqual(hass.data[const.DOMAIN][const.DATA_CALORIE_REQUESTS], set())
            hass.services = FakeConversationServices()
            self.assertEqual((await calories.async_estimate_calories(hass, "pasta"))["total_kcal"], 2350)
            self.recipe = await self.store.async_save_recipe({**self.store.get_recipe("pasta"), "total_kcal": 1500})

    async def test_duplicate_request_and_timeout_do_not_spend_or_change_twice(self):
        gate = asyncio.Event()
        hass = self.hass(FakeConversationServices(hook=gate.wait))
        pending = asyncio.create_task(calories.async_estimate_calories(hass, "pasta"))
        await asyncio.sleep(0)
        with self.assertRaisesRegex(HomeAssistantError, "bereits"):
            await calories.async_estimate_calories(hass, "pasta")
        gate.set()
        await pending
        self.assertEqual(len(hass.services.calls), 1)
        hass.services = FakeConversationServices(hook=asyncio.Event().wait)
        with patch.object(calories, "CALORIE_TIMEOUT", 0.01), self.assertRaisesRegex(HomeAssistantError, "rechtzeitig"):
            await calories.async_estimate_calories(hass, "pasta")
        self.assertEqual(hass.data[const.DOMAIN][const.DATA_CALORIE_REQUESTS], set())

    async def test_ha_error_response_preserves_provider_message_code_and_old_total(self):
        self.recipe = await self.store.async_save_recipe({**self.recipe, "total_kcal": 1500})
        message = "429 RESOURCE_EXHAUSTED: quota exceeded"
        hass = self.hass(FakeConversationServices(response={
            "response_type": "error", "data": {"code": "unknown"},
            "speech": {"plain": {"speech": message}},
        }))
        with self.assertRaises(HomeAssistantError) as raised:
            await calories.async_estimate_calories(hass, "pasta")
        self.assertIn(message, str(raised.exception))
        self.assertIn("unknown", str(raised.exception))
        self.assertEqual(self.store.get_recipe("pasta")["total_kcal"], 1500)
        self.assertEqual(hass.data[const.DOMAIN][const.DATA_CALORIE_REQUESTS], set())
        self.assertEqual(len(hass.services.calls), 1)

    async def test_ha_error_response_without_speech_or_data_still_reports_failure(self):
        for response in ({"response_type": "error"},
                         {"response_type": "error", "speech": {"plain": {"speech": '{"total_kcal":99}'}}},
                         ["invalid"]):
            with self.subTest(response=response), self.assertRaises(HomeAssistantError):
                await calories.async_estimate_calories(self.hass(FakeConversationServices(response=response)), "pasta")
            self.assertIsNone(self.store.get_recipe("pasta")["total_kcal"])

    async def test_service_exception_preserves_its_message(self):
        hass = self.hass(FakeConversationServices(error=HomeAssistantError("403 PERMISSION_DENIED")))
        with self.assertRaisesRegex(HomeAssistantError, "403 PERMISSION_DENIED"):
            await calories.async_estimate_calories(hass, "pasta")

    async def test_missing_agent_and_empty_recipe_fail_before_call(self):
        hass = self.hass()
        hass.states.get = lambda _id: None
        with self.assertRaisesRegex(HomeAssistantError, "fehlt"):
            await calories.async_estimate_calories(hass, "pasta")
        self.assertEqual(hass.services.calls, [])
        await self.store.async_save_recipe({"id": "empty", "name": "Leer"})
        with self.assertRaisesRegex(HomeAssistantError, "Zutaten"):
            await calories.async_estimate_calories(hass, "empty")

    async def test_storage_failure_keeps_previous_value_in_memory(self):
        self.recipe = await self.store.async_save_recipe({**self.recipe, "total_kcal": 1500})
        async def fail(_data):
            raise OSError("Disk unavailable")
        self.store._store.async_save = fail
        with self.assertRaisesRegex(HomeAssistantError, "gespeichert"):
            await calories.async_estimate_calories(self.hass(), "pasta")
        self.assertEqual(self.store.get_recipe("pasta")["total_kcal"], 1500)
        self.assertEqual(self.store.get_recipe("pasta")["calories_source"], "manual")


if __name__ == "__main__":
    unittest.main()
