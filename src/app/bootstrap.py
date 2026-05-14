"""Application bootstrap wiring config, knowledge base, agents, and logging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from uuid import uuid4

from src.agents.factory import ROLE_ORDER, build_rag_agents
from src.config import llm_config, patch_autogen_streaming_token_count
from src.persistence.mongo_logger import MongoConversationLogger
from src.rag.knowledge_base import RAGKnowledgeManager
from src.app.streaming import enable_streaming_with_mongo_logging


@dataclass
class AppContext:
    session_id: str
    llm_config: Dict
    knowledge_manager: RAGKnowledgeManager
    agents: Dict[str, object]
    mongo_logger: MongoConversationLogger


def initialize_app() -> AppContext:
    patch_autogen_streaming_token_count()

    session_id = str(uuid4())
    mongo_logger = MongoConversationLogger()

    enable_streaming_with_mongo_logging(
        session_id=session_id,
        mongo_logger=mongo_logger,
        stream_enabled=llm_config.get("stream", True),
    )

    knowledge_manager = RAGKnowledgeManager()
    knowledge_manager.initialize_default_knowledge()

    agents = build_rag_agents(knowledge_manager)

    return AppContext(
        session_id=session_id,
        llm_config=llm_config,
        knowledge_manager=knowledge_manager,
        agents=agents,
        mongo_logger=mongo_logger,
    )


__all__ = ["initialize_app", "AppContext", "ROLE_ORDER"]
