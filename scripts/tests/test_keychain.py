"""Tests for reading Whisper API keys from the macOS Keychain."""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import keychain  # noqa: E402
from keychain import read_api_key_from_keychain  # noqa: E402


def _completed(returncode: int, stdout: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


@mock.patch.object(keychain.shutil, "which", return_value="/usr/bin/security")
@mock.patch.object(keychain.sys, "platform", "darwin")
class TestReadApiKeyFromKeychain(unittest.TestCase):

    def setUp(self):
        read_api_key_from_keychain.cache_clear()

    def test_returns_stored_key_for_its_service(self, _which):
        with mock.patch.object(keychain.subprocess, "run", return_value=_completed(0, "gsk_example\n")) as run:
            self.assertEqual(read_api_key_from_keychain("GROQ_API_KEY"), "gsk_example")
        argv = run.call_args.args[0]
        self.assertEqual(argv[argv.index("-s") + 1], "groq-api-key")

    def test_missing_item_returns_none(self, _which):
        with mock.patch.object(keychain.subprocess, "run", return_value=_completed(44, "")):
            self.assertIsNone(read_api_key_from_keychain("OPENAI_API_KEY"))

    def test_timeout_returns_none_and_warns(self, _which):
        timeout = subprocess.TimeoutExpired(cmd="security", timeout=10)
        with mock.patch.object(keychain.subprocess, "run", side_effect=timeout), \
                mock.patch.object(keychain.sys, "stderr") as stderr:
            self.assertIsNone(read_api_key_from_keychain("GROQ_API_KEY"))
        self.assertIn("groq-api-key", stderr.write.call_args.args[0])

    def test_name_without_a_service_never_calls_security(self, _which):
        with mock.patch.object(keychain.subprocess, "run") as run:
            self.assertIsNone(read_api_key_from_keychain("SETUP_COMPLETE"))
        run.assert_not_called()

    def test_other_platforms_never_call_security(self, _which):
        with mock.patch.object(keychain.sys, "platform", "linux"), \
                mock.patch.object(keychain.subprocess, "run") as run:
            self.assertIsNone(read_api_key_from_keychain("GROQ_API_KEY"))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
