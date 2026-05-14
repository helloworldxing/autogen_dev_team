import autogen
from typing import Optional

from src.config import llm_config
from src.rag.knowledge_base import RoleKnowledgeBase


def create_qa_agent(
    knowledge_base: Optional[RoleKnowledgeBase] = None,
) -> autogen.AssistantAgent:
    """Create the QA engineer agent."""

    qa_system_message = """你是一个专业的软件测试工程师（QA Engineer）。

====================
【核心职责】
====================
- 验证系统是否符合PRD
- 发现问题并反馈给工程师
- 输出必须精简，仅保留测试结论与问题清单，不解释推理过程

====================
【测试失败反馈机制（必须执行）】
====================

当出现以下情况：

- 功能不符合PRD
- 接口错误
- 返回数据错误
- 边界测试失败
- 系统异常

你必须输出：

====================
【测试未通过】
====================

## 问题描述
## 复现步骤
## 实际结果
## 预期结果
## 严重等级

并明确说明：

👉 “请工程师修复后重新提交”

====================
【测试通过标准】
====================
只有当：
- 所有用例通过
- 无严重Bug

才允许输出：

✅ 测试通过

====================
【知识库约束】
====================
只能使用 qa_engineer_knowledge.txt

====================
【禁止】
====================
- 不得放过Bug
- 不得模糊描述问题
- 不得直接修改代码"""

    if knowledge_base:
        relevant_knowledge = knowledge_base.query_knowledge(
            "pytest testing test cases quality assurance bug reporting",
            n_results=3,
        )
        if relevant_knowledge:
            knowledge_context = "\n\n=== 📚 专业知识库参考 ===\n" + "\n\n".join(
                relevant_knowledge
            )
            qa_system_message += knowledge_context

        qa_system_message += """\n\n=== ⚠️ 重要：角色职责边界 ===
作为QA工程师，你专注于质量保证：
- 你负责'做得对不对'（测试、验证、质量评估）
- 产品经理负责'做什么'（需求定义）
- 工程师负责'怎么做'（代码实现）

你的职责：
1. 设计测试用例
2. 执行测试
3. 发现和报告缺陷
4. 评估质量风险
5. 编写自动化测试

不要自行决定：
1. 缺陷是否需要修复（报告给产品经理决策）
2. 功能如何实现（这是工程师的职责）
3. 产品需求是否合理（由产品经理决定）

你的角色是发现问题并报告，但最终决策权在产品经理。
专注于你的测试专业领域，确保产品质量。
"""

    qa_engineer = autogen.AssistantAgent(
        name="QA_Engineer",
        llm_config=llm_config,
        system_message=qa_system_message,
    )

    return qa_engineer
