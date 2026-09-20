"""The credentials file is refused when group- or other-readable: it holds a
password, and a loose mode leaks it to every local reader."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import alert_email
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 2


class ModeTest(unittest.TestCase):
    def test_a_group_readable_credentials_file_is_refused(self):
        loose = pathlib.Path(tempfile.mkdtemp()) / "smtp.env"
        loose.write_text("SMTP_HOST=h\nSMTP_PORT=465\nSMTP_USER=u\n"
                         "SMTP_PASS=p\nSMTP_FROM=f\nSMTP_TO=t\n", "utf-8")
        loose.chmod(0o664)
        with unittest.mock.patch.object(alert_email, "ENV", loose), \
             self.assertRaises(SystemExit) as caught:
            alert_email.credentials()
        self.assertIn("chmod 600", str(caught.exception))
        loose.chmod(0o600)
        with unittest.mock.patch.object(alert_email, "ENV", loose):
            self.assertEqual("h", alert_email.credentials()["SMTP_HOST"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
