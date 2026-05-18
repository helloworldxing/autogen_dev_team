"""Tests for message compression system."""

import pytest
import time

from src.rag.message_compressor import (
    CompressionLevel,
    CompressionMetrics,
    CompressionStats,
    ContentTypeDetector,
    CoordinatorMessageFilter,
    MessageCompressor,
    create_compressor,
)


class TestContentTypeDetector:
    """Test content type detection."""

    def test_detect_code(self):
        content = "```python\ndef hello():\n    print('world')\n```"
        assert ContentTypeDetector.detect(content) == "code"

    def test_detect_code_snippet(self):
        content = "Here is some code:\n```python\nprint('hello')\n```"
        assert ContentTypeDetector.detect(content) == "code"

    def test_detect_document(self):
        content = "# Header\n\nSome content\n## Subheader\nMore content"
        assert ContentTypeDetector.detect(content) == "document"

    def test_detect_conversation(self):
        content = "\n".join([f"Line {i}" for i in range(15)])
        assert ContentTypeDetector.detect(content) == "conversation"

    def test_detect_general(self):
        content = "This is a short message"
        assert ContentTypeDetector.detect(content) == "general"


class TestMessageCompressor:
    """Test core message compression."""

    def test_light_compression(self):
        compressor = create_compressor(level="light")
        text = "This   is    a    test\n\n\nwith   extra   whitespace"
        result = compressor.compress(text)
        assert "   " not in result
        assert "\n\n\n" not in result

    def test_moderate_compression(self):
        compressor = create_compressor(level="moderate")
        text = "**Bold text** and __underline text__ with `code`"
        result = compressor.compress(text)
        assert "**" not in result
        assert "__" not in result

    def test_aggressive_compression(self):
        compressor = create_compressor(level="aggressive")
        text = """请注意：这是一个重要内容

重要：请仔细阅读

**粗体文本**应该被处理"""
        result = compressor.compress(text)
        assert "请注意" not in result
        assert "重要：" not in result
        assert "粗体" in result

    def test_preserve_structure_moderate(self):
        compressor = create_compressor(level="moderate", preserve_structure=True)
        text = "# Title\n\n## Section\n\nContent"
        result = compressor.compress(text)
        assert "#" in result

    def test_compress_message_dict(self):
        compressor = create_compressor(level="moderate")
        message = {
            "role": "assistant",
            "content": "**Important** message with `code`",
        }
        result = compressor.compress_message_dict(message)
        assert isinstance(result, dict)
        assert result["role"] == "assistant"
        assert "_compression_applied" in result

    def test_compression_ratio_tracking(self):
        compressor = MessageCompressor(level=CompressionLevel.MODERATE)
        original = "**Bold** text with ```python code ```"
        compressed = compressor.compress(original)
        stats = compressor.get_stats()
        assert stats.total_messages == 1
        assert stats.total_original_bytes == len(original)
        assert stats.total_compressed_bytes == len(compressed)

    def test_deduplication(self):
        compressor = create_compressor(level="moderate")
        content1 = "Same content"
        content2 = "Same content"
        assert not compressor.is_duplicate(content1)
        assert compressor.is_duplicate(content2)

    def test_history_compression_last_n(self):
        compressor = create_compressor(level="moderate")
        messages = [{"content": f"Message {i}"} for i in range(15)]
        result = compressor.compress_history(messages, strategy="last_n")
        assert len(result) <= compressor.max_history_messages

    def test_history_compression_summarize(self):
        compressor = create_compressor(level="moderate")
        messages = [{"content": f"Message {i}"} for i in range(15)]
        result = compressor.compress_history(messages, strategy="summarize")
        assert len(result) < len(messages)
        assert any("_is_summary" in msg for msg in result)

    def test_history_compression_hybrid(self):
        compressor = create_compressor(level="moderate")
        messages = [{"content": f"Message {i}"} for i in range(15)]
        result = compressor.compress_history(messages, strategy="hybrid")
        assert len(result) < len(messages)


