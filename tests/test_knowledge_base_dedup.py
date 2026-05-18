"""Regression tests for Chroma ID deduplication in RoleKnowledgeBase.add_knowledge."""

from __future__ import annotations

from src.rag.knowledge_base import RoleKnowledgeBase


class _DummyVectorStore:
    def __init__(self) -> None:
        self.calls = []

    def add_documents(self, documents, ids):
        self.calls.append((documents, ids))


def test_add_knowledge_deduplicates_duplicate_doc_ids_within_batch():
    vs = _DummyVectorStore()
    kb = RoleKnowledgeBase("product_manager", vs)

    docs = [
        "同一段知识",
        "同一段知识",
        "另一段知识",
        "同一段知识",
    ]
    metas = [
        {"source": "a.txt"},
        {"source": "a.txt"},
        {"source": "a.txt"},
        {"source": "a.txt"},
    ]

    kb.add_knowledge(docs, metas)

    assert len(vs.calls) == 1
    _, ids = vs.calls[0]
    assert len(ids) == 2
    assert len(set(ids)) == len(ids)
