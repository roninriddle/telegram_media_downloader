"""Config schema tests."""

import unittest

from module.config_schema import get_config_errors, get_default_config, merge_config


class ConfigSchemaTest(unittest.TestCase):
    def test_default_config_reports_required_fields(self):
        errors = get_config_errors(get_default_config())
        self.assertIn("api_id is required", errors)
        self.assertIn("api_hash is required", errors)
        self.assertIn("at least one chat_id is required", errors)

    def test_minimal_config_is_ready(self):
        config = merge_config(
            get_default_config(),
            {
                "api_id": "12345",
                "api_hash": "abc123",
                "chat": [{"chat_id": "me"}],
                "media_types": ["photo"],
                "file_formats": {"photo": ["all"]},
            },
        )
        self.assertEqual(get_config_errors(config), [])


if __name__ == "__main__":
    unittest.main()
