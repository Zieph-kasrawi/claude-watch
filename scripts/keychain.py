#!/usr/bin/env python3
"""Read Whisper API keys from the macOS Keychain.

The Keychain is where /watch expects its keys to live on macOS: they are
stored there with `security add-generic-password` (see SKILL.md Step 0) and
read back here at run time, so a key never sits in a plaintext file or passes
through a chat. On other platforms, or when no Keychain item exists, this
returns None and callers fall back to `~/.config/watch/.env`.

The key value is returned to the caller only — it is never printed or logged.
"""
from __future__ import annotations

import functools
import os
import pwd
import shutil
import subprocess
import sys


# Keychain service name for each environment variable /watch reads.
# `groq-api-key` is the name the rest of the founder's setup already uses for
# the same Groq account key; keep one name per credential.
KEYCHAIN_SERVICE_BY_ENV_VAR = {
    "GROQ_API_KEY": "groq-api-key",
    "OPENAI_API_KEY": "openai-api-key",
}

# `security` exits with this code when the item does not exist.
SECURITY_ITEM_NOT_FOUND_EXIT_CODE = 44


@functools.lru_cache(maxsize=None)
def read_api_key_from_keychain(env_var_name: str) -> str | None:
    """Return the key stored under the Keychain service for `env_var_name`.

    None when not on macOS, when `security` is unavailable, when the name has
    no Keychain service, or when the item is missing. A locked Keychain, a
    refused access prompt or a timeout also returns None, with a warning on
    stderr naming the service so it is not mistaken for a missing key.
    """
    service = KEYCHAIN_SERVICE_BY_ENV_VAR.get(env_var_name)
    if service is None or sys.platform != "darwin" or shutil.which("security") is None:
        return None
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", pwd.getpwuid(os.getuid()).pw_name, "-s", service, "-w"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        _warn_keychain_unreadable(service, type(error).__name__)
        return None
    if result.returncode == SECURITY_ITEM_NOT_FOUND_EXIT_CODE:
        return None
    if result.returncode != 0:
        _warn_keychain_unreadable(service, f"security exited {result.returncode}")
        return None
    value = result.stdout.strip()
    return value or None


def _warn_keychain_unreadable(service: str, reason: str) -> None:
    sys.stderr.write(
        f"[watch] could not read Keychain item {service} ({reason}); "
        "the Keychain may be locked or access was refused\n"
    )
    sys.stderr.flush()
