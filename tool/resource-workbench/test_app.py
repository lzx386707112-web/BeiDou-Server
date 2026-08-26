from __future__ import annotations

import unittest

from werkzeug.test import Client
from werkzeug.wrappers import Response

from app import create_app


class ResourceWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = Client(create_app(), Response)

    def test_root_renders_persistent_module_host(self):
        response = self.client.get("/")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-initial-module="map-mob"', body)
        self.assertIn('data-src="/quests/?embedded=1"', body)

    def test_root_accepts_initial_module(self):
        response = self.client.get("/?module=quests")
        self.assertIn('data-initial-module="quests"', response.get_data(as_text=True))

    def test_health_lists_mounted_modules(self):
        payload = self.client.get("/api/health").get_json()
        self.assertEqual(payload["modules"], ["map-mob", "img-editor", "quests"])

    def test_map_mob_page_uses_integrated_navigation(self):
        response = self.client.get("/map-mob/")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-api-base="/map-mob"', body)
        self.assertIn('class="suite-link active"', body)
        embedded = self.client.get("/map-mob/?embedded=1").get_data(as_text=True)
        self.assertNotIn('class="suite-nav"', embedded)
        self.assertIn('class="module-embedded"', embedded)

    def test_img_editor_page_and_api_are_mounted(self):
        page = self.client.get("/img-editor/")
        body = page.get_data(as_text=True)
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-api-base="/img-editor"', body)
        self.assertIn('href="/?module=map-mob"', body)

        state = self.client.get("/img-editor/api/state")
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.get_json(), {"opened": False})

    def test_quest_manager_page_is_mounted(self):
        page = self.client.get("/quests/")
        body = page.get_data(as_text=True)
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-api-base="/quests"', body)
        self.assertIn("任务管理", body)


if __name__ == "__main__":
    unittest.main()
