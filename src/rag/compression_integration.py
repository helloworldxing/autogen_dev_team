"""Integration layer for message compression in the multi-agent system.

This module provides seamless integration between the message compression
system and the existing AutoGen-based coordinator architecture.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional, Set

from src.rag.message_compressor import (
    CompressionLevel,
    CompressionMetrics,
    CompressionStats,
    ContentTypeDetector,
    CoordinatorMessageFilter,
    MessageCompressor,
    create_compressor,
)


class CompressionConfig:
    """Configuration for message compression."""

    ENABLED = os.getenv("COMPRESSION_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    LEVEL = os.getenv("COMPRESSION_LEVEL", "moderate").strip().lower()

    PRESERVE_STRUCTURE = os.getenv("COMPRESSION_PRESERVE_STRUCTURE", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    MAX_HISTORY_MESSAGES = int(os.getenv("COMPRESSION_MAX_HISTORY", "10"))

    ENABLE_DEDUPLICATION = os.getenv("COMPRESSION_DEDUP", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    ENABLE_HISTORY_COMPRESSION = os.getenv("COMPRESSION_HISTORY", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    HISTORY_COMPRESSION_STRATEGY = os.getenv("COMPRESSION_HISTORY_STRATEGY", "hybrid").strip().lower()


class CompressedGroupChatManager:
    """Group chat manager with integrated message compression.

    This wrapper intercepts messages in the group chat and applies
    compression to reduce communication overhead while preserving
    essential information.
    """

    def __init__(
        self,
        base_manager: Any,
        compressor: Optional[MessageCompressor] = None,
        config: Optional[CompressionConfig] = None,
    ):
        self.base_manager = base_manager
        self.config = config or CompressionConfig()
        self.compressor = compressor or create_compressor(
            level=self.config.LEVEL,
            preserve_structure=self.config.PRESERVE_STRUCTURE,
        )
        self.coordinator_filter = CoordinatorMessageFilter(self.compressor)
        self._message_count = 0
        self._total_original_bytes = 0
        self._total_compressed_bytes = 0
        self._enabled = self.config.ENABLED

    def __getattr__(self, name):
        """Delegate missing methods to the base manager."""
        if self.base_manager:
            return getattr(self.base_manager, name)
        raise AttributeError(f"{self.__class__.__name__} object has no attribute '{name}'")

    @property
    def stats(self) -> CompressionStats:
        """Get compression statistics."""
        return self.compressor.get_stats()

    def process_message_for_delivery(
        self,
        message: Dict[str, Any],
        sender: str,
        receiver: str,
    ) -> Dict[str, Any]:
        """Process a message before delivery, applying compression if enabled."""
        if not self._enabled:
            return message

        self._message_count += 1
        original_content = message.get("content", "")

        if isinstance(original_content, str):
            self._total_original_bytes += len(original_content)

        processed = self.compressor.compress_message_dict(message)

        if self._enabled and isinstance(original_content, str):
            compressed_content = processed.get("content", "")
            if isinstance(compressed_content, str):
                self._total_compressed_bytes += len(compressed_content)

        return processed

    def should_deliver_message(
        self,
        message: Dict[str, Any],
        sender: str,
        receiver: str,
    ) -> bool:
        """Determine if a message should be delivered to the receiver."""
        if not self._enabled:
            return True

        content = message.get("content", "")

        if self.config.ENABLE_DEDUPLICATION and self.compressor.is_duplicate(content):
            return False

        if receiver == "Coordinator" and not self.coordinator_filter.should_forward_to_coordinator(
            message, sender
        ):
            return False

        return True

    def compress_conversation_history(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Compress conversation history to reduce context size."""
        if not self._enabled or not self.config.ENABLE_HISTORY_COMPRESSION:
            return messages

        return self.compressor.compress_history(
            messages,
            strategy=self.config.HISTORY_COMPRESSION_STRATEGY,
        )

    def get_compression_report(self) -> Dict[str, Any]:
        """Generate a compression effectiveness report."""
        stats = self.compressor.get_stats()
        report = stats.to_dict()
        report["message_count"] = self._message_count
        report["total_original_bytes"] = self._total_original_bytes
        report["total_compressed_bytes"] = self._total_compressed_bytes
        report["overall_bytes_ratio"] = (
            1.0 - (self._total_compressed_bytes / max(1, self._total_original_bytes))
            if self._total_original_bytes > 0
            else 0.0
        )
        report["enabled"] = self._enabled
        report["config"] = {
            "level": self.config.LEVEL,
            "preserve_structure": self.config.PRESERVE_STRUCTURE,
            "max_history_messages": self.config.MAX_HISTORY_MESSAGES,
            "enable_deduplication": self.config.ENABLE_DEDUPLICATION,
            "enable_history_compression": self.config.ENABLE_HISTORY_COMPRESSION,
            "history_compression_strategy": self.config.HISTORY_COMPRESSION_STRATEGY,
        }
        return report

    def reset_stats(self) -> None:
        """Reset compression statistics."""
        self.compressor.reset_stats()
        self._message_count = 0
        self._total_original_bytes = 0
        self._total_compressed_bytes = 0


