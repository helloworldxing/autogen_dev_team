from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set


@dataclass(frozen=True)
class StackPolicy:
    stack_type: str
    backend_language: str
    frontend_language: str
    default_code_extension: str
    allowed_extensions: Set[str]
    guidance: str


DEFAULT_STACK_POLICY_RULES: Dict[str, Any] = {
    "common_extensions": [
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".env",
        ".sql",
        ".xml",
        ".properties",
        ".sh",
        ".bat",
        ".dockerfile",
    ],
    "backend_extensions": {
        "python": [".py"],
        "java": [".java", ".kt"],
        "typescript": [".ts", ".js"],
    },
    "frontend_extensions": [".ts", ".tsx", ".js", ".jsx", ".vue", ".css", ".scss", ".html"],
    "language_aliases": {
        "python": ["python", "py", "fastapi", "flask", "django"],
        "java": ["java", "spring", "spring boot", "maven", "gradle", "mybatis", "jpa"],
        "typescript": ["typescript", "ts", "node", "nestjs", "express", "next.js", "nextjs"],
        "javascript": ["javascript", "js", "react", "vue", "angular"],
    },
    "profiles": [
        {
            "id": "java_spring_maven",
            "priority": 120,
            "stack_type": "backend",
            "backend_language": "java",
            "frontend_language": "javascript",
            "default_code_extension": ".java",
            "keywords_all": ["java"],
            "keywords_any": ["spring", "spring boot", "maven", "gradle", "mybatis", "jpa"],
            "guidance": "后端项目（Java/Spring/Maven 模板）。请输出 controller/service/entity/repository 分层，并包含 pom.xml 或 build.gradle。",
        },
        {
            "id": "python_fastapi",
            "priority": 110,
            "stack_type": "backend",
            "backend_language": "python",
            "frontend_language": "javascript",
            "default_code_extension": ".py",
            "keywords_any": ["python", "fastapi", "flask", "django", "pytest"],
            "guidance": "后端项目（Python/FastAPI 模板）。请输出 routers/services/models/repositories 分层，并包含 requirements 或 pyproject 配置。",
        },
        {
            "id": "fullstack_java_vue",
            "priority": 200,
            "stack_type": "fullstack",
            "backend_language": "java",
            "frontend_language": "javascript",
            "default_code_extension": ".java",
            "keywords_all": ["java", "vue"],
            "keywords_any": ["全栈", "fullstack", "前后端"],
            "guidance": "全栈项目（Java + Vue 模板）。后端按 Java 分层，前端按 Vue 分层，允许 .xml/.yml/.sql。",
        },
        {
            "id": "generic_fullstack",
            "priority": 90,
            "stack_type": "fullstack",
            "backend_language": "python",
            "frontend_language": "javascript",
            "default_code_extension": ".py",
            "keywords_any": ["fullstack", "全栈", "前后端"],
            "guidance": "全栈项目通用模板。后端与前端均需分层，允许多语言配置文件。",
        },
        {
            "id": "generic_frontend",
            "priority": 80,
            "stack_type": "frontend",
            "backend_language": "python",
            "frontend_language": "javascript",
            "default_code_extension": ".js",
            "keywords_any": ["frontend", "前端", "页面", "组件", "react", "vue", "angular", "ui"],
            "guidance": "前端项目模板。请输出 pages/components/store(api) 等分层结构。",
        },
        {
            "id": "default_backend_python",
            "priority": 10,
            "stack_type": "backend",
            "backend_language": "python",
            "frontend_language": "javascript",
            "default_code_extension": ".py",
            "keywords_any": [],
            "guidance": "后端项目（主语言：python），请按后端分层输出。",
        },
    ],
}


def _normalize_ext(ext: str) -> str:
    return ext if ext.startswith(".") else f".{ext}"


def _contains_all(text: str, keywords: List[str]) -> bool:
    if not keywords:
        return True
    return all(k.lower() in text for k in keywords)


def _contains_any(text: str, keywords: List[str]) -> bool:
    if not keywords:
        return True
    return any(k.lower() in text for k in keywords)


