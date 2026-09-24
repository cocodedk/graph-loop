"""The exported issue and its signature carry no machine or provider identity."""

from __future__ import annotations

import unittest

from test_loop import Fakes, loop_for, task
from turn import stood_down


class StallDraftPrivacyTest(unittest.TestCase):
    def test_scrubbed_failures_group_across_paths_accounts_and_sessions(self):
        _, book, space = loop_for(task(status="rejected"), Fakes(),
                                 [task(id="T2", status="rejected")])
        space.event("driver_started")
        private = []
        for number, card in enumerate(("T1", "T2"), 1):
            user = f"fixture-user-{number}"
            account = f"fixture-account-{number}"
            session = f"12345678-1234-4567-8abc-12345678900{number}"
            # Built in pieces so this fixture obeys the public repository's scrub too.
            home = "/" + "home/" + user
            path = home + f"/project-{number}/test.py"
            config = home + "/" + ".claude-" + "personal"
            words = (f"FAIL: the same assertion at {path}\n"
                     f"session_id={session} account={account}\n"
                     f"config={config}; owner {user}; bare {account} {session}")
            private.extend((path, home, user, account, session, config))
            book.note(card, session=session, session_account=account)
            space.event("attempt", task=card, account=account, session_id=session)
            space.artifact(card, "gate-output", words)
            space.event("failed", task=card, step="gate", why=words)
        stood_down(space, 78, "nothing startable")
        drafts = list((space.root / "issues").glob("*.md"))
        self.assertEqual(1, len(drafts))
        body = drafts[0].name + drafts[0].read_text()
        for value in private:
            self.assertNotIn(value, body)
        self.assertIn("T1", body)
        self.assertIn("T2", body)
        self.assertIn("same assertion", body)

    def test_labels_non_uuid_sessions_and_paths_outside_home_are_scrubbed(self):
        _, _, space = loop_for(task(status="partial_by_agent"), Fakes())
        session = "opaque-session-fixture"
        home = "$" + "HOME/"
        words = (f"session id: {session}\n"
                 "account='example-account'\n"
                 "runner at /var/tmp/private-tree/gradlew\n"
                 "artifact file:///var/tmp/private-tree/output.txt\n"
                 f"config={home}secret; script=~/bin/runner\n"
                 "Windows C:\\Users\\example\\script.py\n"
                 "contact=example@example.test")
        space.event("needs_a_person", task="T1", step="build", why=words)
        stood_down(space, 78, "nothing startable")
        draft = next((space.root / "issues").glob("*.md")).read_text()
        for value in (session, "example-account", "private-tree", home, "~/bin", "file://",
                      "C:\\Users", "example@example.test"):
            self.assertNotIn(value, draft)

    def test_a_new_run_keeps_history_and_can_record_the_card_again(self):
        _, _, space = loop_for(task(status="rejected"), Fakes())
        for _ in range(2):
            space.event("driver_started")
            space.event("failed", task="T1", step="gate", why="FAIL: same assertion")
            stood_down(space, 78, "nothing startable")
        drafts = list((space.root / "issues").glob("*.md"))
        self.assertEqual(1, len(drafts))
        body = drafts[0].read_text()
        self.assertIn("Run: 1", body)
        self.assertIn("Run: 2", body)
        self.assertEqual(2, body.count("## Card T1"))
