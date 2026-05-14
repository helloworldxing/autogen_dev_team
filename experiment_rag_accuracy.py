"""实验1: RAG准确度对比实验（真实项目知识库 + 实际输出）"""

import json
from pathlib import Path
from typing import List, Dict
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams["font.sans-serif"] = ["SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False

from src.agents.factory import build_base_agents, build_rag_agents
from src.config import patch_autogen_streaming_token_count
from src.rag.knowledge_base import RAGKnowledgeManager


def evaluate_response_quality(response: str, expected_keywords: List[str]) -> float:
    """评估响应质量（基于关键词匹配）"""
    if not response or not expected_keywords:
        return 0.0

    response_lower = response.lower()
    matched = sum(1 for kw in expected_keywords if kw.lower() in response_lower)
    return matched / len(expected_keywords)


def generate_agent_response(agent, query: str) -> str:
    """调用真实智能体生成回复内容。"""
    messages = [{"role": "user", "content": query}]
    reply = agent.generate_reply(messages=messages, sender=None)
    if isinstance(reply, dict):
        return reply.get("content", "") or ""
    if isinstance(reply, str):
        return reply
    return str(reply) if reply is not None else ""


def run_rag_accuracy_experiment():
    """运行RAG准确度对比实验"""

    patch_autogen_streaming_token_count()

    # 测试用例 - 基于项目知识库内容构建
    test_cases = [
        {
            "name": "数据库设计规范",
            "query": "数据库设计规范有哪些要点？",
            "expected_keywords": ["主键", "索引", "表结构", "冗余"],
        },
        {
            "name": "RESTful接口规范",
            "query": "RESTful接口设计应包含哪些方法和返回格式？",
            "expected_keywords": [
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "code",
                "message",
                "data",
            ],
        },
        {
            "name": "安全规范",
            "query": "安全规范中如何处理密码与鉴权？",
            "expected_keywords": ["密码", "JWT", "Session", "SQL注入"],
        },
        {
            "name": "编码规范",
            "query": "编码规范有哪些要求？",
            "expected_keywords": ["单一职责", "命名", "重复代码", "异常处理"],
        },
        {
            "name": "性能优化",
            "query": "性能优化方面有哪些建议？",
            "expected_keywords": ["N+1", "缓存", "Redis", "IO"],
        },
    ]

    print("=" * 60)
    print("实验1: RAG准确度对比实验")
    print("=" * 60)

    # 初始化真实知识库（项目 knowledge_bases）
    kb_manager = RAGKnowledgeManager(knowledge_base_path="knowledge_bases")
    kb_manager.initialize_default_knowledge()

    base_agents = build_base_agents()
    rag_agents = build_rag_agents(kb_manager)
    base_engineer = base_agents["engineer"]
    rag_engineer = rag_agents["engineer"]

    results = {"without_rag": [], "with_rag": []}

    # 测试无RAG场景
    print("\n[测试1] 无RAG场景（基础回复）")
    print("-" * 60)
    for i, case in enumerate(test_cases, 1):
        base_response = generate_agent_response(base_engineer, case["query"])
        base_score = evaluate_response_quality(base_response, case["expected_keywords"])
        results["without_rag"].append(base_score)

        print(f"案例{i:2d} ({case['name']:12s}): 准确度 {base_score:6.1%}")

    # 测试有RAG场景
    print("\n[测试2] 有RAG场景（注入知识库）")
    print("-" * 60)
    for i, case in enumerate(test_cases, 1):
        rag_response = generate_agent_response(rag_engineer, case["query"])
        rag_score = evaluate_response_quality(rag_response, case["expected_keywords"])
        results["with_rag"].append(rag_score)

        print(f"案例{i:2d} ({case['name']:12s}): 准确度 {rag_score:6.1%}")

    # 计算统计数据
    avg_without = sum(results["without_rag"]) / len(results["without_rag"])
    avg_with = sum(results["with_rag"]) / len(results["with_rag"])
    improvement = (
        ((avg_with - avg_without) / avg_without * 100) if avg_without > 0 else 0
    )

    print("\n" + "=" * 60)
    print("实验结果汇总")
    print("=" * 60)
    print(f"无RAG平均准确度: {avg_without:.1%}")
    print(f"有RAG平均准确度: {avg_with:.1%}")
    print(f"准确度提升幅度: {improvement:.1f}%")

    # 详细的逐案例对比表
    print("\n" + "-" * 80)
    print("详细对比表")
    print("-" * 80)
    print(f"{'案例':<20} {'无RAG':<12} {'有RAG':<12} {'提升幅度':<12}")
    print("-" * 80)
    for i, case in enumerate(test_cases):
        without = results["without_rag"][i]
        with_rag = results["with_rag"][i]
        case_improvement = ((with_rag - without) / without * 100) if without > 0 else 0
        print(
            f"{case['name']:<20} {without:>10.1%}  {with_rag:>10.1%}  {case_improvement:>10.1f}%"
        )
    print("-" * 80)

    # 生成可视化图表
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # 图1: 逐案例对比
    x = range(1, len(test_cases) + 1)
    ax1.plot(
        x,
        [s * 100 for s in results["without_rag"]],
        "o-",
        label="无RAG",
        linewidth=2.5,
        markersize=10,
        color="#ff7f0e",
    )
    ax1.plot(
        x,
        [s * 100 for s in results["with_rag"]],
        "s-",
        label="有RAG",
        linewidth=2.5,
        markersize=10,
        color="#2ca02c",
    )
    ax1.set_xlabel("测试案例", fontsize=12, fontweight="bold")
    ax1.set_ylabel("准确度 (%)", fontsize=12, fontweight="bold")
    ax1.set_title("RAG对准确度的影响（逐案例对比）", fontsize=14, fontweight="bold")
    ax1.legend(fontsize=11, loc="upper left")
    ax1.grid(True, alpha=0.3, linestyle="--")
    ax1.set_xticks(x)
    ax1.set_ylim(0, 100)

    # 图2: 平均准确度对比
    categories = ["无RAG", "有RAG"]
    values = [avg_without * 100, avg_with * 100]
    colors = ["#ff7f0e", "#2ca02c"]
    bars = ax2.bar(
        categories, values, color=colors, alpha=0.7, edgecolor="black", linewidth=2
    )
    ax2.set_ylabel("平均准确度 (%)", fontsize=12, fontweight="bold")
    ax2.set_title("RAG准确度提升对比", fontsize=14, fontweight="bold")
    ax2.set_ylim(0, 100)

    # 在柱状图上添加数值标签
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax2.text(
            bar.get_x() + bar.get_width() / 2.0,
            height + 2,
            f"{val:.1f}%",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
        )

    ax2.grid(True, axis="y", alpha=0.3, linestyle="--")

    plt.tight_layout()
    output_path = Path("experiment_results/rag_accuracy_comparison.png")
    output_path.parent.mkdir(exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"\n图表已保存: {output_path}")

    # 保存详细结果
    result_data = {
        "test_cases": len(test_cases),
        "test_case_names": [case["name"] for case in test_cases],
        "without_rag": {"scores": results["without_rag"], "average": avg_without},
        "with_rag": {"scores": results["with_rag"], "average": avg_with},
        "improvement_percentage": improvement,
        "case_details": [
            {
                "name": case["name"],
                "without_rag": results["without_rag"][i],
                "with_rag": results["with_rag"][i],
                "improvement": (
                    (
                        (results["with_rag"][i] - results["without_rag"][i])
                        / results["without_rag"][i]
                        * 100
                    )
                    if results["without_rag"][i] > 0
                    else 0
                ),
            }
            for i, case in enumerate(test_cases)
        ],
    }

    json_path = Path("experiment_results/rag_accuracy_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)
    print(f"详细结果已保存: {json_path}")

    return result_data


if __name__ == "__main__":
    run_rag_accuracy_experiment()
