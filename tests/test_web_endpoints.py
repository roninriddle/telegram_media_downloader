"""Web endpoint tests."""

import os
import tempfile
import unittest

from module.app import Application
from module.download_stat import get_download_result
from module import task_history
from module import web


class WebEndpointTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = self.tempdir.name
        self.config_path = os.path.join(root, "config", "config.yaml")
        self.data_path = os.path.join(root, "config", "data.yaml")
        self.history_path = os.path.join(root, "config", "task_history.json")
        for name in ("config", "downloads", "log", "sessions", "temp"):
            os.makedirs(os.path.join(root, name), exist_ok=True)
        task_history.configure_history_file(self.history_path)
        self.app = Application(self.config_path, self.data_path)
        self.app.save_path = os.path.join(root, "downloads")
        self.app.temp_save_path = os.path.join(root, "temp")
        self.app.log_file_path = os.path.join(root, "log")
        self.app.session_file_path = os.path.join(root, "sessions")
        web._application = self.app
        web.get_flask_app().config["LOGIN_DISABLED"] = True
        self.client = web.get_flask_app().test_client()

    def tearDown(self):
        get_download_result().clear()
        task_history.configure_history_file("task_history.json")
        self.tempdir.cleanup()

    def test_config_schema_endpoint(self):
        response = self.client.get("/api/config/schema")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("schema", payload)
        self.assertIn("defaults", payload)

    def test_save_minimal_config(self):
        response = self.client.post(
            "/api/config",
            json={
                "config": {
                    "api_id": "12345",
                    "api_hash": "abc123",
                    "chat": [{"chat_id": "me"}],
                    "media_types": ["photo"],
                    "file_formats": {"photo": ["all"]},
                }
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertTrue(payload["ready"])
        self.assertTrue(os.path.exists(self.config_path))

    def test_zero_size_download_record(self):
        get_download_result().clear()
        get_download_result()["chat"] = {
            1: {
                "down_byte": 0,
                "total_size": 0,
                "file_name": "/tmp/empty.bin",
                "download_speed": 0,
            }
        }
        response = self.client.get("/get_download_list?already_down=false")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload[0]["download_progress"], "0")

    def test_system_status_endpoint(self):
        response = self.client.get("/api/system/status")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("paths", payload)
        self.assertGreaterEqual(len(payload["paths"]), 4)


if __name__ == "__main__":
    unittest.main()
