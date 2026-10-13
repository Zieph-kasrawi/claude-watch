"""Transcription models are named only in scripts/hosted_model_roles.py."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import whisper  # noqa: E402
from hosted_model_roles import (  # noqa: E402
    GROQ_TRANSCRIPTION_ROLE,
    HOSTED_MODEL_ROLES,
    OPENAI_TRANSCRIPTION_ROLE,
    model_id_for_role,
)


class TranscriptionModelsComeFromTheirRoles(unittest.TestCase):
    def test_each_provider_uses_its_role_model(self):
        self.assertEqual(whisper.GROQ_MODEL, model_id_for_role(GROQ_TRANSCRIPTION_ROLE))
        self.assertEqual(whisper.OPENAI_MODEL, model_id_for_role(OPENAI_TRANSCRIPTION_ROLE))

    def test_the_transcription_script_writes_no_model_id_itself(self):
        source = (SCRIPTS / "whisper.py").read_text(encoding="utf-8")
        for model in HOSTED_MODEL_ROLES.values():
            self.assertNotIn(model["model_id"], source)


if __name__ == "__main__":
    unittest.main()