class CoordinatorCompressionMixin:
    """Mixin class to add compression capabilities to the Coordinator agent.

    This mixin provides methods to wrap message processing with
    compression, reducing communication overhead while maintaining
    the coordinator's role in workflow management.
    """

    def __init__(
        self,
        compression_level: str = "moderate",
        **kwargs,
    ):
        self.compression_enabled = CompressionConfig.ENABLED
        self.compression_level = compression_level
        self.compressor = create_compressor(level=compression_level)
        self.coordinator_filter = CoordinatorMessageFilter(self.compressor)
        self._init_compression_metrics()

    def _init_compression_metrics(self) -> None:
        """Initialize compression metrics tracking."""
        self._compression_stats: Dict[str, Any] = {
            "messages_compressed": 0,
            "bytes_saved": 0,
            "compression_ratio": 0.0,
        }

    def compress_outgoing_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Compress an outgoing coordinator message."""
        if not self.compression_enabled:
            return message

        compressed = self.compressor.compress_message_dict(message)

        if compressed.get("_compression_applied"):
            self._compression_stats["messages_compressed"] += 1
            original_len = message.get("content", "") if isinstance(message.get("content"), str) else 0
            compressed_len = len(compressed.get("content", ""))
            if original_len > 0:
                self._compression_stats["bytes_saved"] += original_len - compressed_len

        return compressed

    def filter_incoming_for_coordinator(
        self,
        message: Dict[str, Any],
        sender: str,
    ) -> bool:
        """Filter incoming messages to determine if coordinator should process them."""
        if not self.compression_enabled:
            return True

        return self.coordinator_filter.should_forward_to_coordinator(message, sender)

    def get_compression_stats(self) -> Dict[str, Any]:
        """Get current compression statistics."""
        stats = self.compressor.get_stats()
        self._compression_stats["compression_ratio"] = stats.get_overall_ratio()
        return {
            **self._compression_stats,
            "detailed_stats": stats.to_dict(),
        }


def create_compressed_coordinator_wrapper(
    base_agent: Any,
    compression_level: str = "moderate",
) -> CoordinatorCompressionMixin:
    """Factory function to wrap a coordinator agent with compression capabilities.

    Args:
        base_agent: The original coordinator agent to wrap
        compression_level: Compression level - "none", "light", "moderate", "aggressive"

    Returns:
        Coordinator agent with compression mixin capabilities
    """
    mixin = CoordinatorCompressionMixin(compression_level=compression_level)

    original_generate_reply = base_agent.generate_reply

    def compressed_generate_reply(self, messages=None, sender=None, **kwargs):
        if messages and compression_level != "none":
            processed_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    compressed_msg = mixin.compress_outgoing_message(msg)
                    processed_messages.append(compressed_msg)
                else:
                    processed_messages.append(msg)
            messages = processed_messages

        return original_generate_reply(messages=messages, sender=sender, **kwargs)

    base_agent.generate_reply = compressed_generate_reply

    return mixin


class MessageRouter:
    """Router with compression support for directing messages between agents."""

    def __init__(
        self,
        compressor: Optional[MessageCompressor] = None,
        enable_routing_compression: bool = True,
    ):
        self.compressor = compressor or create_compressor()
        self.enable_routing_compression = enable_routing_compression
        self._routed_messages: int = 0
        self._filtered_messages: int = 0

    def route_message(
        self,
        message: Dict[str, Any],
        sender: str,
        receiver: str,
    ) -> Optional[Dict[str, Any]]:
        """Route a message with optional compression."""
        self._routed_messages += 1

        if not self.enable_routing_compression:
            return message

        content = message.get("content", "")
        if isinstance(content, str) and self.compressor.is_duplicate(content):
            self._filtered_messages += 1
            return None

        compressed = self.compressor.compress_message_dict(message)

        return compressed

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        total = self._routed_messages
        return {
            "total_routed": total,
            "total_filtered": self._filtered_messages,
            "filter_rate": (
                self._filtered_messages / total if total > 0 else 0.0
            ),
        }


def patch_group_chat_for_compression(
    groupchat_class: type,
    compression_config: Optional[CompressionConfig] = None,
) -> None:
    """Monkey-patch the GroupChat class to add compression support.

    This function modifies the GroupChat behavior to intercept and
    compress messages before they are added to the message list.
    """
    config = compression_config or CompressionConfig()

    if not config.ENABLED:
        return

    compressor = create_compressor(
        level=config.LEVEL,
        preserve_structure=config.PRESERVE_STRUCTURE,
    )

    original_append = getattr(groupchat_class, 'append', None)

    def compressed_append(self, message, **kwargs):
        if isinstance(message, dict) and config.ENABLED:
            compressed_msg = compressor.compress_message_dict(message)
            message["_compressed"] = compressed_msg.get("_compression_applied", False)
            return original_append(message, **kwargs) if original_append else None
        return original_append(message, **kwargs) if original_append else None

    if original_append:
        groupchat_class.append = compressed_append
