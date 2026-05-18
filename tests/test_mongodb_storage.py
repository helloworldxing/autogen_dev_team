from __future__ import annotations

import uuid

from dotenv import load_dotenv

from src.persistence.mongo_logger import MongoConversationLogger

load_dotenv()


def test_mongodb_can_store_message() -> None:
    logger = MongoConversationLogger()

    assert logger.enabled, "MongoDB 未启用，请检查 MONGO_ENABLED 或连接配置"
    assert logger.collection is not None, "MongoDB 连接失败，无法执行存储测试"

    session_id = f"pytest-mongo-{uuid.uuid4().hex}"
    sender = "pytest-sender"
    receiver = "pytest-receiver"
    content = "这是一条用于验证 MongoDB 是否可以存储消息的测试消息。"

    print(f"MongoDB 测试ssion_id: {session_id}")

    logger.log_message(
        session_id=session_id,
        sender=sender,
        receiver=receiver,
        content=content,
        raw_message={"source": "pytest"},
    )

    doc = logger.collection.find_one(
        {
            "session_id": session_id,
            "sender": sender,
            "receiver": receiver,
            "content": content,
        }
    )

    assert doc is not None, "消息已写入，但 MongoDB 中没有查到对应记录"
    assert doc["content_hash"], "记录缺少 content_hash"
    assert doc["content_length"] == len(content), "content_length 不正确"

    logger.close()
