"""Resolve each hosted model role to its provider's newest generally available model.

Founder ruling 2026-10-12: a paid-provider role switches by itself to the newest
generation of the same tier, so no hand-edited model ID goes stale. It never switches to
another tier or another provider, and never onto a preview, beta, experimental or
deprecated model.

A role declares its tier as `same_tier_model_id_pattern`, a model ID with `{version}`
where the generation goes: `claude-sonnet-{version}`, `gpt-{version}`,
`gemini-{version}-flash-image`. `{version}` is numbers joined by `.` or `-`, optionally
followed by a snapshot date; nothing else may differ, so a `-mini` variant is
not in the `gpt-{version}` tier. The role's `model_id` is the seed: the model used until
the first listing succeeds, and whenever no listing has ever succeeded.

The provider's model listing is read at most once per RESOLUTION_REFRESH_INTERVAL_HOURS.
The result is cached in one JSON file per roles file under the state directory, together
with every switch and every failed listing. When a listing fails, the last good model
from the cache (or the seed) is used, a WARNING goes to standard error, and the failure
is stamped in the cache. The daily outdated-model-pin report (claude-hermes-setup) reads
these caches and tells the founder about every switch and every failed listing.

This module uses only the standard library, so it is the same file in every repository
that has a hosted model roles file.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

STATE_DIRECTORY_ENVIRONMENT_VARIABLE = "HOSTED_MODEL_ROLE_STATE_DIRECTORY"
DEFAULT_STATE_DIRECTORY = Path.home() / ".local" / "state" / "hosted-model-role-resolutions"
RESOLUTION_REFRESH_INTERVAL_HOURS = 24
# After a failed listing, the last good model is used without asking again for this long,
# so an outage does not delay every start; the failure stays stamped for the daily report.
RETRY_AFTER_FAILED_LISTING_MINUTES = 60
LISTING_TIMEOUT_SECONDS = 20
# Words providers use for models that are not generally available.
NOT_GENERALLY_AVAILABLE = re.compile(
    r"(?:^|[-_.])(?:preview|beta|alpha|exp|experimental|deprecated)(?:$|[-_.0-9])", re.IGNORECASE
)
# A generation is numbers of one or two digits (`5`, `4-5`, `5.4`). A snapshot date after
# it, written `-20250929`, `-2025-09-29` or `-0709`, is the same generation, never a newer one.
VERSION_SHAPE = (
    r"(?P<version>\d{1,2}(?:[.-]\d{1,2})*)"
    r"(?:-(?P<snapshot>\d{8}|\d{4}-\d{2}-\d{2}|\d{4}))?"
)

ModelLister = Callable[[], list[str]]


class ModelListingError(RuntimeError):
    """The provider's model listing could not be read."""


def same_tier_regex(same_tier_model_id_pattern: str) -> re.Pattern:
    before, separator, after = same_tier_model_id_pattern.partition("{version}")
    if not separator:
        raise ValueError(f"{same_tier_model_id_pattern!r} has no {{version}} placeholder")
    return re.compile(re.escape(before) + VERSION_SHAPE + re.escape(after), re.IGNORECASE)


def newest_generally_available_model_id(
    model_ids: list[str], same_tier_model_id_pattern: str
) -> str | None:
    """The highest generation in the tier; an undated ID beats its own dated snapshot."""
    tier = same_tier_regex(same_tier_model_id_pattern)
    candidates = []
    for model_id in model_ids:
        match = tier.fullmatch(model_id)
        if not match or NOT_GENERALLY_AVAILABLE.search(model_id):
            continue
        generation = tuple(int(part) for part in re.split(r"[.-]", match.group("version")))
        is_undated = match.group("snapshot") is None
        candidates.append((generation, is_undated, match.group("snapshot") or "", model_id))
    return max(candidates)[3] if candidates else None


# Some providers sit behind Cloudflare, which refuses Python's default User-Agent with HTTP
# 403 (Groq did on 2026-10-12), so every listing names its client.
LISTING_USER_AGENT = "hosted-model-role-resolver/1.0 (python-urllib)"