def _load_rules() -> Dict[str, Any]:
    configured = os.getenv("STACK_POLICY_RULES_PATH", "").strip()
    if configured:
        candidate = Path(configured)
    else:
        candidate = Path(__file__).resolve().parents[1] / "config" / "stack_policy_rules.json"

    if candidate.is_file():
        try:
            content = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(content, dict):
                return content
        except Exception:
            return DEFAULT_STACK_POLICY_RULES

    return DEFAULT_STACK_POLICY_RULES


def _detect_explicit_languages(
    text: str, language_aliases: Dict[str, List[str]]
) -> Set[str]:
    detected: Set[str] = set()
    for language, aliases in language_aliases.items():
        if any(str(alias).lower() in text for alias in aliases):
            detected.add(str(language).lower())
    return detected


def infer_stack_policy(task: str) -> StackPolicy:
    text = task.lower()
    rules = _load_rules()
    profiles = rules.get("profiles", [])
    common_ext = {_normalize_ext(e).lower() for e in rules.get("common_extensions", [])}
    backend_ext_map = {
        str(lang).lower(): {_normalize_ext(e).lower() for e in exts}
        for lang, exts in rules.get("backend_extensions", {}).items()
        if isinstance(exts, list)
    }
    frontend_ext = {
        _normalize_ext(e).lower() for e in rules.get("frontend_extensions", [])
    }
    language_aliases = {
        str(language).lower(): [str(alias).lower() for alias in aliases]
        for language, aliases in rules.get("language_aliases", {}).items()
        if isinstance(aliases, list)
    }

    matched_profiles: List[Dict[str, Any]] = []
    for profile in profiles:
        keywords_all = [str(k).lower() for k in profile.get("keywords_all", [])]
        keywords_any = [str(k).lower() for k in profile.get("keywords_any", [])]
        if not _contains_all(text, keywords_all):
            continue
        if not _contains_any(text, keywords_any):
            continue
        matched_profiles.append(profile)

    if matched_profiles:
        selected = max(
            matched_profiles,
            key=lambda p: (
                int(p.get("priority", 0)),
                len(p.get("keywords_all", [])) + len(p.get("keywords_any", [])),
            ),
        )
    else:
        selected = {
            "stack_type": "backend",
            "backend_language": "python",
            "frontend_language": "javascript",
            "default_code_extension": ".py",
            "guidance": "后端项目（主语言：python），请按后端分层输出。",
        }

    stack_type = str(selected.get("stack_type", "backend")).lower()
    backend_lang = str(selected.get("backend_language", "python")).lower()
    frontend_lang = str(selected.get("frontend_language", "javascript")).lower()
    default_ext = _normalize_ext(str(selected.get("default_code_extension", ".py"))).lower()
    guidance = str(selected.get("guidance", "请按分层结构输出项目。"))

    explicit_languages = _detect_explicit_languages(text, language_aliases)
    explicit_backend_order = ["java", "python", "typescript", "javascript"]
    explicit_backend = next(
        (
            lang
            for lang in explicit_backend_order
            if lang in explicit_languages and lang in backend_ext_map
        ),
        "",
    )
    if explicit_backend:
        backend_lang = explicit_backend
        backend_defaults = sorted(backend_ext_map.get(backend_lang, {default_ext}))
        default_ext = backend_defaults[0] if backend_defaults else default_ext
        guidance = (
            f"{guidance}（检测到用户显式指定后端语言：{backend_lang}，已按用户指定强制覆盖默认语言）"
        )

    if "typescript" in explicit_languages:
        frontend_lang = "typescript"
    elif "javascript" in explicit_languages:
        frontend_lang = "javascript"

    if stack_type == "frontend":
        allowed = common_ext | frontend_ext
    elif stack_type == "fullstack":
        allowed = common_ext | frontend_ext | backend_ext_map.get(backend_lang, {default_ext})
    else:
        allowed = common_ext | backend_ext_map.get(backend_lang, {default_ext})
        allowed.add(default_ext)

    return StackPolicy(
        stack_type=stack_type,
        backend_language=backend_lang,
        frontend_language=frontend_lang,
        default_code_extension=default_ext,
        allowed_extensions={e.lower() for e in allowed},
        guidance=guidance,
    )
