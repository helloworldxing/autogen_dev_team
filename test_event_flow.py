#!/usr/bin/env python3
"""测试事件流，验证消息是否正确转发到前端"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 测试事件回调
events_received = []


def test_event_callback(event):
    events_received.append(event)
    event_type = event.get("type", "unknown")
    if event_type == "message":
        print(f"✓ 收到消息事件: {event.get('sender')} -> {event.get('receiver')}")
    elif event_type == "status":
        print(f"✓ 收到状态事件: {event.get('stage')} - {event.get('message')}")


# 简单任务测试
test_task = "生成一个简单的 Python 函数，计算数字的阶乘"

print("=" * 60)
print("开始测试事件流...")
print("=" * 60)

try:
    from src.app.main import run_task

    result = run_task(test_task, event_callback=test_event_callback)

    print("\n" + "=" * 60)
    print("事件统计:")
    print("=" * 60)

    message_count = len([e for e in events_received if e.get("type") == "message"])
    status_count = len([e for e in events_received if e.get("type") == "status"])

    print(f"消息事件数: {message_count}")
    print(f"状态事件数: {status_count}")
    print(f"总事件数: {len(events_received)}")

    if message_count > 0:
        print("\n✅ 事件流正常，消息正被转发到前端")
    else:
        print("\n⚠️ 警告：没有检测到消息事件，前端可能看不到对话内容")

    print("\n任务完成！")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback

    traceback.print_exc()
