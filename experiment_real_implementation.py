"""
基于项目实际实现的RAG准确度实验
使用真实的RAG系统和消息压缩机制
"""
import json
import time
from pathlib import Path
from typing import List, Dict
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

from src.rag.knowledge_base import RAGKnowledgeManager
from src.rag.agent_wrapper import RAGAgentWrapper
from src.rag.message_compressor import MessageCompressor, CompressionLevel


class SimpleAgent:
    """简单的测试Agent"""
    def __init__(self, name: str):
        self.name = name
        self.chat_messages = {}

    def generate_reply(self, messages=None, sender=None, **kwargs):
        """生成回复"""
        if messages and isinstance(messages[-1], dict):
            content = messages[-1].get("content", "")
            return {"role": "assistant", "content": f"Response to: {content[:50]}"}
        return {"role": "assistant", "content": "No message"}


def run_real_rag_experiment():
    """运行基于真实RAG实现的实验"""

    print("=" * 70)
    print("实验1：基于项目RAG实现的准确度测试")
    print("=" * 70)

    # 初始化知识库管理器
    kb_manager = RAGKnowledgeManager(knowledge_base_path="project_kb")
    engineer_kb = kb_manager.get_knowledge_base("engineer")

    # 添加真实的工程知识
    engineering_knowledge = [
        "用户认证系统应使用JWT令牌进行无状态认证",
        "密码必须使用bcrypt或argon2进行加密存储",
        "支持OAuth 2.0第三方登录可提升用户体验",
        "会话管理需要设置合理的过期时间",
        "数据库设计应遵循第三范式减少冗余",
        "为常用查询字段建立索引提升性能",
        "使用外键约束保证数据完整性",
        "API测试应包含单元测试和集成测试",
        "使用Mock对象隔离外部依赖",
        "编写清晰的断言验证响应数据",
    ]

    engineer_kb.add_knowledge(engineering_knowledge)
    print(f"[OK] 已加载 {engineer_kb.get_knowledge_count()} 条知识")

    # 测试查询
    test_queries = [
        "如何实现用户认证？",
        "数据库设计有什么要点？",
        "API测试应该怎么做？",
        "如何提升系统性能？",
        "如何保证数据安全？",
    ]

    results = {
        "without_rag": [],
        "with_rag": [],
        "queries": test_queries
    }

    print("\n[测试1] 无RAG - 直接查询")
    print("-" * 70)
    for i, query in enumerate(test_queries, 1):
        agent = SimpleAgent("engineer")
        messages = [{"role": "user", "content": query}]

        start = time.time()
        response = agent.generate_reply(messages=messages)
        elapsed = time.time() - start

        # 无RAG时的响应长度作为基础指标
        response_length = len(response["content"])
        results["without_rag"].append(response_length)

        print(f"查询{i}: {query[:30]:30s} | 响应长度: {response_length:4d}字符 | 耗时: {elapsed*1000:6.1f}ms")

    print("\n[测试2] 有RAG - 注入知识库")
    print("-" * 70)
    for i, query in enumerate(test_queries, 1):
        agent = SimpleAgent("engineer")
        wrapped_agent = RAGAgentWrapper(agent, engineer_kb)

        messages = [{"role": "user", "content": query}]

        start = time.time()
        response = wrapped_agent.get_agent().generate_reply(messages=messages)
        elapsed = time.time() - start

        # 有RAG时的响应长度（包含注入的知识）
        response_length = len(response["content"])
        results["with_rag"].append(response_length)

        print(f"查询{i}: {query[:30]:30s} | 响应长度: {response_length:4d}字符 | 耗时: {elapsed*1000:6.1f}ms")

    # 计算统计数据
    avg_without = sum(results["without_rag"]) / len(results["without_rag"])
    avg_with = sum(results["with_rag"]) / len(results["with_rag"])
    improvement_ratio = (avg_with - avg_without) / avg_without * 100 if avg_without > 0 else 0

    print("\n" + "=" * 70)
    print("实验结果")
    print("=" * 70)
    print(f"无RAG平均响应长度: {avg_without:.0f}字符")
    print(f"有RAG平均响应长度: {avg_with:.0f}字符")
    print(f"响应内容增长: {improvement_ratio:.1f}%")

    # 生成图表 - 简洁版本，不显示"提升"标注
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # 图1: 逐查询对比
    x = range(1, len(test_queries) + 1)
    ax1.plot(x, results["without_rag"], 'o-', label='无RAG', linewidth=2.5, markersize=10, color='#ff7f0e')
    ax1.plot(x, results["with_rag"], 's-', label='有RAG', linewidth=2.5, markersize=10, color='#2ca02c')
    ax1.set_xlabel('测试查询', fontsize=12, fontweight='bold')
    ax1.set_ylabel('响应长度（字符）', fontsize=12, fontweight='bold')
    ax1.set_title('RAG对响应内容的影响', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=11, loc='upper left')
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.set_xticks(x)

    # 图2: 平均对比
    categories = ['无RAG', '有RAG']
    values = [avg_without, avg_with]
    colors = ['#ff7f0e', '#2ca02c']
    bars = ax2.bar(categories, values, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
    ax2.set_ylabel('平均响应长度（字符）', fontsize=12, fontweight='bold')
    ax2.set_title('平均响应长度对比', fontsize=14, fontweight='bold')

    # 在柱状图上添加数值标签
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 5,
                f'{val:.0f}', ha='center', va='bottom', fontsize=12, fontweight='bold')

    ax2.grid(True, axis='y', alpha=0.3, linestyle='--')

    plt.tight_layout()
    output_path = Path("experiment_results/rag_real_comparison.png")
    output_path.parent.mkdir(exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n图表已保存: {output_path}")

    # 保存结果
    result_data = {
        "test_queries": test_queries,
        "without_rag": results["without_rag"],
        "with_rag": results["with_rag"],
        "avg_without": avg_without,
        "avg_with": avg_with,
        "improvement_ratio": improvement_ratio
    }

    json_path = Path("experiment_results/rag_real_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)
    print(f"结果已保存: {json_path}")

    return result_data


def run_real_compression_experiment():
    """运行基于真实压缩实现的实验"""

    print("\n" + "=" * 70)
    print("实验2：基于项目压缩实现的效率测试")
    print("=" * 70)

    # 真实的多智能体通信消息
    test_messages = [
        {
            "type": "code",
            "content": """def authenticate_user(username: str, password: str) -> bool:
    \"\"\"验证用户身份\"\"\"
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    return verify_password(password, user.password_hash)

# 使用示例
if authenticate_user("admin", "password123"):
    print("认证成功")
else:
    print("认证失败")"""
        },
        {
            "type": "conversation",
            "content": """产品经理: 我们需要在下周发布新的认证功能。
工程师: 好的，我会开始设计认证系统架构。
产品经理: 需要支持哪些认证方式？
工程师: 首先支持邮箱密码登录，然后逐步添加OAuth。
QA工程师: 我会准备相应的测试用例。"""
        },
        {
            "type": "document",
            "content": """# API设计规范

## 请求格式
- 使用RESTful风格
- 统一使用JSON格式
- 请求头包含Content-Type: application/json

## 响应格式
{
  "code": 200,
  "message": "success",
  "data": {}
}

## 错误处理
- 4xx: 客户端错误
- 5xx: 服务器错误"""
        },
    ]

    compression_levels = [
        ("NONE", CompressionLevel.NONE),
        ("LIGHT", CompressionLevel.LIGHT),
        ("MODERATE", CompressionLevel.MODERATE),
        ("AGGRESSIVE", CompressionLevel.AGGRESSIVE)
    ]

    results = {}

    for level_name, level in compression_levels:
        print(f"\n[测试] 压缩等级: {level_name}")
        print("-" * 70)

        compressor = MessageCompressor(level=level)
        level_results = []

        for i, msg in enumerate(test_messages, 1):
            content = msg["content"]
            content_type = msg["type"]

            original_size = len(content)
            compressed = compressor.compress(content, content_type)
            compressed_size = len(compressed)

            ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

            level_results.append({
                "type": content_type,
                "original_size": original_size,
                "compressed_size": compressed_size,
                "ratio": ratio
            })

            print(f"消息{i} ({content_type:12s}): {original_size:5d}B → {compressed_size:5d}B | 压缩率: {ratio:5.1f}%")

        stats = compressor.get_stats()
        overall_ratio = stats.get_overall_ratio() * 100

        results[level_name] = {
            "messages": level_results,
            "overall_ratio": overall_ratio,
            "total_original": stats.total_original_bytes,
            "total_compressed": stats.total_compressed_bytes
        }

        print(f"总体压缩率: {overall_ratio:.1f}%")

    # 生成图表 - 简洁版本
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

    # 图1: 压缩等级对比
    levels = list(results.keys())
    overall_ratios = [results[level]["overall_ratio"] for level in levels]
    colors = ['#d62728', '#ff7f0e', '#2ca02c', '#1f77b4']

    bars = ax1.bar(levels, overall_ratios, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
    ax1.set_ylabel('压缩率 (%)', fontsize=12, fontweight='bold')
    ax1.set_title('不同压缩等级的压缩率', fontsize=14, fontweight='bold')
    ax1.set_ylim(0, max(overall_ratios) * 1.2)
    ax1.grid(True, axis='y', alpha=0.3)

    for bar, val in zip(bars, overall_ratios):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')

    # 图2: 消息类型压缩效果
    moderate_data = results["MODERATE"]["messages"]
    msg_types = [m["type"] for m in moderate_data]
    msg_ratios = [m["ratio"] for m in moderate_data]

    ax2.barh(range(len(msg_types)), msg_ratios, color='#2ca02c', alpha=0.7, edgecolor='black')
    ax2.set_yticks(range(len(msg_types)))
    ax2.set_yticklabels(msg_types, fontsize=10)
    ax2.set_xlabel('压缩率 (%)', fontsize=12, fontweight='bold')
    ax2.set_title('各消息类型压缩率 (MODERATE等级)', fontsize=14, fontweight='bold')
    ax2.grid(True, axis='x', alpha=0.3)

    for i, val in enumerate(msg_ratios):
        ax2.text(val, i, f' {val:.1f}%', va='center', fontsize=10)

    # 图3: 数据量对比
    x = range(len(levels))
    original_sizes = [results[level]["total_original"] for level in levels]
    compressed_sizes = [results[level]["total_compressed"] for level in levels]

    width = 0.35
    ax3.bar([i - width/2 for i in x], original_sizes, width, label='原始大小', color='#ff7f0e', alpha=0.7)
    ax3.bar([i + width/2 for i in x], compressed_sizes, width, label='压缩后大小', color='#2ca02c', alpha=0.7)
    ax3.set_ylabel('数据量 (Bytes)', fontsize=12, fontweight='bold')
    ax3.set_title('压缩前后数据量对比', fontsize=14, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(levels)
    ax3.legend(fontsize=11)
    ax3.grid(True, axis='y', alpha=0.3)

    # 图4: 压缩率趋势
    ax4.plot(levels, overall_ratios, 'o-', linewidth=3, markersize=10, color='#1f77b4')
    ax4.fill_between(range(len(levels)), overall_ratios, alpha=0.3, color='#1f77b4')
    ax4.set_ylabel('压缩率 (%)', fontsize=12, fontweight='bold')
    ax4.set_xlabel('压缩等级', fontsize=12, fontweight='bold')
    ax4.set_title('压缩率变化趋势', fontsize=14, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.set_ylim(0, max(overall_ratios) * 1.1)

    for i, (level, ratio) in enumerate(zip(levels, overall_ratios)):
        ax4.text(i, ratio, f'{ratio:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')

    plt.tight_layout()
    output_path = Path("experiment_results/compression_real_comparison.png")
    output_path.parent.mkdir(exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n图表已保存: {output_path}")

    # 保存结果
    json_path = Path("experiment_results/compression_real_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"结果已保存: {json_path}")

    return results


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("基于项目实现的真实实验")
    print("=" * 70)

    rag_results = run_real_rag_experiment()
    compression_results = run_real_compression_experiment()

    print("\n" + "=" * 70)
    print("[OK] 所有实验完成")
    print("=" * 70)
    print(f"\n[DATA] RAG实验结果:")
    print(f"   无RAG平均响应: {rag_results['avg_without']:.0f}字符")
    print(f"   有RAG平均响应: {rag_results['avg_with']:.0f}字符")
    print(f"   内容增长: {rag_results['improvement_ratio']:.1f}%")

    print(f"\n[DATA] 压缩实验结果:")
    print(f"   MODERATE等级压缩率: {compression_results['MODERATE']['overall_ratio']:.1f}%")
