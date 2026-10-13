"""The one place the watch skill names a hosted model.

Every script names a transcription model by the role below; only this file says which
provider model plays it today, so an upgrade is one edit here. Groq is preferred (cheaper
and faster); OpenAI is the fallback.

check-hosted-models-are-named-only-in-the-mapping-file (claude-hermes-setup) fails when a
hosted model ID is written anywhere else in this repository.
"""

GROQ_TRANSCRIPTION_ROLE = "hosted-groq-transcription-model"
OPENAI_TRANSCRIPTION_ROLE = "hosted-openai-transcription-model"

HOSTED_MODEL_ROLES = {
    GROQ_TRANSCRIPTION_ROLE: {"provider": "groq", "model_id": "whisper-large-v3"},
    OPENAI_TRANSCRIPTION_ROLE: {"provider": "openai", "model_id": "whisper-1"},
}


def model_id_for_role(role: str) -> str:
    return HOSTED_MODEL_ROLES[role]["model_id"]
