"""The one place the watch skill names a hosted model.

Every script names a transcription model by the role below; only this file says which
provider model plays it. Groq is preferred (cheaper and faster); OpenAI is the fallback.

Each role declares its tier as `same_tier_model_id_pattern`, and moves itself to its
provider's newest generally available model of that tier (founder ruling 2026-10-12,
auto-switch to newest) through hosted_model_role_resolver.py, the same file every
repository carries. `model_id` is the seed, used until the first listing and whenever a
listing fails. Each role's endpoint comes from its provider below.

check-hosted-models-are-named-only-in-the-mapping-file (claude-hermes-setup) fails when a
hosted model ID is written anywhere else in this repository.
"""

from pathlib import Path

from hosted_model_role_resolver import ModelListingError, model_lister, resolve_model_id  # noqa: F401

ROLES_FILE = Path(__file__).resolve()

GROQ_TRANSCRIPTION_ROLE = "hosted-groq-transcription-model"
OPENAI_TRANSCRIPTION_ROLE = "hosted-openai-transcription-model"

HOSTED_MODEL_PROVIDERS = {
    "groq": {"api_base_url": "https://api.groq.com/openai/v1", "model_listing_kind": "openai-compatible"},
    "openai": {"api_base_url": "https://api.openai.com/v1", "model_listing_kind": "openai-compatible"},
}

HOSTED_MODEL_ROLES = {
    GROQ_TRANSCRIPTION_ROLE: {
        "provider": "groq",
        "model_id": "whisper-large-v3",
        "same_tier_model_id_pattern": "whisper-large-v{version}",
    },
    OPENAI_TRANSCRIPTION_ROLE: {
        "provider": "openai",
        "model_id": "whisper-1",
        "same_tier_model_id_pattern": "whisper-{version}",
    },
}


def model_id_for_role(role: str) -> str:
    """The role's seed model, as written above."""
    return HOSTED_MODEL_ROLES[role]["model_id"]


def provider_for_role(role: str) -> dict:
    return HOSTED_MODEL_PROVIDERS[HOSTED_MODEL_ROLES[role]["provider"]]


def transcription_endpoint_for_role(role: str) -> str:
    return provider_for_role(role)["api_base_url"] + "/audio/transcriptions"


def current_model_id_for_role(role: str, api_key: str) -> str:
    """The provider's newest generally available model of the role's tier, read with the
    provider key the transcription itself uses; never raises because a listing failed."""
    entry, provider = HOSTED_MODEL_ROLES[role], provider_for_role(role)
    return resolve_model_id(
        roles_file=ROLES_FILE,
        role=role,
        provider=entry["provider"],
        seed_model_id=entry["model_id"],
        same_tier_model_id_pattern=entry["same_tier_model_id_pattern"],
        list_model_ids=model_lister(
            provider["model_listing_kind"], provider["api_base_url"], api_key
        ),
    )
