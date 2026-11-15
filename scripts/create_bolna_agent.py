#!/usr/bin/env python
"""Create a new Bolna agent from the current one, dated today.

The old agent is left untouched. The clone keeps the same voice stack, tools,
webhook and prompts, so only the name and creation date differ.

Usage:
    .venv/bin/python scripts/create_bolna_agent.py "Bhakti Hospital Assistant"
"""

import sys
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings  # noqa: E402

TIMEOUT = 60.0


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "Bhakti Hospital Assistant"
    headers = {
        "Authorization": f"Bearer {settings.bolna_api_key}",
        "Content-Type": "application/json",
    }
    base = settings.bolna_base_url.rstrip("/")

    with httpx.Client(timeout=TIMEOUT) as client:
        source = client.get(f"{base}/agent/{settings.bolna_agent_id}", headers=headers)
        source.raise_for_status()
        old = source.json()

        tasks = [
            {
                "task_type": task.get("task_type", "conversation"),
                "toolchain": task.get("toolchain"),
                "task_config": task.get("task_config"),
                "tools_config": task.get("tools_config"),
            }
            for task in old.get("tasks", [])
        ]

        payload = {
            "agent_config": {
                "agent_name": name,
                "agent_welcome_message": (
                    "Hello, this is Bhakti from Bhaktivedanta Hospital. "
                    "How may I help you today?"
                ),
                "agent_type": old.get("agent_type") or "other",
                "webhook_url": old.get("webhook_url"),
                "call_summary_enabled": bool(old.get("call_summary_enabled")),
                "tasks": tasks,
            },
            "agent_prompts": old.get("agent_prompts"),
        }

        created = client.post(f"{base}/v2/agent", headers=headers, json=payload)
        if created.status_code >= 400:
            print(f"Create failed ({created.status_code}): {created.text}", file=sys.stderr)
            return 1

        body = created.json()
        agent_id = body.get("agent_id") or body.get("id")
        if not agent_id:
            print(f"Unexpected response: {body}", file=sys.stderr)
            return 1

        verify = client.get(f"{base}/agent/{agent_id}", headers=headers)
        verify.raise_for_status()
        fresh = verify.json()

    print(f"agent_id: {agent_id}")
    print(f"name: {fresh.get('agent_name')}")
    print(f"created_at: {fresh.get('created_at')}")
    print(f"webhook: {fresh.get('webhook_url')}")
    tools = (fresh.get("tasks") or [{}])[0].get("tools_config", {}).get("api_tools") or {}
    print(f"tools: {', '.join(sorted((tools.get('tools_params') or {}).keys()))}")
    print()
    print("Now put this in .env:")
    print(f"BOLNA_AGENT_ID={agent_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
