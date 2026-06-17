"""Task history persistence tests."""

import os
import tempfile
import unittest

from module import task_history


class TaskHistoryTest(unittest.TestCase):
    def test_record_and_list_done_task(self):
        with tempfile.TemporaryDirectory() as directory:
            history_file = os.path.join(directory, "task_history.json")
            task_history.configure_history_file(history_file)
            task_history.record_task("chat", 10, 100, 100, "/tmp/file.bin", 0)
            rows = task_history.list_history(status="done")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["chat"], "chat")
            self.assertEqual(rows[0]["id"], "10")
            self.assertTrue(os.path.exists(history_file))


if __name__ == "__main__":
    unittest.main()
