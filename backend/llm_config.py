"""Runtime configuration and health checks for LLM providers."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from backend.config import PROJECT_ROOT

LLM_CONFIG_PATH = Path(os.environ.get("LLM_CONFIG_PATH", PROJECT_ROOT / "llm_config.json"))


def _env_default_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("MODELSCOPE_ACCESS_TOKEN") or ""


def _env_default_base_url() -> str:
    return os.environ.get("OPENAI_BASE_URL") or os.environ.get("BASE_URL") or "https://api-inference.modelscope.cn/v1/"


def _env_default_model() -> str:
    return os.environ.get("OPENAI_MODEL") or os.environ.get("MODEL") or "deepseek-ai/DeepSeek-V3.2"


def default_llm_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "default_provider": os.environ.get("LLM_PROVIDER", "modelscope"),
        "default_language": os.environ.get("LLM_LANGUAGE", "zh"),
        "temperature": float(os.environ.get("LLM_TEMPERATURE", "0.2")),
        "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "512")),
        "timeout_seconds": int(os.environ.get("LLM_TIMEOUT_SECONDS", "60")),
        "retry_count": int(os.environ.get("LLM_RETRY_COUNT", "1")),
        "modelscope": {
            "api_key": _env_default_api_key(),
            "base_url": _env_default_base_url(),
            "model": _env_default_model(),
        },
        "ollama": {
            "host": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            "model": os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
            "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "5m"),
        },
        "local": {
            "model_path": os.environ.get(
                "LOCAL_LLM_MODEL_PATH",
                "./Qwen2.5-7B-Instruct/Qwen/Qwen2___5-7B-Instruct",
            ),
            "device_map": os.environ.get("LOCAL_LLM_DEVICE_MAP", "auto"),
            "torch_dtype": os.environ.get("LOCAL_LLM_TORCH_DTYPE", "float16"),
        },
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = _deep_merge(default_llm_config(), config)
    if normalized["default_provider"] not in {"modelscope", "ollama", "local"}:
        normalized["default_provider"] = "modelscope"
    if normalized["default_language"] not in {"zh", "en"}:
        normalized["default_language"] = "zh"
    normalized["temperature"] = max(0.0, min(float(normalized["temperature"]), 2.0))
    normalized["max_tokens"] = max(64, int(normalized["max_tokens"]))
    normalized["timeout_seconds"] = max(5, int(normalized["timeout_seconds"]))
    normalized["retry_count"] = max(0, min(int(normalized["retry_count"]), 5))
    return normalized


def load_llm_config() -> dict[str, Any]:
    if not LLM_CONFIG_PATH.exists():
        return _normalize_config({})
    try:
        saved = json.loads(LLM_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        saved = {}
    return _normalize_config(saved)


def public_llm_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    data = copy.deepcopy(config or load_llm_config())
    api_key = data.get("modelscope", {}).get("api_key", "")
    data.setdefault("modelscope", {})
    data["modelscope"]["api_key"] = ""
    data["modelscope"]["api_key_set"] = bool(api_key)
    return data


def save_llm_config(payload: dict[str, Any]) -> dict[str, Any]:
    current = load_llm_config()
    incoming_modelscope = payload.get("modelscope", {})
    if isinstance(incoming_modelscope, dict) and incoming_modelscope.get("api_key", None) == "":
        incoming_modelscope = dict(incoming_modelscope)
        incoming_modelscope["api_key"] = current.get("modelscope", {}).get("api_key", "")
        payload = dict(payload)
        payload["modelscope"] = incoming_modelscope

    next_config = _normalize_config(_deep_merge(current, payload))
    LLM_CONFIG_PATH.write_text(
        json.dumps(next_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return public_llm_config(next_config)


def resolve_llm_config(provider: str | None = None) -> tuple[str, dict[str, Any], dict[str, Any]]:
    config = load_llm_config()
    active_provider = provider or config.get("default_provider", "modelscope")
    if active_provider not in {"modelscope", "ollama", "local"}:
        raise ValueError(f"Unknown LLM provider: {active_provider}")
    return active_provider, config, config[active_provider]


def test_llm_provider(provider: str | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    base_config = load_llm_config()
    if overrides:
        incoming_modelscope = overrides.get("modelscope", {})
        if isinstance(incoming_modelscope, dict) and incoming_modelscope.get("api_key", None) == "":
            incoming_modelscope = dict(incoming_modelscope)
            incoming_modelscope["api_key"] = base_config.get("modelscope", {}).get("api_key", "")
            overrides = dict(overrides)
            overrides["modelscope"] = incoming_modelscope
        base_config = _normalize_config(_deep_merge(base_config, overrides))
    active_provider = provider or base_config.get("default_provider", "modelscope")

    try:
        if active_provider == "modelscope":
            settings = base_config["modelscope"]
            if not settings.get("api_key"):
                raise ValueError("API key is empty.")
            client = OpenAI(
                api_key=settings["api_key"],
                base_url=settings["base_url"],
                timeout=base_config["timeout_seconds"],
            )
            client.chat.completions.create(
                model=settings["model"],
                messages=[{"role": "user", "content": "Reply with OK."}],
                temperature=base_config["temperature"],
                max_tokens=16,
                stream=False,
            )
            return {"ok": True, "provider": active_provider, "message": "ModelScope API connection succeeded."}

        if active_provider == "ollama":
            import ollama

            settings = base_config["ollama"]
            client = ollama.Client(host=settings["host"])
            client.show(settings["model"])
            return {"ok": True, "provider": active_provider, "message": "Ollama model is available."}

        if active_provider == "local":
            settings = base_config["local"]
            model_path = Path(settings["model_path"])
            if not model_path.is_absolute():
                model_path = PROJECT_ROOT / model_path
            if not model_path.exists():
                raise FileNotFoundError(f"Local model path does not exist: {model_path}")
            import torch  # noqa: F401
            import transformers  # noqa: F401

            return {"ok": True, "provider": active_provider, "message": "Local model files and Python packages are available."}

        raise ValueError(f"Unknown LLM provider: {active_provider}")
    except Exception as exc:
        return {"ok": False, "provider": active_provider, "message": str(exc)}
