from __future__ import annotations

import os
from typing import Set

import autogen

from src.app.artifacts import streaming_printer_factory


import re


def sanitize_terminal_text(content: str) -> str:
    """Sanitize content for terminal display."""
    text = content
    text = text.replace("```python", "")
    text = text.replace("```", "")
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"^\s{0,3}#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def enable_streaming_with_mongo_logging(
    *,
    mongo_logger,
    session_id: str,
    seen_hashes: Set[str],
    stream_enabled: bool,
    on_event=None,
) -> None:
    """Patch AutoGen streaming to log to Mongo and print incrementally."""

    if not hasattr(autogen.ConversableAgent, "_streaming_mongo_original_print"):
        autogen.ConversableAgent._streaming_mongo_original_print = (
            autogen.ConversableAgent._print_received_message
        )

    original_print = autogen.ConversableAgent._streaming_mongo_original_print
    stream_env_enabled = os.getenv("STREAM_PRINT_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    use_stream = stream_enabled and stream_env_enabled

    if not use_stream:

        def passthrough(self, message, sender=None, **kwargs):
            if isinstance(message, dict):
                content = message.get("content", "")
            else:
                content = message

            if isinstance(content, str) and content.strip():
                sender_name = getattr(sender, "name", "unknown")
                receiver_name = getattr(self, "name", "unknown")
                if on_event is not None:
                    try:
                        on_event(
                            {
                                "type": "message",
                                "session_id": session_id,
                                "sender": sender_name,
                                "receiver": receiver_name,
                                "content": sanitize_terminal_text(content),
                            }
                        )
                    except Exception:
                        pass

                mongo_logger.log_message(
                    session_id=session_id,
                    receiver=receiver_name,
                    sender=sender_name,
                    content=content,
                    raw_message=message,
                )
                return

            return original_print(self, message, sender, **kwargs)

        autogen.ConversableAgent._print_received_message = passthrough
        autogen.ConversableAgent._streaming_mongo_patch_applied = True
        return

    patched = streaming_printer_factory(
        mongo_logger,
        session_id,
        seen_hashes,
        original_print,
        on_event=on_event,
    )

    autogen.ConversableAgent._print_received_message = patched
    autogen.ConversableAgent._streaming_mongo_patch_applied = True
