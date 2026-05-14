from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set


LANGUAGE_BY_EXT: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".vue": "frontend",
    ".java": "java",
    ".go": "go",
    ".cs": "dotnet",
    ".rb": "ruby",
    ".php": "php",
}

# 统一的行业分层语义，不绑定某个语言。
GENERIC_CORE_LAYER_RULES: Dict[str, Set[str]] = {
    "presentation": {
        "controller",
        "controllers",
        "api",
        "route",
        "routes",
        "handler",
        "handlers",
        "view",
        "views",
        "pages",
        "components",
        "ui",
        # Java/Spring 常用
        "rest",
        "web",
    },
    "application": {
        "service",
        "services",
        "usecase",
        "usecases",
        "application",
        "app",
        "logic",
        # 常见的“业务”层别名
        "biz",
        "business",
    },
    "domain": {
        "domain",
        "model",
        "models",
        "entity",
        "entities",
        "schema",
        "schemas",
        "dto",
        "dtos",
        "core",
        # DDD 常见
        "aggregate",
        "aggregates",
        "vo",
        "valueobject",
        "valueobjects",
    },
    "data": {
        "repository",
        "repositories",
        "dao",
        "daos",
        "store",
        "stores",
        "persistence",
        "db",
        "database",
        "infra",
        # Java 常见
        "mapper",
        "mappers",
    },
}

# 语言偏好的额外目录别名（在通用规则之上补充）。
LANGUAGE_CORE_LAYER_RULES: Dict[str, Dict[str, Set[str]]] = {
    "python": {
        "presentation": {"routers", "endpoints", "blueprints"},
        "application": {"biz", "business"},
        "domain": {"serializers"},
        "data": {"orm", "migrations"},
    },
    "javascript": {
        "presentation": {"controllers", "routes", "middleware"},
        "application": {"services", "usecases"},
        "domain": {"models", "schemas"},
        "data": {"repositories", "db", "prisma"},
    },
    "typescript": {
        "presentation": {"controllers", "routes", "resolvers"},
        "application": {"services", "usecases"},
        "domain": {"entities", "models", "types"},
        "data": {"repositories", "db", "prisma", "typeorm"},
    },
    "java": {
        # 允许 presentation 等“抽象层名”缺失，直接出现 controller/service/entity/repository
        "presentation": {"controller", "controllers", "presentation", "web", "rest"},
        "application": {"service", "services", "application", "app", "usecase", "usecases"},
        "domain": {"entity", "entities", "domain", "model", "models", "dto", "dtos"},
        "data": {"repository", "repositories", "dao", "mapper", "mappers", "infra", "persistence"},
    },
    "frontend": {
        "presentation": {"pages", "components", "views", "layouts"},
        "application": {"composables", "hooks", "store", "stores"},
        "domain": {"models", "schemas", "types"},
        "data": {"api", "services", "repositories"},
    },
}

AUX_LAYER_RULES: Dict[str, Set[str]] = {
    "config": {"config", "configs", "setting", "settings"},
    "tests": {"test", "tests", "__tests__", "spec", "specs"},
}

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".cs",
    ".rb",
    ".php",
    ".vue",
}


@dataclass
class ArchitectureValidationResult:
    is_valid: bool
    reasons: List[str]
    detected_layers: Dict[str, List[str]]
    code_file_count: int
    primary_language: str


def list_delivery_files(output_dir: Path) -> List[str]:
    if not output_dir.is_dir():
        return []
    return sorted(
        [
            p.relative_to(output_dir).as_posix()
            for p in output_dir.rglob("*")
            if p.is_file()
        ]
    )


def _is_code_file(path: str) -> bool:
    return Path(path).suffix.lower() in CODE_EXTENSIONS


def _find_matched_layers(path: str, layer_rules: Dict[str, Set[str]]) -> Set[str]:
    tokens = [seg.lower() for seg in Path(path).parts]
    matched: Set[str] = set()
    for layer, aliases in layer_rules.items():
        if any(token in aliases for token in tokens):
            matched.add(layer)
    return matched


def _detect_primary_language(files: List[str]) -> str:
    counts: Dict[str, int] = {}
    for file_path in files:
        ext = Path(file_path).suffix.lower()
        language = LANGUAGE_BY_EXT.get(ext)
        if not language:
            continue
        counts[language] = counts.get(language, 0) + 1
    if not counts:
        return "generic"
    return max(counts.items(), key=lambda item: item[1])[0]


