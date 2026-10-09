"""Tests for resolving the research library /watch files reports into."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import research_library  # noqa: E402
import setup  # noqa: E402
from research_library import RESEARCH_LIBRARY_SETTING, resolve_research_library_directory  # noqa: E402


class TestResolveResearchLibraryDirectory(unittest.TestCase):

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.missing_config_file = self.root / "no-such-config" / ".env"
        environment_without_setting = {
            k: v for k, v in os.environ.items() if k != RESEARCH_LIBRARY_SETTING
        }
        patches = [
            mock.patch.dict(os.environ, environment_without_setting, clear=True),
            mock.patch.object(setup, "CONFIG_FILE", self.missing_config_file),
            mock.patch.object(setup, "read_api_key_from_keychain", return_value=None),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.addCleanup(self.temporary_directory.cleanup)

    def _make_library(self) -> Path:
        library = self.root / "research"
        (library / "wiki").mkdir(parents=True)
        (library / "wiki" / "SCHEMA.md").write_text("---\ntype: Schema\n---\n", encoding="utf-8")
        return library

    def test_unset_setting_returns_none(self):
        self.assertIsNone(resolve_research_library_directory())

    def test_configured_library_with_schema_is_returned(self):
        library = self._make_library()
        with mock.patch.dict(os.environ, {RESEARCH_LIBRARY_SETTING: str(library)}):
            self.assertEqual(resolve_research_library_directory(), library)

    def test_configured_directory_without_wiki_schema_returns_none(self):
        bare_directory = self.root / "not-a-library"
        bare_directory.mkdir()
        with mock.patch.dict(os.environ, {RESEARCH_LIBRARY_SETTING: str(bare_directory)}):
            self.assertIsNone(resolve_research_library_directory())

    def test_setting_is_read_from_the_config_file(self):
        library = self._make_library()
        config_file = self.root / ".env"
        config_file.write_text(f"GROQ_API_KEY=\n{RESEARCH_LIBRARY_SETTING}={library}\n", encoding="utf-8")
        config_file.chmod(0o600)
        with mock.patch.object(setup, "CONFIG_FILE", config_file):
            self.assertEqual(resolve_research_library_directory(), library)

    def test_command_exits_nonzero_when_unconfigured(self):
        with mock.patch.object(research_library.sys, "stderr"):
            self.assertEqual(research_library.main(), 1)


if __name__ == "__main__":
    unittest.main()