def _get_json(url: str, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": LISTING_USER_AGENT, **headers}
    )
    try:
        with urllib.request.urlopen(request, timeout=LISTING_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise ModelListingError(f"{url}: {exc}") from exc


def anthropic_model_lister(api_base_url: str, api_key: str) -> ModelLister:
    def list_model_ids() -> list[str]:
        model_ids, after_id = [], None
        while True:
            query = "?limit=1000" + (f"&after_id={after_id}" if after_id else "")
            page = _get_json(
                f"{api_base_url}/v1/models{query}",
                {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            )
            model_ids += [model["id"] for model in page.get("data", [])]
            if not page.get("has_more"):
                return model_ids
            after_id = page.get("last_id")

    return list_model_ids


def openai_compatible_model_lister(api_base_url: str, api_key: str) -> ModelLister:
    def list_model_ids() -> list[str]:
        page = _get_json(f"{api_base_url}/models", {"Authorization": f"Bearer {api_key}"})
        return [model["id"] for model in page.get("data", [])]

    return list_model_ids


def google_model_lister(api_base_url: str, api_key: str) -> ModelLister:
    def list_model_ids() -> list[str]:
        model_ids, page_token = [], ""
        while True:
            query = "?pageSize=1000" + (f"&pageToken={page_token}" if page_token else "")
            page = _get_json(f"{api_base_url}/models{query}", {"x-goog-api-key": api_key})
            model_ids += [model["name"].removeprefix("models/") for model in page.get("models", [])]
            page_token = page.get("nextPageToken", "")
            if not page_token:
                return model_ids

    return list_model_ids


MODEL_LISTERS_BY_LISTING_KIND = {
    "anthropic": anthropic_model_lister,
    "openai-compatible": openai_compatible_model_lister,
    "google": google_model_lister,
}


def model_lister(listing_kind: str, api_base_url: str, api_key: str) -> ModelLister:
    if not api_key:

        def no_key() -> list[str]:
            raise ModelListingError("no API key is set for this provider")

        return no_key
    return MODEL_LISTERS_BY_LISTING_KIND[listing_kind](api_base_url.rstrip("/"), api_key)


def state_file_for(roles_file: Path) -> Path:
    directory = Path(
        os.environ.get(STATE_DIRECTORY_ENVIRONMENT_VARIABLE) or DEFAULT_STATE_DIRECTORY
    )
    roles_file = roles_file.resolve()
    digest = hashlib.sha256(str(roles_file).encode()).hexdigest()[:12]
    return directory / f"{roles_file.parent.name}-{digest}.json"


def _read_state(state_file: Path, roles_file: Path) -> dict:
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"roles_file": str(roles_file.resolve()), "roles": {}, "switches": []}


def _write_state(state_file: Path, state: dict) -> None:
    """Best effort: a cache that cannot be written must never stop a model being chosen."""
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=state_file.parent, suffix=".tmp", delete=False
        ) as temporary:
            temporary.write(json.dumps(state, indent=2) + "\n")
        os.replace(temporary.name, state_file)
    except OSError as exc:
        print(
            f"WARNING: could not record hosted model role resolution in {state_file} ({exc}); "
            "the daily model report will not see this resolution",
            file=sys.stderr,
        )


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def resolve_model_id(
    *,
    roles_file: Path,
    role: str,
    provider: str,
    seed_model_id: str,
    same_tier_model_id_pattern: str,
    list_model_ids: ModelLister,
    now: Callable[[], datetime.datetime] | None = None,
) -> str:
    """The model this role should use now; never raises because a listing failed."""
    now = now or _now
    state_file = state_file_for(roles_file)
    state = _read_state(state_file, roles_file)
    record = state["roles"].setdefault(role, {})
    declared = (provider, seed_model_id, same_tier_model_id_pattern)
    remembered = (
        record.get("provider"),
        record.get("seed_model_id"),
        record.get("same_tier_model_id_pattern"),
    )
    if remembered != declared:
        # The role was redeclared (another provider, tier or seed): what was resolved for the
        # old declaration no longer applies, so the new seed stands until the new listing.
        record.clear()
        record.update(provider=provider, seed_model_id=seed_model_id)
    current = record.get("resolved_model_id") or seed_model_id
    checked_at = record.get("listing_succeeded_at")
    if checked_at and now() - datetime.datetime.fromisoformat(checked_at) < datetime.timedelta(
        hours=RESOLUTION_REFRESH_INTERVAL_HOURS
    ):
        return current
    failed_at = record.get("listing_failed_at")
    if failed_at and now() - datetime.datetime.fromisoformat(failed_at) < datetime.timedelta(
        minutes=RETRY_AFTER_FAILED_LISTING_MINUTES
    ):
        return current

    stamp = now().isoformat(timespec="seconds")
    try:
        newest = newest_generally_available_model_id(list_model_ids(), same_tier_model_id_pattern)
    except (ModelListingError, KeyError, TypeError, ValueError) as exc:
        record.update(
            provider=provider,
            same_tier_model_id_pattern=same_tier_model_id_pattern,
            listing_failed_at=stamp,
            listing_error=str(exc),
        )
        _write_state(state_file, state)
        print(
            f"WARNING: could not list {provider}'s models to resolve {role} ({exc}); "
            f"using {current}, the last model that was resolved or seeded",
            file=sys.stderr,
        )
        return current

    record.update(
        provider=provider,
        same_tier_model_id_pattern=same_tier_model_id_pattern,
        listing_succeeded_at=stamp,
        listing_failed_at=None,
        listing_error=None,
    )
    if newest is None:
        record["no_generally_available_model_in_tier"] = True
        newest = current
        print(
            f"WARNING: {provider} lists no generally available {same_tier_model_id_pattern} "
            f"model for {role}; staying on {current}, which the provider may have retired. "
            "Move the role to a tier the provider still serves.",
            file=sys.stderr,
        )
    else:
        record["no_generally_available_model_in_tier"] = False
    if newest != current:
        state["switches"].append(
            {"role": role, "provider": provider, "from": current, "to": newest, "at": stamp}
        )
        print(f"NOTICE: {role} switched from {current} to {newest}", file=sys.stderr)
    record["resolved_model_id"] = newest
    _write_state(state_file, state)
    return newest