class TestCoordinatorMessageFilter:
    """Test coordinator-specific message filtering."""

    def setup_method(self):
        self.compressor = create_compressor(level="moderate")
        self.filter = CoordinatorMessageFilter(self.compressor)

    def test_filter_redundant_patterns(self):
        message = {
            "content": "好的，首先让我们开始工作：请分析这个需求"
        }
        result = self.filter.filter_coordinator_message(message)
        assert "好的" not in result["content"]
        assert "首先" not in result["content"]

    def test_should_forward_with_keyword(self):
        message = {"content": "产品经理已经完成了PRD文档"}
        assert self.filter.should_forward_to_coordinator(message, "Product_Manager")

    def test_should_forward_short_message(self):
        message = {"content": "好的"}
        assert not self.filter.should_forward_to_coordinator(message, "Product_Manager")

    def test_should_forward_terminate(self):
        message = {"content": "TERMINATE - 任务完成"}
        assert self.filter.should_forward_to_coordinator(message, "Product_Manager")


class TestCompressionMetrics:
    """Test compression metrics and statistics."""

    def test_compute_ratio(self):
        metrics = CompressionMetrics(
            original_length=100,
            compressed_length=75,
        )
        ratio = metrics.compute_ratio()
        assert ratio == 0.25

    def test_compute_ratio_zero_original(self):
        metrics = CompressionMetrics(
            original_length=0,
            compressed_length=0,
        )
        ratio = metrics.compute_ratio()
        assert ratio == 0.0

    def test_compression_stats_record(self):
        stats = CompressionStats()
        metrics = CompressionMetrics(
            original_length=100,
            compressed_length=80,
            content_type="code",
            processing_time_ms=5.0,
        )
        metrics.compute_ratio()
        stats.record(metrics)

        assert stats.total_messages == 1
        assert stats.total_original_bytes == 100
        assert stats.total_compressed_bytes == 80

    def test_overall_ratio(self):
        stats = CompressionStats()
        for i in range(5):
            metrics = CompressionMetrics(
                original_length=100,
                compressed_length=70,
                content_type="general",
                processing_time_ms=1.0,
            )
            metrics.compute_ratio()
            stats.record(metrics)

        assert abs(stats.get_overall_ratio() - 0.30) < 0.01

    def test_stats_to_dict(self):
        stats = CompressionStats()
        metrics = CompressionMetrics(
            original_length=200,
            compressed_length=100,
            content_type="document",
            processing_time_ms=10.0,
        )
        metrics.compute_ratio()
        stats.record(metrics)

        result = stats.to_dict()
        assert "total_messages" in result
        assert "overall_compression_ratio" in result
        assert "by_content_type" in result


class TestPerformance:
    """Test performance characteristics."""

    def test_compression_speed(self):
        compressor = create_compressor(level="moderate")
        content = """
        这是一个测试文本，用于验证压缩性能。
        **这是粗体文本** 包含一些 `代码` 和其他格式。
        ```python
        def hello():
            print("world")
        ```
        """ * 10

        start = time.time()
        for _ in range(100):
            compressor.compress(content)
        elapsed = (time.time() - start) * 1000

        assert elapsed < 5000

    def test_large_content_compression(self):
        compressor = create_compressor(level="moderate")
        content = """
        # 大型文档

        ## 章节一

        这是一个很长的内容...

        """ * 100

        result = compressor.compress(content)
        assert len(result) < len(content)
        assert compressor.get_stats().total_original_bytes == len(content)

    def test_repeated_compression_stability(self):
        compressor = create_compressor(level="aggressive")
        content = "Test content " * 50

        results = set()
        for _ in range(10):
            result = compressor.compress(content)
            results.add(result)

        assert len(results) == 1


class TestIntegration:
    """Integration tests for compression with message flow."""

    def test_factory_creates_correct_level(self):
        compressor = create_compressor(level="none")
        assert compressor.level == CompressionLevel.NONE

        compressor = create_compressor(level="light")
        assert compressor.level == CompressionLevel.LIGHT

        compressor = create_compressor(level="moderate")
        assert compressor.level == CompressionLevel.MODERATE

        compressor = create_compressor(level="aggressive")
        assert compressor.level == CompressionLevel.AGGRESSIVE

    def test_compression_preserves_key_content(self):
        compressor = create_compressor(level="aggressive")

        key_content = """
        产品需求文档 (PRD)

        1. 目标：创建一个用户管理系统
        2. 功能：
           - 用户注册
           - 用户登录
           - 权限管理
        3. 验收标准：
           - 所有功能必须通过测试
        """

        result = compressor.compress(key_content)

        assert "PRD" in result or "产品需求" in result
        assert "用户" in result
        assert "注册" in result or "登录" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
