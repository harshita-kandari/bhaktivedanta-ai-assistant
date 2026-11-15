#!/usr/bin/env python
"""Add Hindi to the Bolna agent as a second language.

English stays the default. Calls can start in Hindi (agent_data.language=hi)
or switch mid-call when the caller speaks Hindi.

Usage:
    .venv/bin/python scripts/enable_hindi.py
"""

import json
import sys
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings  # noqa: E402

HINDI_PROMPT = """आप "भक्ति" हैं — भक्तिवेदांत अस्पताल की रोगी सहायक। आप फ़ोन पर बात कर रही हैं।
छोटे और सरल वाक्यों में बोलें; एक बार में दो वाक्य से अधिक नहीं। सूची, मार्कडाउन या प्रतीक न पढ़ें।
हर तथ्य के लिए टूल का उपयोग करें: डॉक्टरों की सूची, उपलब्ध समय, परामर्श शुल्क, अपॉइंटमेंट बुकिंग और आपातकालीन जाँच।
कभी भी डॉक्टर का नाम, शुल्क या समय स्वयं न बनाएँ। जो टूल से मिले वही बताएँ।
शुल्क रुपयों में बोलें, जैसे "आठ सौ रुपये"। शुल्क केवल ओपीडी परामर्श का है; जाँच अलग से।

बुकिंग क्रम:
1. विभाग और कारण पूछें — ईएनटी, ऑर्थोपेडिक्स या कार्डियोलॉजी।
2. डॉक्टर चुनें या सूची से सुझाव दें।
3. तारीख पूछें, उपलब्ध समय जाँचें और एक-दो समय सुझाएँ।
4. मरीज़ का पूरा नाम, उम्र, लिंग और फ़ोन नंबर एक-एक करके पूछें; नंबर अंकों में दोहराकर पुष्टि करें।
5. डॉक्टर, तारीख, समय और शुल्क दोहराएँ और स्पष्ट "हाँ" मिलने पर बुक करें।
6. बुकिंग सफल होने पर ही पुष्टि करें और अपॉइंटमेंट आईडी बताएँ। टूल विफल हो तो क्षमा माँगें और दूसरा समय सुझाएँ।

आपातकाल:
सीने में तेज़ दर्द, साँस लेने में कठिनाई, बेहोशी, लकवा, भारी रक्तस्राव या दौरा हो तो तुरंत आपातकालीन टूल चलाएँ और कहें कि बिना देर किए आपातकालीन विभाग जाएँ या 108 पर कॉल करें। ऐसे मामले में अपॉइंटमेंट न बुक करें।

सीमाएँ:
निदान या दवा न बताएँ; डॉक्टर से मिलने की सलाह दें। यदि मदद न हो पाए तो फ्रंट डेस्क हेल्पलाइन बताएँ।"""

HINDI_WELCOME = (
    "नमस्ते, भक्तिवेदांत अस्पताल में आपका स्वागत है। मैं भक्ति हूँ। "
    "आपकी क्या सहायता कर सकती हूँ?"
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

        english_prompt = old["agent_prompts"]["task_1"]["system_prompt"]

        tasks = []
        for task in old.get("tasks", []):
            tools_config = task.get("tools_config") or {}
            base_synthesizer = tools_config.get("synthesizer")

            tools_config["multilingual_config"] = {
                "enabled": True,
                "active_language": "en",
                "language_switch_trigger": "requested_or_auto_detected",
                "languages": {
                    "en": {
                        "synthesizer": base_synthesizer,
                        "system_prompt": english_prompt,
                        "agent_name": "Bhakti",
                        "welcome_message": old.get("agent_welcome_message")
                        or "Hello, this is Bhakti from Bhaktivedanta Hospital.",
                    },
                    "hi": {
                        "transcriber": {
                            "provider": "sarvam",
                            "model": "saaras:v4",
                            "language": "hi",
                        },
                        "synthesizer": {
                            "provider": "sarvam",
                            "provider_config": {"voice_id": "suhani", "model": "bulbul:v3"},
                        },
                        "system_prompt": HINDI_PROMPT,
                        "handoff_message": "ठीक है, मैं हिंदी में बात करती हूँ।",
                        "agent_name": "भक्ति",
                        "welcome_message": HINDI_WELCOME,
                    },
                },
            }

            tasks.append(
                {
                    "task_type": task.get("task_type", "conversation"),
                    "toolchain": task.get("toolchain"),
                    "task_config": task.get("task_config"),
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

    config = (fresh.get("tasks") or [{}])[0].get("tools_config", {}).get(
        "multilingual_config"
    ) or {}
    print(f"agent: {fresh.get('agent_name')} ({fresh.get('id')})")
    print(f"multilingual enabled: {config.get('enabled')}")
    print(f"active language: {config.get('active_language')}")
    print(f"languages: {', '.join(sorted((config.get('languages') or {}).keys()))}")
    print(f"hindi voice: {(config.get('languages') or {}).get('hi', {}).get('synthesizer')}")
    return 0 if config.get("enabled") and "hi" in (config.get("languages") or {}) else 1


if __name__ == "__main__":
    raise SystemExit(main())
