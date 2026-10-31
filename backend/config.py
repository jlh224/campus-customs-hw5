"""Model, gateway, paths, and token limits for the Campus Customs agent team.

Every agent uses the same model, gpt-6-luna, through the Portkey gateway with
PORTKEY_API_KEY. The model name is fixed here on purpose (no env override),
so no other model can slip into a run.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"
OUTPUT_DIR = ROOT / "output"
AUDIT_PATH = OUTPUT_DIR / "audit_trail.json"

load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")  # course-folder .env, if the project one is missing

# ---------- Model (the only one allowed) ----------
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
BOSS_EFFORT = "medium"  # the Boss makes the final calls
SPECIALIST_EFFORT = "low"  # specialists do focused lookups; lower effort = fewer tokens

# ---------- Token and loop limits ----------
MAX_MODEL_REQUESTS_PER_RUN = 10  # model calls one agent may make for one task (an owner coordinating 2 teammates needs ~8)
MAX_TOOL_CALLS_PER_RUN = 14  # tool calls one agent may make for one task
MAX_DELEGATION_DEPTH = 3  # Boss -> A -> B -> C, no deeper
MAX_DELEGATIONS_PER_TICKET = 8  # total handoffs across the whole ticket
TICKET_TOKEN_BUDGET = 200_000  # input + output tokens across all agents on one ticket
TOOL_RESULT_CHARS = 3_000  # longer tool results are cut before going back to the model
AUDIT_PREVIEW_CHARS = 1_500  # text kept per field in the audit trail
MODEL_TIMEOUT_SECONDS = 40  # one model call; normal calls take 1-5 s
MODEL_MAX_RETRIES = 2  # retry a timed-out or failed call before giving up


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Add it to HW5/.env (see .env.example).")
    return key


_client: AsyncOpenAI | None = None


def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna over Portkey (OpenAI Responses API)."""
    global _client
    if _client is None:
        key = require_api_key()
        _client = AsyncOpenAI(
            api_key=key,
            base_url=PORTKEY_BASE_URL,
            default_headers={"x-portkey-api-key": key, "x-portkey-provider": "openai"},
            timeout=MODEL_TIMEOUT_SECONDS,  # an occasional request hangs at the gateway; don't wait forever
            max_retries=MODEL_MAX_RETRIES,
        )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=_client))


def settings(effort: str) -> OpenAIResponsesModelSettings:
    return OpenAIResponsesModelSettings(openai_reasoning_effort=effort)


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()
