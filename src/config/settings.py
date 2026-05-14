"""Runtime settings and LLM configuration loader."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().strip('"').strip("'")


@dataclass
class LLMSettings:
    """Normalized LLM configuration used by AutoGen agents."""

    config_list: List[Dict[str, Any]]
    stream: bool
    cache_seed: int = 42
    temperature: float = 0.7
    timeout: int = 120

    def to_llm_config(self) -> Dict[str, Any]:
        return {
            "config_list": self.config_list,
            "cache_seed": self.cache_seed,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "stream": self.stream,
        }


def load_llm_settings() -> LLMSettings:
    """Load LLM settings from environment variables with basic validation."""

    use_local_llm = _env_bool("USE_LOCAL_LLM", False)
    stream_enabled = _env_bool("AUTOGEN_STREAM", False)

    if use_local_llm:
        local_model = os.getenv("LOCAL_LLM_MODEL", "deepseek-r1:latest")
        local_base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
        local_api_key = os.getenv("LOCAL_LLM_API_KEY", "ollama")

        config_list = [
            {
                "model": local_model,
                "api_key": local_api_key,
                "base_url": local_base_url,
            }
        ]
    else:
        deepseek_api_key = _env_str("DEEPSEEK_API_KEY")
        if not deepseek_api_key:
            raise ValueError("云端模式下 .env 文件中未找到 DEEPSEEK_API_KEY。")

        model_name = _env_str("DEEPSEEK_MODEL", "deepseek-coder")
        base_url = _env_str(
            "DEEPSEEK_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        config_list = [
            {
                "model": model_name,
                "api_key": deepseek_api_key,
                "base_url": base_url,
            }
        ]

    # Allow runtime override for request timeout (seconds)
    timeout_env = os.getenv("LLM_TIMEOUT")
    try:
        timeout_val = (
            int(timeout_env)
            if timeout_env is not None and timeout_env.strip() != ""
            else 120
        )
    except ValueError:
        timeout_val = 120

    return LLMSettings(
        config_list=config_list, stream=stream_enabled, timeout=timeout_val
    )


# Eagerly load settings for convenient imports (llm_settings / llm_config).
llm_settings: LLMSettings = load_llm_settings()
llm_config: Dict[str, Any] = llm_settings.to_llm_config()


def patch_autogen_streaming_token_count() -> None:
    """Avoid stream-mode crash when provider model name is unknown to AutoGen token counter."""

    import autogen.oai.client as oai_client

    if getattr(oai_client, "_llm_stream_patch_applied", False):
        return

    original_count_token = oai_client.count_token

    def safe_count_token(messages, model=""):
        try:
            return original_count_token(messages, model=model)
        except NotImplementedError:
            return 0

    oai_client.count_token = safe_count_token
    oai_client._llm_stream_patch_applied = True


__all__ = [
    "LLMSettings",
    "load_llm_settings",
    "llm_settings",
    "llm_config",
    "patch_autogen_streaming_token_count",
]
