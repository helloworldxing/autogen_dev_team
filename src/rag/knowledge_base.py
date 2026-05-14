"""RAG knowledge base modules per role (LangChain + Chroma-backed)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_chroma import Chroma
from sentence_transformers import SentenceTransformer

from src.rag.retrieval_formatter import format_retrieved_context


class SentenceTransformerEmbeddings(Embeddings):
    """LangChain embedding adapter based on sentence-transformers."""

    def __init__(self, model: SentenceTransformer) -> None:
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return self.model.encode(texts).tolist()

    def embed_query(self, text: str) -> List[float]:
        if not text:
            return []
        return self.model.encode([text]).tolist()[0]


class RoleKnowledgeBase:
    """Role-specific knowledge base backed by LangChain Chroma."""

    def __init__(
        self,
        role_name: str,
        vectorstore: Chroma,
        *,
        namespace: Optional[str] = None,
        knowledge_base_path: Path | str = "knowledge_bases",
    ) -> None:
        self.role_name = role_name
        self.vectorstore = vectorstore
        self.namespace = namespace or role_name
        self.knowledge_base_path = Path(knowledge_base_path)
        self.default_min_similarity = float(os.getenv("RAG_MIN_SIMILARITY", "0.30"))

        print(f"{role_name} 知识库已初始化（namespace={self.namespace}）")

    def add_knowledge(
        self, documents: List[str], metadatas: Optional[List[Dict]] = None
    ) -> None:
        if not documents:
            return

        cleaned_pairs: List[tuple[str, Dict]] = []
        for idx, doc in enumerate(documents):
            if not isinstance(doc, str):
                continue
            text = doc.strip()
            if not text:
                continue

            if metadatas is None:
                metadata = {"source": "manual_input"}
            elif idx < len(metadatas):
                metadata = dict(metadatas[idx] or {})
            else:
                metadata = {}

            cleaned_pairs.append((text, metadata))

        if not cleaned_pairs:
            return

        lc_docs: List[Document] = []
        ids: List[str] = []
        seen_ids: set[str] = set()
        skipped_duplicates = 0

        for doc, metadata in cleaned_pairs:
            safe_metadata = dict(metadata or {})
            safe_metadata["role"] = self.role_name
            doc_id = self._generate_doc_id(doc)
            if doc_id in seen_ids:
                skipped_duplicates += 1
                continue

            seen_ids.add(doc_id)
            safe_metadata["doc_id"] = doc_id
            lc_docs.append(Document(page_content=doc, metadata=safe_metadata))
            ids.append(doc_id)

        if not lc_docs:
            return

        self.vectorstore.add_documents(documents=lc_docs, ids=ids)
        message = f"已向 {self.role_name} 知识库添加 {len(lc_docs)} 条知识"
        if skipped_duplicates:
            message += f"（跳过 {skipped_duplicates} 条重复内容）"
        print(message)

    def query_knowledge(
        self, query: str, n_results: int = 3, min_similarity: Optional[float] = None
    ) -> List[str]:
        if not query or not query.strip():
            return []

        items = self.query_knowledge_items(
            query,
            n_results=n_results,
            min_similarity=min_similarity,
        )
        return [item["text"] for item in items if item.get("text")]

    def query_knowledge_items(
        self, query: str, n_results: int = 3, min_similarity: Optional[float] = None
    ) -> List[Dict]:
        if not query or not query.strip():
            return []

        threshold = (
            self.default_min_similarity
            if min_similarity is None
            else float(min_similarity)
        )

        matches = self.vectorstore.similarity_search_with_score(
            query=query,
            k=max(1, n_results),
        )
        all_items: List[Dict] = []
        for rank, (doc, score) in enumerate(matches, start=1):
            source = (doc.metadata or {}).get("source", "unknown")
            similarity = self._distance_to_similarity(float(score))
            all_items.append(
                {
                    "rank": rank,
                    "text": doc.page_content,
                    "source": source,
                    "score": float(score),
                    "similarity": similarity,
                    "matched": similarity >= threshold,
                }
            )
        filtered = [item for item in all_items if item["matched"]]

        # 如果阈值过滤后为空，回退到最相似的一条，避免上下文完全丢失。
        if not filtered and all_items:
            fallback = dict(all_items[0])
            fallback["matched"] = True
            fallback["fallback"] = True
            return [fallback]

        return filtered

    def load_from_file(self, file_path: str | Path) -> None:
        path = Path(file_path)
        if not path.exists():
            print(f"⚠ 知识文件不存在: {path}")
            return

        content = path.read_text(encoding="utf-8")
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if paragraphs:
            metadatas = [{"source": str(path)} for _ in paragraphs]
            self.add_knowledge(paragraphs, metadatas)

    def get_knowledge_count(self) -> int:
        payload = self.vectorstore.get(include=[])
        ids = payload.get("ids", []) if isinstance(payload, dict) else []
        return len(ids)

    def clear_knowledge_base(self) -> None:
        payload = self.vectorstore.get(include=[])
        ids = payload.get("ids", []) if isinstance(payload, dict) else []
        if ids:
            self.vectorstore.delete(ids=ids)
        print(f"✓ {self.role_name} 知识库已清空")

    def retrieve_context(
        self, query: str, n_results: int = 3, min_similarity: Optional[float] = None
    ) -> str:
        if not query or not query.strip():
            return ""

        threshold = (
            self.default_min_similarity
            if min_similarity is None
            else float(min_similarity)
        )

        raw_matches = self.vectorstore.similarity_search_with_score(
            query=query,
            k=max(1, n_results),
        )

        candidates: List[Dict] = []
        for rank, (doc, score) in enumerate(raw_matches, start=1):
            source = (doc.metadata or {}).get("source", "unknown")
            similarity = self._distance_to_similarity(float(score))
            candidates.append(
                {
                    "rank": rank,
                    "text": doc.page_content,
                    "source": source,
                    "score": float(score),
                    "similarity": similarity,
                    "matched": similarity >= threshold,
                }
            )

        selected = [item for item in candidates if item["matched"]]
        if not selected and candidates:
            fallback = dict(candidates[0])
            fallback["matched"] = True
            fallback["fallback"] = True
            selected = [fallback]

        if not selected:
            return ""

        return format_retrieved_context(
            query=query,
            candidates=candidates,
            selected=selected,
            min_similarity=threshold,
        )

    def _generate_doc_id(self, document: str) -> str:
        digest = hashlib.md5(document.encode("utf-8")).hexdigest()
        return f"{self.role_name}-{digest}"

    @staticmethod
    def _distance_to_similarity(distance: float) -> float:
        # Chroma 返回距离（越小越相似），这里统一映射到 (0, 1] 区间的相似度分数。
        return 1.0 / (1.0 + max(distance, 0.0))


class RAGKnowledgeManager:
    """Manage all role knowledge bases."""

    def __init__(self, knowledge_base_path: str | Path = "knowledge_bases") -> None:
        self.knowledge_base_path = Path(knowledge_base_path)
        self.knowledge_base_path.mkdir(parents=True, exist_ok=True)

        self.embedding_model_name = os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.embedding_model = SentenceTransformer(self.embedding_model_name)
        self.embedding_adapter = SentenceTransformerEmbeddings(self.embedding_model)

        self.chroma_root = Path(
            os.getenv("CHROMA_PERSIST_ROOT", str(self.knowledge_base_path))
        )
        self.chroma_root.mkdir(parents=True, exist_ok=True)

        def build_role_store(role: str) -> Chroma:
            role_dir = self.chroma_root / role
            role_dir.mkdir(parents=True, exist_ok=True)
            return Chroma(
                collection_name=f"{role}_knowledge",
                embedding_function=self.embedding_adapter,
                persist_directory=str(role_dir),
            )

        self.knowledge_bases = {
            "coordinator": RoleKnowledgeBase(
                "coordinator",
                build_role_store("coordinator"),
                knowledge_base_path=self.knowledge_base_path,
            ),
            "product_manager": RoleKnowledgeBase(
                "product_manager",
                build_role_store("product_manager"),
                knowledge_base_path=self.knowledge_base_path,
            ),
            "engineer": RoleKnowledgeBase(
                "engineer",
                build_role_store("engineer"),
                knowledge_base_path=self.knowledge_base_path,
            ),
            "qa_engineer": RoleKnowledgeBase(
                "qa_engineer",
                build_role_store("qa_engineer"),
                knowledge_base_path=self.knowledge_base_path,
            ),
        }

        print(f"Chroma 存储已就绪: {self.chroma_root}")
        print("RAG知识库管理器初始化完成")

    def get_knowledge_base(self, role_name: str) -> Optional[RoleKnowledgeBase]:
        return self.knowledge_bases.get(role_name)

    def initialize_default_knowledge(self) -> None:
        role_files = {
            "coordinator": "coordinator_knowledge.txt",
            "product_manager": "product_manager_knowledge.txt",
            "engineer": "engineer_knowledge.txt",
            "qa_engineer": "qa_engineer_knowledge.txt",
        }

        for role_name, filename in role_files.items():
            file_path = self.knowledge_base_path / filename
            kb = self.get_knowledge_base(role_name)
            if kb:
                kb.load_from_file(file_path)

    def get_all_knowledge_stats(self) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        for role_name, kb in self.knowledge_bases.items():
            stats[role_name] = kb.get_knowledge_count()
        return stats
