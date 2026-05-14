"""Agent factory to centralize role creation and RAG wrapping."""

from __future__ import annotations

from typing import Dict

from src.rag.agent_wrapper import RAGAgentWrapper
from src.rag.knowledge_base import RAGKnowledgeManager

from .coordinator import create_coordinator_agent
from .engineer import create_engineer_agent
from .product_manager import create_pm_agent
from .qa_engineer import create_qa_agent


ROLE_ORDER = ["coordinator", "product_manager", "engineer", "qa_engineer"]


def build_base_agents() -> Dict[str, object]:
    """Instantiate agents without RAG wrapping (ablation baseline)."""

    return {
        "coordinator": create_coordinator_agent(),
        "product_manager": create_pm_agent(),
        "engineer": create_engineer_agent(),
        "qa_engineer": create_qa_agent(),
    }


def build_rag_agents(knowledge_manager: RAGKnowledgeManager) -> Dict[str, object]:
    """Instantiate and wrap agents with role-specific knowledge bases."""

    agents = {
        "coordinator": RAGAgentWrapper(
            create_coordinator_agent(
                knowledge_base=knowledge_manager.get_knowledge_base("coordinator")
            ),
            knowledge_manager.get_knowledge_base("coordinator"),
        ).get_agent(),
        "product_manager": RAGAgentWrapper(
            create_pm_agent(
                knowledge_base=knowledge_manager.get_knowledge_base("product_manager")
            ),
            knowledge_manager.get_knowledge_base("product_manager"),
        ).get_agent(),
        "engineer": RAGAgentWrapper(
            create_engineer_agent(
                knowledge_base=knowledge_manager.get_knowledge_base("engineer")
            ),
            knowledge_manager.get_knowledge_base("engineer"),
        ).get_agent(),
        "qa_engineer": RAGAgentWrapper(
            create_qa_agent(
                knowledge_base=knowledge_manager.get_knowledge_base("qa_engineer")
            ),
            knowledge_manager.get_knowledge_base("qa_engineer"),
        ).get_agent(),
    }

    return agents
