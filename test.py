import sys
from typing import Any, Dict, Optional
from autogen import ConversableAgent

# 保存原始方法（可选）
original_print = ConversableAgent._print_received_message

def streaming_print_received_message(
    self,
    message: Dict[str, Any],
    sender: Optional[ConversableAgent] = None,
    **kwargs
):
    """支持流式打印的 _print_received_message 替代实现"""
    # 只对 content 字段为字符串且非空的消息做流式处理
    content = message.get("content") or ""
    if not isinstance(content, str) or not content.strip():
        return original_print(self, message, sender, **kwargs)

    # 模拟流式输出：逐字符（或按词元）打印（实际中建议按 token 分块）
    sys.stdout.write("\n" + "▌ ")
    sys.stdout.flush()

    for i, char in enumerate(content):
        sys.stdout.write(char)
        sys.stdout.flush()
        # 可选：添加微小延迟模拟真实流式体验（调试用，生产环境通常移除）
        # import time; time.sleep(0.02)
    sys.stdout.write("\n")
    sys.stdout.flush()

# 应用 monkey patch（务必在创建 agent 前执行！）
ConversableAgent._print_received_message = streaming_print_received_message