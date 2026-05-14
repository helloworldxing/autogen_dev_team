"""Streaming print hook with Mongo persistence."""

from __future__ import annotations

import hashlib
import sys
from typing import Set

import autogen

from src.app.delivery import sanitize_terminal_text
from src.persistence.mongo_logger import MongoConversationLogger

_SEEN_MESSAGE_HASHES: Set[str] = set()


def enable_streaming_with_mongo_logging(
    *,
    session_id: str,
    mongo_logger: MongoConversationLogger,
    stream_enabled: bool = True,
) -> None:
    if getattr(autogen.ConversableAgent, "_streaming_mongo_patch_applied", False):
        return

    original_print = autogen.ConversableAgent._print_received_message

    def streaming_print_received_message(self, message, sender=None, **kwargs):  # type: ignore[override]
        if isinstance(message, dict):
            content = message.get("content", "")
        else:
            content = message

        if isinstance(content, str) and content.strip():
            cleaned_for_terminal = sanitize_terminal_text(content)
            sender_name = getattr(sender, "name", "unknown")
            receiver_name = getattr(self, "name", "unknown")
            dedupe_key = (
                f"{sender_name}->{receiver_name}:{cleaned_for_terminal.strip()}"
            )
            dedupe_hash = hashlib.sha1(
                dedupe_key.encode("utf-8", errors="ignore")
            ).hexdigest()

            if dedupe_hash in _SEEN_MESSAGE_HASHES:
                return
            _SEEN_MESSAGE_HASHES.add(dedupe_hash)

            if stream_enabled:
                sys.stdout.write("\n" + "▌ ")
                sys.stdout.flush()
                for char in cleaned_for_terminal:
                    sys.stdout.write(char)
                    sys.stdout.flush()
                sys.stdout.write("\n")
                sys.stdout.flush()
            else:
                original_print(
                    self, {"content": cleaned_for_terminal}, sender, **kwargs
                )

            mongo_logger.log_message(
                session_id=session_id,
                receiver=receiver_name,
                sender=sender_name,
                content=content,
                raw_message=message,
            )
            return

        return original_print(self, message, sender, **kwargs)

    autogen.ConversableAgent._print_received_message = streaming_print_received_message
    autogen.ConversableAgent._streaming_mongo_patch_applied = True


__all__ = ["enable_streaming_with_mongo_logging"]
