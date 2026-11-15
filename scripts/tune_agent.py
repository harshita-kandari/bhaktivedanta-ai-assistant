#!/usr/bin/env python
"""Tune the Bolna agent for smoother phone conversations.

- wait a little longer before deciding the caller finished (fewer cut-offs)
- bias speech recognition towards hospital vocabulary
- stop guessing the language from noisy audio (switch only when asked)
- shorter replies, shorter handoff, fewer repeated questions

Usage:
    .venv/bin/python scripts/tune_agent.py
"""

import sys
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings  # noqa: E402

KEYWORDS = (
    "Bhaktivedanta, ENT, Orthopedics, Cardiology, "
    "Dr. Rajesh Sharma, Dr. Anita Desai, appointment, OPD"
)


def main() -> int:
    headers = {
        "Authorization": f"Bearer {settings.bolna_api_key}",
        "Content-Type": "application/json",
    }
    base = settings.bolna_base_url.rstrip("/")

    with httpx.Client(timeout=60.0) as client:
        source = client.get(f"{base}/agent/{settings.bolna_agent_id}", headers=headers)
        source.raise_for_status()
        old = source.json()

        tasks = []
        for task in old.get("tasks", []):
            tools_config = task.get("tools_config") or {}
            task_config = task.get("task_config") or {}

            transcriber = tools_config.get("transcriber") or {}
            transcriber["endpointing"] = 500
            transcriber["keywords"] = KEYWORDS
            tools_config["transcriber"] = transcriber

            llm_agent = tools_config.get("llm_agent") or {}
            llm_config = llm_agent.get("llm_config") or {}
            llm_config["max_tokens"] = 400
            llm_agent["llm_config"] = llm_config
            tools_config["llm_agent"] = llm_agent

            multilingual = tools_config.get("multilingual_config") or {}
            if multilingual.get("enabled"):
                multilingual["language_switch_trigger"] = "caller_requested"
                hindi = (multilingual.get("languages") or {}).get("hi") or {}
                hindi_transcriber = hindi.get("transcriber") or {}
                hindi_transcriber["endpointing"] = 500
                hindi["transcriber"] = hindi_transcriber
                hindi["handoff_message"] = "ठीक है, हिंदी में बात करते हैं।"
                multilingual["languages"]["hi"] = hindi
            tools_config["multilingual_config"] = multilingual

            task_config["number_of_words_for_interruption"] = 3
            task_config["interruption_backoff_period"] = 800
            task_config["hangup_after_silence"] = 12
            task_config["call_terminate"] = 240

            tasks.append(
                {
                    "task_type": task.get("task_type", "conversation"),
                    "toolchain": task.get("toolchain"),
                    "task_config": task_config,
                    "tools_config": tools_config,
                }
            )

        payload = {
            "agent_config": {
                "agent_name": old.get("agent_name"),
                "agent_welcome_message": old.get("agent_welcome_message"),
                "agent_type": old.get("agent_type") or "other",
                "webhook_url": old.get("webhook_url"),
                "call_summary_enabled": bool(old.get("call_summary_enabled")),
                "tasks": tasks,
            },
            "agent_prompts": old.get("agent_prompts"),
        }

        updated = client.put(
            f"{base}/v2/agent/{settings.bolna_agent_id}", headers=headers, json=payload
        )
        if updated.status_code >= 400:
            print(f"Update failed ({updated.status_code}): {updated.text}", file=sys.stderr)
            return 1

        verify = client.get(f"{base}/agent/{settings.bolna_agent_id}", headers=headers)
        verify.raise_for_status()
        fresh = verify.json()

    task = (fresh.get("tasks") or [{}])[0]
    transcriber = task["tools_config"]["transcriber"]
    config = task.get("task_config", {})
    multilingual = task["tools_config"].get("multilingual_config") or {}

    print(f"endpointing: {transcriber.get('endpointing')}")
    print(f"keywords: {transcriber.get('keywords')}")
    print(f"interruption words: {config.get('number_of_words_for_interruption')}")
    print(f"language trigger: {multilingual.get('language_switch_trigger')}")
    print(f"max tokens: {task['tools_config']['llm_agent']['llm_config'].get('max_tokens')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
