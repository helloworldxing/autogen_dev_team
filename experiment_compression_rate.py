"""实验2: 消息压缩率实验"""

import json
import time
import re
from pathlib import Path
from typing import List, Dict
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams["font.sans-serif"] = ["SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False

from src.rag.message_compressor import MessageCompressor, CompressionLevel


def generate_test_messages() -> List[Dict[str, str]]:
    """生成测试消息集"""
    return [
        {
            "type": "code",
            "content": """```python
def calculate_fibonacci(n: int) -> int:
    \"\"\"计算斐波那契数列第n项\"\"\"
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

# 测试代码
for i in range(10):
    print(f"fibonacci({i}) = {calculate_fibonacci(i)}")
```

以上是一个递归实现的斐波那契数列计算函数。请注意，这个实现效率较低，对于大的n值会有性能问题。""",
        },
        {
            "type": "conversation",
            "content": """产品经理: 我们需要在下周发布新的用户认证功能。

工程师: 好的，我会开始设计认证系统架构。我们需要支持哪些认证方式？

产品经理: 首先支持邮箱密码登录，然后逐步添加第三方OAuth登录。

工程师: 明白了。我会使用JWT进行无状态认证，并确保密码使用bcrypt加密存储。

QA工程师: 我会准备相应的测试用例，包括正常登录、错误密码、会话过期等场景。

协调员: 很好，大家分工明确。请工程师在周三前完成设计文档，QA在周四前准备好测试计划。""",
        },
        {
            "type": "document",
            "content": """# 产品需求文档 (PRD)

## 1. 项目背景
本项目旨在开发一个现代化的任务管理系统，帮助团队更高效地协作。

## 2. 核心功能
- **任务创建**: 用户可以创建任务并设置优先级
- **任务分配**: 支持将任务分配给团队成员
- **进度跟踪**: 实时查看任务完成状态
- **通知提醒**: 任务截止前自动提醒

## 3. 技术要求
- 前端使用React + TypeScript
- 后端使用Python FastAPI
- 数据库使用PostgreSQL
- 部署在AWS云平台

## 4. 时间规划
- 第1-2周: 需求分析和设计
- 第3-4周: 核心功能开发
- 第5周: 测试和优化
- 第6周: 上线部署""",
        },
        {
            "type": "general",
            "content": "请帮我review这段代码，看看有没有潜在的bug或性能问题。特别关注边界条件的处理。",
        },
        {
            "type": "code_snippet",
            "content": """这是API端点的实现：

```python
@app.post("/api/users")
async def create_user(user: UserCreate):
    return {"id": 123, "name": user.name}
```

需要添加数据验证和错误处理。""",
        },
        {
            "type": "conversation",
            "content": """用户: 系统登录很慢，能优化一下吗？

工程师: 我检查了一下，发现是数据库查询没有使用索引。我会添加索引并优化查询语句。

用户: 大概需要多久？

工程师: 今天下午就能完成，优化后登录速度应该能提升50%以上。

用户: 太好了，谢谢！""",
        },
        {
            "type": "document",
            "content": """## API设计规范

### 请求格式
- 使用RESTful风格
- 统一使用JSON格式
- 请求头包含Content-Type: application/json

### 响应格式
```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

### 错误处理
- 4xx: 客户端错误
- 5xx: 服务器错误
- 返回详细错误信息""",
        },
        {
            "type": "general",
            "content": "明天的会议改到下午3点，请大家准时参加。会议主题是讨论Q2的产品规划。",
        },
    ]


def calculate_semantic_preservation(
    original: str, compressed: str, keywords: list
) -> float:
    """计算语义保留度 - 基于关键词保留率"""
    if not keywords:
        return 1.0

    original_lower = original.lower()
    compressed_lower = compressed.lower()

    preserved = sum(
        1
        for kw in keywords
        if kw.lower() in compressed_lower and kw.lower() in original_lower
    )
    return preserved / len(keywords) if keywords else 1.0


def summarize_text(text: str, max_sentences: int = 2) -> str:
    """生成简要摘要（句子级截取，便于比较压缩前后要点）。"""
    if not text:
        return ""

    sentences = [s.strip() for s in re.split(r"[。！？!?\n]+", text) if s.strip()]
    if not sentences:
        return text.strip()

    return "。".join(sentences[:max_sentences])


def calculate_summary_similarity(
    original_summary: str, compressed_summary: str, keywords: list
) -> float:
    """比较摘要中的关键词重合度，衡量压缩前后摘要一致性。"""
    if not keywords:
        return 1.0

    original_lower = original_summary.lower()
    compressed_lower = compressed_summary.lower()
    matched = sum(
        1
        for kw in keywords
        if kw.lower() in original_lower and kw.lower() in compressed_lower
    )
    return matched / len(keywords) if keywords else 1.0


def run_compression_experiment():
    """运行消息压缩率实验"""

    print("=" * 60)
    print("实验2: 消息压缩率实验")
    print("=" * 60)

    test_messages = generate_test_messages()

    compression_levels = [
        ("NONE", CompressionLevel.NONE),
        ("LIGHT", CompressionLevel.LIGHT),
        ("MODERATE", CompressionLevel.MODERATE),
        ("AGGRESSIVE", CompressionLevel.AGGRESSIVE),
    ]

    # 为每种消息类型定义关键词，用于评估语义保留度
    keyword_map = {
        "code": ["def", "return", "function", "class", "import"],
        "conversation": ["产品经理", "工程师", "QA", "完成", "优化"],
        "document": ["API", "设计", "规范", "格式", "错误"],
        "general": ["会议", "讨论", "规划", "参加"],
        "code_snippet": ["def", "async", "return", "json"],
    }

    results = {}

    for level_name, level in compression_levels:
        print(f"\n[测试] 压缩级别: {level_name}")
        print("-" * 80)

        compressor = MessageCompressor(level=level)
        level_results = []

        for i, msg in enumerate(test_messages, 1):
            content = msg["content"]
            content_type = msg["type"]

            original_size = len(content)
            compressed = compressor.compress(content, content_type)
            compressed_size = len(compressed)

            ratio = (
                (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
            )

            # 计算语义保留度
            keywords = keyword_map.get(content_type, [])
            preservation = calculate_semantic_preservation(
                content, compressed, keywords
            )

            # 摘要一致性（压缩前后摘要对比）
            original_summary = summarize_text(content)
            compressed_summary = summarize_text(compressed)
            summary_similarity = calculate_summary_similarity(
                original_summary, compressed_summary, keywords
            )

            level_results.append(
                {
                    "type": content_type,
                    "original_size": original_size,
                    "compressed_size": compressed_size,
                    "ratio": ratio,
                    "preservation": preservation,
                    "summary_similarity": summary_similarity,
                }
            )

            print(
                f"消息{i} ({content_type:12s}): {original_size:5d}B → {compressed_size:5d}B | "
                f"压缩率: {ratio:5.1f}% | 语义保留: {preservation:5.1%} | 摘要一致: {summary_similarity:5.1%}"
            )

        stats = compressor.get_stats()
        overall_ratio = stats.get_overall_ratio() * 100
        avg_preservation = sum(r["preservation"] for r in level_results) / len(
            level_results
        )
        avg_summary_similarity = sum(
            r["summary_similarity"] for r in level_results
        ) / len(level_results)

        results[level_name] = {
            "messages": level_results,
            "overall_ratio": overall_ratio,
            "avg_preservation": avg_preservation,
            "avg_summary_similarity": avg_summary_similarity,
            "total_original": stats.total_original_bytes,
            "total_compressed": stats.total_compressed_bytes,
        }

        print(f"\n总体压缩率: {overall_ratio:.1f}%")
        print(f"平均语义保留度: {avg_preservation:.1%}")
        print(f"平均摘要一致性: {avg_summary_similarity:.1%}")
        print(f"总原始大小: {stats.total_original_bytes}B")
        print(f"总压缩大小: {stats.total_compressed_bytes}B")

    # 生成可视化图表
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

    # 图1: 不同压缩级别的总体压缩率对比
    levels = list(results.keys())
    overall_ratios = [results[level]["overall_ratio"] for level in levels]
    colors = ["#d62728", "#ff7f0e", "#2ca02c", "#1f77b4"]

    bars = ax1.bar(
        levels,
        overall_ratios,
        color=colors,
        alpha=0.7,
        edgecolor="black",
        linewidth=1.5,
    )
    ax1.set_ylabel("压缩率 (%)", fontsize=12)
    ax1.set_title("不同压缩级别的总体压缩率", fontsize=14, fontweight="bold")
    ax1.set_ylim(0, max(overall_ratios) * 1.2)
    ax1.grid(True, axis="y", alpha=0.3)

    for bar, val in zip(bars, overall_ratios):
        height = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{val:.1f}%",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    # 图2: 各消息类型在MODERATE级别下的压缩率和语义保留度
    moderate_data = results["MODERATE"]["messages"]
    msg_types = [m["type"] for m in moderate_data]
    msg_ratios = [m["ratio"] for m in moderate_data]
    msg_preservation = [m["preservation"] * 100 for m in moderate_data]

    x_pos = range(len(msg_types))
    width = 0.35

    ax2_twin = ax2.twinx()
    bars1 = ax2.bar(
        [i - width / 2 for i in x_pos],
        msg_ratios,
        width,
        label="压缩率",
        color="#2ca02c",
        alpha=0.7,
        edgecolor="black",
    )
    bars2 = ax2_twin.bar(
        [i + width / 2 for i in x_pos],
        msg_preservation,
        width,
        label="语义保留度",
        color="#1f77b4",
        alpha=0.7,
        edgecolor="black",
    )

    ax2.set_ylabel("压缩率 (%)", fontsize=12, color="#2ca02c")
    ax2_twin.set_ylabel("语义保留度 (%)", fontsize=12, color="#1f77b4")
    ax2.set_title(
        "各消息类型压缩率与语义保留度 (MODERATE级别)", fontsize=14, fontweight="bold"
    )
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(msg_types, fontsize=10)
    ax2.grid(True, axis="y", alpha=0.3)
    ax2.tick_params(axis="y", labelcolor="#2ca02c")
    ax2_twin.tick_params(axis="y", labelcolor="#1f77b4")

    # 添加图例
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=10)

    # 图3: 压缩前后数据量对比
    x = range(len(levels))
    original_sizes = [results[level]["total_original"] for level in levels]
    compressed_sizes = [results[level]["total_compressed"] for level in levels]

    width = 0.35
    ax3.bar(
        [i - width / 2 for i in x],
        original_sizes,
        width,
        label="原始大小",
        color="#ff7f0e",
        alpha=0.7,
    )
    ax3.bar(
        [i + width / 2 for i in x],
        compressed_sizes,
        width,
        label="压缩后大小",
        color="#2ca02c",
        alpha=0.7,
    )
    ax3.set_ylabel("数据量 (Bytes)", fontsize=12)
    ax3.set_title("压缩前后数据量对比", fontsize=14, fontweight="bold")
    ax3.set_xticks(x)
    ax3.set_xticklabels(levels)
    ax3.legend(fontsize=11)
    ax3.grid(True, axis="y", alpha=0.3)

    # 图4: 压缩效率趋势（压缩率随级别变化）
    ax4.plot(levels, overall_ratios, "o-", linewidth=3, markersize=10, color="#1f77b4")
    ax4.fill_between(range(len(levels)), overall_ratios, alpha=0.3, color="#1f77b4")
    ax4.set_ylabel("压缩率 (%)", fontsize=12)
    ax4.set_xlabel("压缩级别", fontsize=12)
    ax4.set_title("压缩率提升趋势", fontsize=14, fontweight="bold")
    ax4.grid(True, alpha=0.3)
    ax4.set_ylim(0, max(overall_ratios) * 1.1)

    for i, (level, ratio) in enumerate(zip(levels, overall_ratios)):
        ax4.text(
            i,
            ratio,
            f"{ratio:.1f}%",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    plt.tight_layout()
    output_path = Path("experiment_results/compression_rate_comparison.png")
    output_path.parent.mkdir(exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"\n图表已保存: {output_path}")

    # 保存详细结果
    json_path = Path("experiment_results/compression_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"详细结果已保存: {json_path}")

    # 打印总结
    print("\n" + "=" * 60)
    print("实验结果总结")
    print("=" * 60)
    print(f"测试消息数: {len(test_messages)}")

    # 找出最佳压缩级别
    best_level = max(results.items(), key=lambda x: x[1]["overall_ratio"])[0]
    print(f"最高压缩率: {results[best_level]['overall_ratio']:.1f}% ({best_level}级别)")

    # 推荐级别分析
    moderate_ratio = results["MODERATE"]["overall_ratio"]
    moderate_preservation = results["MODERATE"]["avg_preservation"]
    print(f"\n推荐配置 (MODERATE级别):")
    print(f"  • 压缩率: {moderate_ratio:.1f}%")
    print(f"  • 平均语义保留度: {moderate_preservation:.1%}")
    print(f"  • 通信数据量减少: {moderate_ratio:.1f}%")

    # 详细的压缩等级对比表
    print("\n" + "-" * 80)
    print("压缩等级对比表")
    print("-" * 80)
    print(
        f"{'压缩等级':<12} {'原始大小':<12} {'压缩后':<12} {'压缩率':<12} {'语义保留度':<12}"
    )
    print("-" * 80)
    for level_name in ["NONE", "LIGHT", "MODERATE", "AGGRESSIVE"]:
        data = results[level_name]
        print(
            f"{level_name:<12} {data['total_original']:>10}B  {data['total_compressed']:>10}B  "
            f"{data['overall_ratio']:>10.1f}%  {data['avg_preservation']:>10.1%}"
        )
    print("-" * 80)

    return results


if __name__ == "__main__":
    run_compression_experiment()
