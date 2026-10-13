"""Transcription models are named only in scripts/hosted_model_roles.py, and each role moves
itself to its provider's newest generally available model of the same tier."""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import hosted_model_roles  # noqa: E402
import whisper  # noqa: E402
from hosted_model_roles import (  # noqa: E402
    GROQ_TRANSCRIPTION_ROLE,
    HOSTED_MODEL_ROLES,
    OPENAI_TRANSCRIPTION_ROLE,
    model_id_for_role,
)


def generation(role: str, version: str) -> str:
    return HOSTED_MODEL_ROLES[role]["same_tier_model_id_pattern"].replace("{version}", version)


class TranscriptionModelsComeFromTheirRoles(unittest.TestCase):
    def setUp(self):
        # No test reaches a provider, and each resolves against its own cache.
        state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(state_directory.cleanup)
        patcher = mock.patch.dict(os.environ, {"HOSTED_MODEL_ROLE_STATE_DIRECTORY": state_directory.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def listing(self, model_ids):
        return mock.patch.object(hosted_model_roles, "model_lister",
                                 lambda kind, base_url, api_key: lambda: model_ids)

    def test_each_backend_uses_its_role_model_and_its_providers_endpoint(self):
        for backend, role in (("groq", GROQ_TRANSCRIPTION_ROLE), ("openai", OPENAI_TRANSCRIPTION_ROLE)):
            with self.listing([model_id_for_role(role)]):
                endpoint, model = whisper.transcription_endpoint_and_model(backend, "a-key")
            self.assertEqual(model, model_id_for_role(role))
            provider = hosted_model_roles.HOSTED_MODEL_PROVIDERS[HOSTED_MODEL_ROLES[role]["provider"]]
            self.assertEqual(endpoint, provider["api_base_url"] + "/audio/transcriptions")

    def test_a_newer_generation_is_picked_up_but_never_a_preview_or_another_tier(self):
        listing = [generation(GROQ_TRANSCRIPTION_ROLE, "3"), generation(GROQ_TRANSCRIPTION_ROLE, "4"),
                   generation(GROQ_TRANSCRIPTION_ROLE, "5") + "-preview",
                   generation(GROQ_TRANSCRIPTION_ROLE, "5") + "-turbo"]
        with self.listing(listing):
            _, model = whisper.transcription_endpoint_and_model("groq", "a-key")
        self.assertEqual(model, generation(GROQ_TRANSCRIPTION_ROLE, "4"))

    def test_a_failed_listing_falls_back_to_the_seed_loudly(self):
        def failing(kind, base_url, api_key):
            def list_model_ids():
                raise hosted_model_roles.ModelListingError("connection refused")
            return list_model_ids

        with mock.patch.object(hosted_model_roles, "model_lister", failing), \
                mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            _, model = whisper.transcription_endpoint_and_model("openai", "a-key")
        self.assertEqual(model, model_id_for_role(OPENAI_TRANSCRIPTION_ROLE))
        self.assertIn("WARNING", stderr.getvalue())

    def test_an_unknown_backend_is_refused(self):
        with self.assertRaises(SystemExit):
            whisper.transcription_endpoint_and_model("elsewhere", "a-key")

    def test_the_transcription_script_writes_no_model_id_or_endpoint_itself(self):
        source = (SCRIPTS / "whisper.py").read_text(encoding="utf-8")
        for model in HOSTED_MODEL_ROLES.values():
            self.assertNotIn(model["model_id"], source)
        for provider in hosted_model_roles.HOSTED_MODEL_PROVIDERS.values():
            self.assertNotIn(provider["api_base_url"], source)


if __name__ == "__main__":
    unittest.main()
