"""A campaign proves its channel before starting and sends its calls for a person."""

import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))
import alert_email
import tmp_root  # noqa: F401 — isolate every test file
from workspace import Workspace

spec = importlib.util.spec_from_file_location("contact_graph_goal", HERE / "graph-goal.py")
goal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(goal)


class CampaignContactTest(unittest.TestCase):
    def test_contact_is_proved_before_work_and_receives_person_events(self):
        with tempfile.TemporaryDirectory() as directory:
            space = Workspace(directory)
            argv = ["--workspace", directory]
            for command in (["plan"], ["run"], ["sources", "--source", "brief.md"]):
                with self.subTest(command=command), self.assertRaisesRegex(SystemExit, "contact"):
                    goal.main(argv + command)
            self.assertEqual([], space.events())
            channel = "person@example.test"
            creds = {"SMTP_HOST": "smtp.example.test", "SMTP_PORT": "465", "SMTP_USER": "test",
                     "SMTP_PASS": "test", "SMTP_FROM": "sender@example.test", "SMTP_TO": "old@example.test"}
            with mock.patch.object(alert_email, "credentials", return_value=creds), \
                 mock.patch.object(alert_email.smtplib, "SMTP_SSL") as smtp:
                sender = smtp.return_value
                sender.send_message.side_effect = OSError("test send failed")
                with self.assertRaisesRegex(OSError, "test send failed"):
                    goal.main(argv + ["contact", channel])
                self.assertFalse((space.root / "contact").exists())
                sender.send_message.side_effect = None
                sender.send_message.return_value = {}
                self.assertEqual(0, goal.main(argv + ["contact", channel]))
                self.assertEqual(f"[{space.root.name}] graph-loop: can this campaign reach you?",
                                 sender.send_message.call_args.args[0]["Subject"])
                self.assertEqual(channel, (space.root / "contact").read_text().strip())
                sender.send_message.reset_mock()
                space.event("needs_a_person", task="T1", why="choose the format")
                space.event("slice_needs_person", task="T2", why="supply the source")
                space.alert("T3", "read this alert")
                self.assertEqual(3, sender.send_message.call_count)
                for call, wording in zip(sender.send_message.call_args_list,
                                         ("choose the format", "supply the source", "read this alert")):
                    message = call.args[0]
                    self.assertEqual(channel, message["To"])
                    self.assertTrue(message["Subject"].startswith(f"[{space.root.name}] graph-loop needs you: T"))
                    self.assertIn(wording, message.get_content())
                self.assertEqual(["needs_a_person", "slice_needs_person", "alert"],
                                 [row["kind"] for row in space.events()])
                self.assertIn("read this alert", (space.root / "ALERTS.txt").read_text())


if __name__ == "__main__":
    unittest.main()
