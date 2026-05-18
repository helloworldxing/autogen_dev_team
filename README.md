# 🤖 AutoGen Dev Team：多智能体协同软件开发系统

本项目基于 AutoGen 搭建一个多角色协作的“软件开发小组”。系统通过 Coordinator 进行流程调度，驱动 Product Manager / Engineer / QA 按既定顺序完成“需求 → PRD → 实现 → 测试 → 交付”。

为了提升生成质量与可控性，项目支持：
- **角色专属 RAG 知识库**（本地 Chroma 持久化 + Sentence-Transformers Embedding）
- **消息压缩与重复过滤**（缓解多轮对话导致的上下文膨胀）
- **对话持久化**（MongoDB 可选，用于回放与评估）
- **代码产物自动落盘**（输出到 `coding/` 目录，形成可交付文件结构）

## 🚀 如何使用

### 1）安装

```bash
pip install -r requirements.txt
```

### 2）配置环境变量（.env）

项目启动时会自动读取 `.env`（已在代码中 `load_dotenv()`）。常用配置如下：

```ini
# === LLM（云端 / 本地二选一）===
USE_LOCAL_LLM=false

# 云端模式：需要 DEEPSEEK_API_KEY（也可填入 DashScope 兼容接口的 key）
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 本地模式（可选）
# USE_LOCAL_LLM=true
# LOCAL_LLM_MODEL=qwen2.5-coder:latest
# LOCAL_LLM_BASE_URL=http://localhost:11434/v1
# LOCAL_LLM_API_KEY=ollama

# 是否启用流式输出（可选）
AUTOGEN_STREAM=true
LLM_TIMEOUT=180

# === RAG（可选）===
EXPERIMENT_ENABLE_RAG=true
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHROMA_PERSIST_ROOT=knowledge_bases
RAG_MIN_SIMILARITY=0.30

# === MongoDB 对话持久化（可选）===
MONGO_ENABLED=true
MONGO_URI=mongodb://localhost:27017
MONGO_DB=autogen_dev_team
MONGO_COLLECTION=conversation_messages
```

### 3）初始化/验证知识库（可选但推荐）

会从 `knowledge_bases/*_knowledge.txt` 加载角色知识，并写入本地 Chroma 持久化目录。

```bash
python test_rag_system.py
```

### 4）命令行运行（推荐）

```bash
python src/app/main.py
```

运行后按提示输入任务描述（支持多行，空行结束）。交付物会输出到 `coding/` 目录下的独立任务文件夹。

### 5）Web 运行（可选）

```bash
python src/app/web.py
```

打开 `http://127.0.0.1:5000/`，在页面中提交任务，前端会异步拉取事件流并展示执行过程。

## 🎓 示例场景

你可以直接把下面任意一条作为“任务描述”输入：

- **需求到交付（完整链路）**：
  - “做一个学生管理系统后端（Spring Boot / FastAPI 二选一），包含学生增删改查、分页查询、参数校验、基础单元测试，并生成 README 使用说明。”

- **工程实现 + 测试**：
  - “给一个 FastAPI API 增加登录鉴权（JWT），并补齐 pytest 测试用例与接口文档。”

- **Bug 修复/重构**：
  - “阅读当前代码，定位并修复一个报错（我会贴出堆栈），同时保证现有测试通过。”

## 📁 项目结构（关键目录）

```
autogen-dev-team/
├── src/
│   ├── app/                 # 任务入口、交付落盘、运行时编排（CLI/Web）
│   ├── agents/              # Coordinator/PM/Engineer/QA 角色定义与工厂
│   ├── rag/                 # RAG 知识库、检索注入、消息压缩
│   ├── persistence/         # MongoDB 持久化
│   └── web/                 # Web UI 静态资源与模板
├── knowledge_bases/         # 角色知识库（txt）+ Chroma 持久化目录
├── coding/                  # 每次任务的交付输出目录
└── test_rag_system.py       # RAG 初始化与基本功能验证
```