def _merge_layer_rules(language: str) -> Dict[str, Set[str]]:
    merged = {
        layer: set(aliases) for layer, aliases in GENERIC_CORE_LAYER_RULES.items()
    }
    extra = LANGUAGE_CORE_LAYER_RULES.get(language, {})
    for layer, aliases in extra.items():
        merged.setdefault(layer, set()).update(aliases)
    return merged


def validate_layered_architecture(files: List[str]) -> ArchitectureValidationResult:
    normalized = [f.replace("\\", "/") for f in files]
    code_files = [f for f in normalized if _is_code_file(f)]
    reasons: List[str] = []
    primary_language = _detect_primary_language(code_files)
    core_layer_rules = _merge_layer_rules(primary_language)

    detected_layers: Dict[str, List[str]] = {
        "presentation": [],
        "application": [],
        "domain": [],
        "data": [],
        "config": [],
        "tests": [],
    }

    for file_path in normalized:
        for layer in _find_matched_layers(file_path, core_layer_rules):
            detected_layers[layer].append(file_path)
        for layer in _find_matched_layers(file_path, AUX_LAYER_RULES):
            detected_layers[layer].append(file_path)

    if len(code_files) < 3:
        reasons.append("代码文件数量不足，疑似单文件或极简结构。")

    # 对不同技术栈使用不同的“多目录分布”判断标准
    nested_code_files = [p for p in code_files if "/" in p]

    # Java 常见目录：src/main/java/com/... 通常会导致很深的包路径；这种情况下只要存在
    # 典型 Maven/Gradle 结构 & 至少一个包目录，就认为有体现层级。
    if primary_language == "java":
        has_maven_like_root = any(
            p.startswith("src/main/java/") or p.startswith("src/test/java/")
            for p in code_files
        )
        has_package_path = any(
            p.startswith("src/main/java/") and len(Path(p).parts) >= 6
            for p in code_files
        )
        has_multi_dir_distribution = (
            len({Path(p).parent.as_posix() for p in code_files}) >= 2
        )
        if not (has_maven_like_root and (has_package_path or has_multi_dir_distribution)):
            reasons.append(
                "Java 项目缺少典型 src/main/java 或包路径层级，未体现多目录结构。"
            )
    else:
        if len(nested_code_files) < 2:
            reasons.append("缺少多目录代码分布，未体现分层目录结构。")

    core_layer_count = sum(1 for layer in core_layer_rules if detected_layers[layer])
    if core_layer_count < 3:
        reasons.append(
            "核心分层不足：至少需要 presentation/application/domain/data 中的 3 类。"
        )

    if not detected_layers["tests"]:
        reasons.append("缺少 tests 目录或测试文件。")

    has_readme = any(
        Path(f).name.lower() in {"readme.md", "user_guide.md"} for f in normalized
    )
    if not has_readme:
        reasons.append("缺少 README.md 或 USER_GUIDE.md。")

    is_valid = len(reasons) == 0
    return ArchitectureValidationResult(
        is_valid=is_valid,
        reasons=reasons,
        detected_layers=detected_layers,
        code_file_count=len(code_files),
        primary_language=primary_language,
    )


def build_layered_architecture_fix_prompt(
    result: ArchitectureValidationResult, output_dir: Path
) -> str:
    reason_lines = "\n".join([f"- {r}" for r in result.reasons])

    return f"""【架构校验未通过】
你当前交付未满足分层架构要求，请立即修复并重新交付。

未通过原因：
{reason_lines}

识别到的主要语言/技术栈：{result.primary_language}

强制要求：
1. 必须采用分层目录结构，不允许单文件实现。
2. 至少包含 presentation/application/domain/data 中的 3 层（按当前语言惯例命名即可）。
3. 必须包含 tests 目录及测试代码。
4. 必须包含 README.md 或 USER_GUIDE.md。
5. 每个文件独立代码块输出，并明确文件路径。
6. 所有文件必须写入目录：{output_dir}

请先输出项目目录树，再输出每个文件的完整代码，最后给运行与测试命令。"""
