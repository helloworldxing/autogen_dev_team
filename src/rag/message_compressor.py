"""Message compression module for multi-agent coordination.

This module provides intelligent message compression to reduce
communication overhead while preserving essential information.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class CompressionLevel(Enum):
    """Compression level presets."""
    NONE = 0
    LIGHT = 1
    MODERATE = 2
    AGGRESSIVE = 3


@dataclass
class CompressionMetrics:
    """Metrics for measuring compression effectiveness."""
    original_length: int = 0
    compressed_length: int = 0
    compression_ratio: float = 0.0
    processing_time_ms: float = 0.0
    content_type: str = "unknown"

    def compute_ratio(self) -> float:
        if self.original_length == 0:
            return 0.0
        self.compression_ratio = 1.0 - (self.compressed_length / self.original_length)
        return self.compression_ratio


@dataclass
class CompressionStats:
    """Aggregate compression statistics."""
    total_messages: int = 0
    total_original_bytes: int = 0
    total_compressed_bytes: int = 0
    total_processing_time_ms: float = 0.0
    by_content_type: Dict[str, int] = field(default_factory=dict)
    by_content_type_original: Dict[str, int] = field(default_factory=dict)
    by_content_type_compressed: Dict[str, int] = field(default_factory=dict)

    def record(self, metrics: CompressionMetrics) -> None:
        self.total_messages += 1
        self.total_original_bytes += metrics.original_length
        self.total_compressed_bytes += metrics.compressed_length
        self.total_processing_time_ms += metrics.processing_time_ms

        ctype = metrics.content_type
        self.by_content_type[ctype] = self.by_content_type.get(ctype, 0) + 1
        self.by_content_type_original[ctype] = self.by_content_type_original.get(ctype, 0) + metrics.original_length
        self.by_content_type_compressed[ctype] = self.by_content_type_compressed.get(ctype, 0) + metrics.compressed_length

    def get_overall_ratio(self) -> float:
        if self.total_original_bytes == 0:
            return 0.0
        return 1.0 - (self.total_compressed_bytes / self.total_original_bytes)

    def get_avg_processing_time_ms(self) -> float:
        if self.total_messages == 0:
            return 0.0
        return self.total_processing_time_ms / self.total_messages

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_messages": self.total_messages,
            "total_original_bytes": self.total_original_bytes,
            "total_compressed_bytes": self.total_compressed_bytes,
            "overall_compression_ratio": round(self.get_overall_ratio(), 4),
            "avg_processing_time_ms": round(self.get_avg_processing_time_ms(), 3),
            "by_content_type": {
                ctype: {
                    "count": self.by_content_type.get(ctype, 0),
                    "original_bytes": self.by_content_type_original.get(ctype, 0),
                    "compressed_bytes": self.by_content_type_compressed.get(ctype, 0),
                    "ratio": round(
                        1.0 - (self.by_content_type_compressed.get(ctype, 0) / max(1, self.by_content_type_original.get(ctype, 0))),
                        4
                    ),
                }
                for ctype in self.by_content_type.keys()
            },
        }


class ContentTypeDetector:
    """Detect the type of message content for targeted compression."""

    CODE_BLOCK_PATTERN = re.compile(r"```(?:[\w]*)\n[\s\S]*?```", re.MULTILINE)
    MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
    HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
    NUMBERED_LIST_PATTERN = re.compile(r"^\d+\.\s+", re.MULTILINE)
    BULLET_LIST_PATTERN = re.compile(r"^[-*+]\s+", re.MULTILINE)
    HEADER_PATTERN = re.compile(r"^#{1,6}\s+", re.MULTILINE)
    EMPHASIS_PATTERN = re.compile(r"\*\*(.*?)\*\*|__(.*?)__")
    INLINE_CODE_PATTERN = re.compile(r"`([^`]+)`")

    @classmethod
    def detect(cls, content: str) -> str:
        """Detect primary content type."""
        if cls.CODE_BLOCK_PATTERN.search(content):
            return "code"
        if cls.HEADER_PATTERN.search(content) and ("#" in content):
            return "document"
        if content.count("\n") > 10:
            return "conversation"
        if "```" in content or "```python" in content:
            return "code_snippet"
        return "general"


class MessageCompressor:
    """Core message compression engine."""

    def __init__(
        self,
        level: CompressionLevel = CompressionLevel.MODERATE,
        preserve_structure: bool = True,
        max_history_messages: int = 10,
    ):
        self.level = level
        self.preserve_structure = preserve_structure
        self.max_history_messages = max_history_messages
        self.stats = CompressionStats()
        self._seen_hashes: Set[str] = set()

    def compress(self, content: str, content_type: Optional[str] = None) -> str:
        """Compress a single message content."""
        start_time = time.time()

        if not content or not content.strip():
            return content

        original_length = len(content)
        detected_type = content_type or ContentTypeDetector.detect(content)

        compressed = content

        if self.level == CompressionLevel.NONE:
            pass
        elif self.level == CompressionLevel.LIGHT:
            compressed = self._light_compress(compressed)
        elif self.level == CompressionLevel.MODERATE:
            compressed = self._moderate_compress(compressed, detected_type)
        elif self.level == CompressionLevel.AGGRESSIVE:
            compressed = self._aggressive_compress(compressed, detected_type)

        compressed_length = len(compressed)

        metrics = CompressionMetrics(
            original_length=original_length,
            compressed_length=compressed_length,
            content_type=detected_type,
        )
        metrics.compute_ratio()
        metrics.processing_time_ms = (time.time() - start_time) * 1000

        self.stats.record(metrics)

        return compressed

    def _light_compress(self, content: str) -> str:
        """Light compression: remove excessive whitespace and basic formatting."""
        text = re.sub(r"\s+", " ", content)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return text.strip()

    def _moderate_compress(self, content: str, content_type: str) -> str:
        """Moderate compression: remove formatting while preserving structure."""
        text = content

        text = re.sub(r"```(?:python|py)?", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```", "", text)

        text = ContentTypeDetector.EMPHASIS_PATTERN.sub(r"\1\2", text)

        text = ContentTypeDetector.MARKDOWN_LINK_PATTERN.sub(r"\1", text)

        if self.preserve_structure:
            text = re.sub(r"^#{1,6}\s+", "# ", text, flags=re.MULTILINE)
        else:
            text = ContentTypeDetector.HEADER_PATTERN.sub("", text)

        text = re.sub(r"\*\*\s*", "", text)
        text = re.sub(r"\s*\*\*", "", text)
        text = re.sub(r"__\s*", "", text)
        text = re.sub(r"\s*__", "", text)

        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

        return text.strip()

    def _aggressive_compress(self, content: str, content_type: str) -> str:
        """Aggressive compression: maximize reduction while preserving meaning."""
        text = self._moderate_compress(content, content_type)

        text = re.sub(r"^[-*+]\s+", "• ", text, flags=re.MULTILINE)

        text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)

        text = ContentTypeDetector.HTML_TAG_PATTERN.sub("", text)

        guide_patterns = [
            r"以下是[的]?\w+内容[：:]\s*",
            r"请注意[：:]\s*",
            r"重要[：:]\s*",
            r"注意[：:]\s*",
            r"⚠️?\s*",
            r"❗\s*",
            r"✅?\s*",
        ]
        for pattern in guide_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

        return text.strip()

    def compress_message_dict(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Compress a message dictionary while preserving metadata."""
        if not isinstance(message, dict):
            return message

        compressed = message.copy()

        if "content" in compressed:
            original_content = compressed["content"]
            if isinstance(original_content, str):
                compressed["content"] = self.compress(original_content)
                compressed["_compression_applied"] = True
                original_len = len(original_content)
                compressed_len = len(compressed["content"])
                compressed["_compression_ratio"] = (
                    1.0 - (compressed_len / original_len) if original_len > 0 else 0.0
                )
            elif isinstance(original_content, list):
                compressed["content"] = [
                    self.compress(item) if isinstance(item, str) else item
                    for item in original_content
                ]

        return compressed

    def compress_history(
        self,
        messages: List[Dict[str, Any]],
        strategy: str = "last_n",
    ) -> List[Dict[str, Any]]:
        """Compress conversation history to reduce context size.

        Args:
            messages: List of message dictionaries
            strategy: Compression strategy - "last_n", "summarize", "hybrid"

        Returns:
            Compressed message list
        """
        if len(messages) <= self.max_history_messages:
            return messages

        if strategy == "last_n":
            return messages[-self.max_history_messages:]

        elif strategy == "summarize":
            if len(messages) <= 3:
                return messages
            summarized = messages[:1]
            summary_content = self._create_history_summary(messages[1:-1])
            summarized.append({
                "role": "system",
                "content": f"[历史摘要] {summary_content}",
                "_is_summary": True,
            })
            summarized.append(messages[-1])
            return summarized

        elif strategy == "hybrid":
            if len(messages) <= 5:
                return messages
            result = messages[:2]
            middle_summary = self._create_history_summary(messages[2:-2])
            result.append({
                "role": "system",
                "content": f"[中间历史摘要] {middle_summary}",
                "_is_summary": True,
            })
            result.append(messages[-1])
            return result

        return messages

    def _create_history_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Create a summary of historical messages."""
        if not messages:
            return "无历史消息"

        action_counts: Dict[str, int] = {}
        key_content: List[str] = []

        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                content_type = ContentTypeDetector.detect(content)
                action_counts[content_type] = action_counts.get(content_type, 0) + 1

                if content_type == "code" and len(content) > 100:
                    key_content.append("[代码片段]")
                elif len(content) > 200:
                    key_content.append(content[:100] + "...")

        summary_parts = [f"共{len(messages)}条消息"]
        for ctype, count in action_counts.items():
            summary_parts.append(f"{ctype}:{count}")

        if key_content:
            summary_parts.append(" ".join(key_content[:2]))

        return " | ".join(summary_parts)

    def is_duplicate(self, content: str) -> bool:
        """Check if content is a duplicate based on semantic hash."""
        content_hash = hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()
        is_dup = content_hash in self._seen_hashes
        self._seen_hashes.add(content_hash)

        if len(self._seen_hashes) > 10000:
            self._seen_hashes = set(list(self._seen_hashes)[-5000:])

        return is_dup

    def get_stats(self) -> CompressionStats:
        """Get compression statistics."""
        return self.stats

    def reset_stats(self) -> None:
        """Reset compression statistics."""
        self.stats = CompressionStats()
        self._seen_hashes.clear()


class CoordinatorMessageFilter:
    """Specialized filter for coordinator agent messages.

    Reduces redundancy in coordinator-specific message patterns
    while preserving decision-critical information.
    """

    REDUNDANT_PATTERNS = [
        (re.compile(r"以下是我(们)?的\w+[：:]\s*", re.IGNORECASE), ""),
        (re.compile(r"现在[让请]我们[来继续]?\w*[：:]\s*", re.IGNORECASE), ""),
        (re.compile(r"首先[，,]?\s*", re.IGNORECASE), ""),
        (re.compile(r"接下来[，,]?\s*", re.IGNORECASE), ""),
        (re.compile(r"然后[，,]?\s*", re.IGNORECASE), ""),
        (re.compile(r"最后[，,]?\s*", re.IGNORECASE), ""),
        (re.compile(r"好的[，,]?\s*", re.IGNORECASE), ""),
        (re.compile(r"好的[，，]?\s*", re.IGNORECASE), ""),
        (re.compile(r"是的[，,]?\s*", re.IGNORECASE), ""),
        (re.compile(r"我来\w*[：:]\s*", re.IGNORECASE), ""),
        (re.compile(r"请\w*[：:]\s*", re.IGNORECASE), ""),
        (re.compile(r"您想要\w*[：:]\s*", re.IGNORECASE), ""),
        (re.compile(r"用户想要\w*[：:]\s*", re.IGNORECASE), ""),
    ]

    WORKFLOW_INDICATORS = [
        "产品经理",
        "工程师",
        "QA",
        "协调员",
        "PRD",
        "代码",
        "测试",
        "交付",
        "完成",
    ]

    def __init__(self, compressor: MessageCompressor):
        self.compressor = compressor

    def filter_coordinator_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Apply coordinator-specific filtering to a message."""
        if not isinstance(message, dict):
            return message

        filtered = message.copy()

        if "content" in filtered and isinstance(filtered["content"], str):
            original = filtered["content"]

            for pattern, replacement in self.REDUNDANT_PATTERNS:
                original = pattern.sub(replacement, original)

            filtered["content"] = original.strip()
            filtered["_coordinator_filter_applied"] = True

        return filtered

    def should_forward_to_coordinator(
        self,
        message: Dict[str, Any],
        current_speaker: str,
    ) -> bool:
        """Determine if a message should be forwarded to coordinator."""
        content = message.get("content", "")

        if not isinstance(content, str):
            return True

        content_lower = content.lower()

        if any(indicator in content for indicator in self.WORKFLOW_INDICATORS):
            return True

        if len(content) < 50:
            return False

        if "terminate" in content_lower:
            return True

        return True


def create_compressor(
    level: str = "moderate",
    preserve_structure: bool = True,
) -> MessageCompressor:
    """Factory function to create a configured message compressor."""
    level_map = {
        "none": CompressionLevel.NONE,
        "light": CompressionLevel.LIGHT,
        "moderate": CompressionLevel.MODERATE,
        "aggressive": CompressionLevel.AGGRESSIVE,
    }
    return MessageCompressor(
        level=level_map.get(level.lower(), CompressionLevel.MODERATE),
        preserve_structure=preserve_structure,
    )
