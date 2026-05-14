"""
测试 Chroma + LangChain + RAG 知识库是否正常工作
"""

from src.rag.knowledge_base import RAGKnowledgeManager
from dotenv import load_dotenv

load_dotenv()  # 确保加载环境变量


def main():
    print("🚀 开始测试 Chroma RAG 系统...\n")

    try:
        # ===== 2. 初始化 RAG 管理器 =====
        print("📦 初始化 RAG 知识库管理器...")
        manager = RAGKnowledgeManager()

        # ===== 3. 获取工程师知识库 =====
        print("\n👨‍💻 获取 engineer 知识库...")
        kb = manager.get_knowledge_base("engineer")

        count = kb.get_knowledge_count()
        print(f"📊 当前 engineer 知识库数量: {count}")

        # 如果没有数据 -》 自动初始化
        if count == 0:
            print("初始化数据库中...")
            kb.add_knowledge(
                [
                    "Python是一种解释型编程语言，适合快速开发。",
                    "Java是一种面向对象的编程语言，广泛用于企业级开发。",
                    "使用缓存可以提高系统性能，例如Redis。",
                    "数据库索引可以加快查询速度。",
                    "多线程可以提升程序执行效率。",
                ]
            )

        items = kb.query_knowledge_items("如何提高系统性能", n_results=3)
        print("\n📌 相似度匹配结果:")
        for item in items:
            similarity = item.get("similarity", 0.0)
            source = item.get("source", "unknown")
            text = str(item.get("text", "")).replace("\n", " ")
            print(
                f"- rank={item.get('rank')} similarity={similarity:.4f} "
                f"source={source} text={text[:80]}..."
            )

        context = kb.retrieve_context("如何提高系统性能", n_results=3)
        print("\n📦 结构化检索块预览:")
        print(context)

        if not kb:
            print("❌ 获取知识库失败")
            return

        #     # ===== 4. 清空旧数据（测试用）=====
        #     print("\n🧹 清空旧知识...")
        #     kb.clear_knowledge_base()

        #     # ===== 5. 添加测试数据 =====
        #     print("\n📚 添加测试知识...")
        #     test_docs = [
        #         "Python是一种解释型编程语言，适合快速开发。",
        #         "Java是一种面向对象的编程语言，广泛用于企业级开发。",
        #         "使用缓存可以提高系统性能，例如Redis。",
        #         "数据库索引可以加快查询速度。",
        #         "多线程可以提升程序执行效率。"
        #     ]

        #     kb.add_knowledge(test_docs)

        #     # ===== 6. 查看数量 =====
        #     count = kb.get_knowledge_count()
        #     print(f"\n📊 当前知识库数量: {count}")

        #     # ===== 7. 查询测试 =====
        #     print("\n🔍 测试查询：'如何提高系统性能'")
        #     results = kb.query_knowledge("如何提高系统性能", n_results=3)

        #     print("\n📌 查询结果:")
        #     for i, res in enumerate(results, 1):
        #         print(f"{i}. {res}")

        #     # ===== 8. 再测试一个查询 =====
        #     print("\n🔍 测试查询：'什么是Java'")
        #     results = kb.query_knowledge("什么是Java", n_results=2)

        #     print("\n📌 查询结果:")
        #     for i, res in enumerate(results, 1):
        #         print(f"{i}. {res}")

        #     print("\n✅ 测试完成！Pinecone + RAG 工作正常 🎉")

        print("\n✅ 测试完成！Chroma + LangChain + RAG 工作正常 🎉")

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")


if __name__ == "__main__":
    main()
