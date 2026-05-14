"""MongoDB conversation persistence utilities."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()


class MongoConversationLogger:
    """Persist multi-agent conversation messages into MongoDB."""

    def __init__(self):
        self.enabled = os.getenv("MONGO_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        self.client: Optional[MongoClient] = None
        self.collection = None
        self._last_route_hash: Dict[str, str] = {}

        if not self.enabled:
            print("⚠ MongoDB 持久化已禁用（MONGO_ENABLED=false）")
            return

        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        mongo_db = os.getenv("MONGO_DB", "autogen_dev_team")
        mongo_collection = os.getenv("MONGO_COLLECTION", "conversation_messages")

        try:
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
            self.client.admin.command("ping")
            self.collection = self.client[mongo_db][mongo_collection]
            print(f"✅ MongoDB 已连接: {mongo_uri} → {mongo_db}.{mongo_collection}")
        except PyMongoError as exc:
            self.enabled = False
            self.client = None
            self.collection = None
            print(f"⚠️  MongoDB 连接失败: {exc}")
            print(f"   连接字符串: {mongo_uri}")
            print(f"   已降级为仅控制台输出（不会持久化数据到 MongoDB）")

    @staticmethod
    def _compact_content(content: str) -> str:
        """压缩文本，减少 MongoDB 冗余存储。"""
        text = content or ""
        text = re.sub(r"```(?:python|py)?", "", text, flags=re.IGNORECASE)
        text = text.replace("```", "")
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"__(.*?)__", r"\1", text)
        text = re.sub(r"`([^`]*)`", r"\1", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def log_message(
        self,
        *,
        session_id: str,
        receiver: str,
        sender: Optional[str],
        content: str,
        raw_message: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled or self.collection is None:
            return

        compact_content = self._compact_content(content)
        route_key = f"{session_id}|{sender or 'unknown'}|{receiver}"
        content_hash = hashlib.sha1(
            compact_content.encode("utf-8", errors="ignore")
        ).hexdigest()

        if self._last_route_hash.get(route_key) == content_hash:
            return
        self._last_route_hash[route_key] = content_hash

        document = {
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc),
            "sender": sender,
            "receiver": receiver,
            "content": content,
            "content_compact": compact_content,
            "content_hash": content_hash,
            "content_length": len(content),
            "compact_length": len(compact_content),
            "raw_message": raw_message or {},
        }

        try:
            result = self.collection.insert_one(document)
            # 可选：取消注释下行来调试每条消息的写入
            # print(f"[MONGO] 消息已保存: {sender}→{receiver} ({result.inserted_id})")
        except PyMongoError as exc:
            print(f"⚠️  MongoDB 写入失败: {exc}")

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
