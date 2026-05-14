"""
RAG知识库系统测试脚本
用于验证知识库的基本功能
"""

from src.rag.knowledge_base import RAGKnowledgeManager
import os


def print_section(title):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_knowledge_base_initialization():
    """测试知识库初始化"""
    print_section("测试1: 知识库初始化")

    manager = RAGKnowledgeManager()

    # 检查所有角色的知识库是否创建
    roles = ["coordinator", "product_manager", "engineer", "qa_engineer"]
    for role in roles:
        kb = manager.get_knowledge_base(role)
        if kb:
            print(f"✓ {role} 知识库创建成功")
        else:
            print(f"✗ {role} 知识库创建失败")

    return manager


def test_knowledge_loading(manager):
    """测试知识库加载"""
    print_section("测试2: 加载知识库内容")

    # 加载默认知识
    manager.initialize_default_knowledge()

    # 检查加载的知识数量
    stats = manager.get_all_knowledge_stats()
    print("\n📊 知识库统计:")
    for role, count in stats.items():
        print(f"  • {role}: {count} 条知识")

    return stats


def test_knowledge_query(manager):
    """测试知识检索"""
    print_section("测试3: 知识检索功能")

    test_cases = [
        {
            "role": "product_manager",
            "query": "如何编写PRD文档",
            "description": "产品经理 - PRD编写",
        },
        {
            "role": "engineer",
            "query": "Python编程规范和最佳实践",
            "description": "工程师 - Python规范",
        },
        {
            "role": "qa_engineer",
            "query": "如何使用pytest编写测试用例",
            "description": "QA工程师 - Pytest测试",
        },
        {
            "role": "coordinator",
            "query": "如何管理项目流程和角色边界",
            "description": "协调员 - 流程管理",
        },
    ]

    for test_case in test_cases:
        print(f"\n🔍 测试查询: {test_case['description']}")
        print(f"   查询内容: {test_case['query']}")

        kb = manager.get_knowledge_base(test_case["role"])
        if kb:
            results = kb.query_knowledge(test_case["query"], n_results=2)
            if results:
                print(f"   ✓ 检索到 {len(results)} 条相关知识")
                for i, result in enumerate(results, 1):
                    preview = result[:100].replace("\n", " ") + "..."
                    print(f"   [{i}] {preview}")
            else:
                print(f"   ⚠ 未检索到相关知识")
        else:
            print(f"   ✗ 知识库不存在")


def test_add_custom_knowledge(manager):
    """测试添加自定义知识"""
    print_section("测试4: 添加自定义知识")

    # 获取产品经理知识库
    pm_kb = manager.get_knowledge_base("product_manager")

    # 添加新知识
    new_knowledge = [
        "OKR目标管理法：Objectives（目标）+ Key Results（关键结果），用于设定和跟踪目标",
        "北极星指标：指导产品发展的核心指标，反映产品的核心价值和长期目标",
    ]

    print("\n➕ 添加新知识:")
    for knowledge in new_knowledge:
        print(f"   • {knowledge[:60]}...")

    initial_count = pm_kb.get_knowledge_count()
    pm_kb.add_knowledge(new_knowledge)
    final_count = pm_kb.get_knowledge_count()

    print(f"\n📊 添加前: {initial_count} 条知识")
    print(f"📊 添加后: {final_count} 条知识")
    print(f"✓ 成功添加 {final_count - initial_count} 条新知识")

    # 测试检索新添加的知识
    print("\n🔍 测试检索新添加的知识:")
    results = pm_kb.query_knowledge("OKR目标管理", n_results=1)
    if results and "OKR" in results[0]:
        print("   ✓ 成功检索到新添加的知识")
    else:
        print("   ⚠ 未能检索到新添加的知识")


def test_role_knowledge_focus():
    """测试角色知识专注性"""
    print_section("测试5: 角色知识专注性验证")

    manager = RAGKnowledgeManager()

    # 测试：产品经理知识库不应该包含编程细节
    pm_kb = manager.get_knowledge_base("product_manager")
    results = pm_kb.query_knowledge("如何编写Python代码", n_results=3)

    print("\n🔍 产品经理查询'如何编写Python代码':")
    if not results or all("Python" not in r or "PRD" in r for r in results):
        print("   ✓ 产品经理知识库正确地专注于产品领域")
    else:
        print("   ⚠ 产品经理知识库可能包含了不相关的技术内容")

    # 测试：工程师知识库不应该包含PRD编写方法
    eng_kb = manager.get_knowledge_base("engineer")
    results = eng_kb.query_knowledge("如何编写PRD文档", n_results=3)

    print("\n🔍 工程师查询'如何编写PRD文档':")
    if not results or all("PRD" not in r or "代码" in r for r in results):
        print("   ✓ 工程师知识库正确地专注于技术领域")
    else:
        print("   ⚠ 工程师知识库可能包含了不相关的产品内容")


def run_all_tests():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "RAG知识库系统测试" + " " * 15 + "║")
    print("╚" + "=" * 58 + "╝")

    try:
        # 测试1: 初始化
        manager = test_knowledge_base_initialization()

        # 测试2: 加载知识
        stats = test_knowledge_loading(manager)

        # 只有在成功加载知识后才继续其他测试
        if all(count > 0 for count in stats.values()):
            # 测试3: 检索
            test_knowledge_query(manager)

            # 测试4: 添加自定义知识
            test_add_custom_knowledge(manager)

            # 测试5: 角色专注性
            test_role_knowledge_focus()

            print_section("✅ 所有测试完成")
            print("\n系统状态: 正常")
            print("知识库已准备就绪，可以开始使用！")
        else:
            print_section("⚠ 警告")
            print("\n某些知识库未能加载知识。")
            print("请检查 knowledge_bases/ 目录下是否存在相应的txt文件。")

    except Exception as e:
        print_section("❌ 测试失败")
        print(f"\n错误信息: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
