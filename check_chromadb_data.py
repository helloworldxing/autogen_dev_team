from __future__ import annotations

import os
import sys
from pathlib import Path

import chromadb
from dotenv import load_dotenv


def _detect_chroma_root() -> Path:
    load_dotenv()
    return Path(os.getenv("CHROMA_PERSIST_ROOT", "knowledge_bases"))


def _preview_collection(collection, preview_size: int = 5) -> None:
    try:
        count = collection.count()
    except Exception as exc:  # pragma: no cover - runtime fallback
        print(f"  ⚠ 统计失败: {exc}")
        return

    print(f"  • 记录数: {count}")
    if count == 0:
        return

    try:
        payload = collection.peek(preview_size)
    except Exception as exc:  # pragma: no cover - runtime fallback
        print(f"  ⚠ 预览失败: {exc}")
        return

    ids = payload.get("ids", []) if isinstance(payload, dict) else []
    documents = payload.get("documents", []) if isinstance(payload, dict) else []
    metadatas = payload.get("metadatas", []) if isinstance(payload, dict) else []

    print("  • 预览前几条记录:")
    for idx, doc_id in enumerate(ids, start=1):
        text = documents[idx - 1] if idx - 1 < len(documents) else ""
        metadata = metadatas[idx - 1] if idx - 1 < len(metadatas) else {}
        preview_text = str(text).replace("\n", " ")[:120]
        print(f"    {idx}. id={doc_id}")
        print(f"       metadata={metadata}")
        print(f"       text={preview_text}")


def main() -> int:
    root = _detect_chroma_root()
    print("=" * 60)
    print("🔎 ChromaDB 诊断")
    print("=" * 60)
    print(f"存储根目录: {root}")

    if not root.exists():
        print("❌ Chroma 存储目录不存在。")
        return 1

    role_dirs = [p for p in root.iterdir() if p.is_dir()]
    if not role_dirs:
        print("⚠ 目录下没有发现角色集合目录。")
        return 0

    found_any = False
    print("\n📚 逐个角色目录检查:")
    for role_dir in sorted(role_dirs):
        print(f"\n- 目录: {role_dir.name}")
        client = chromadb.PersistentClient(path=str(role_dir))
        try:
            collections = client.list_collections()
        except Exception as exc:  # pragma: no cover - runtime fallback
            print(f"  ⚠ 读取集合失败: {exc}")
            continue

        if not collections:
            print("  ⚠ 没有发现任何 Chroma 集合。")
            continue

        found_any = True
        for collection_info in collections:
            collection_name = getattr(collection_info, "name", str(collection_info))
            print(f"  • 集合: {collection_name}")
            try:
                collection = client.get_collection(collection_name)
            except Exception as exc:  # pragma: no cover - runtime fallback
                print(f"    ⚠ 无法打开集合: {exc}")
                continue
            _preview_collection(collection)

    if not found_any:
        print("\n⚠ 没有发现任何可读取的 Chroma 集合。")
        return 0

    print("\n提示:")
    print("1. 这里查看的是本地 Chroma 持久化文件，不是 MongoDB。")
    print(
        "2. 默认路径是 knowledge_bases/，如果设置了 CHROMA_PERSIST_ROOT 就看那个目录。"
    )
    print(
        "3. 每个角色通常对应一个集合，比如 coordinator_knowledge、engineer_knowledge。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
