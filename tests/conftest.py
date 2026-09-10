"""Hermetic defaults that prevent developer credentials from altering tests."""

from __future__ import annotations

import os

for _credential_name in (
    "CLUTCH_API_KEY",
    "DATABASE_URL",
    "DIRECT_DATABASE_URL",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "OPENAI_API_KEY",
    "REDIS_URL",
):
    os.environ[_credential_name] = ""
os.environ["CLUTCH_REQUIRE_AUTH"] = "false"
