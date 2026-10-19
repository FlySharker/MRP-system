import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from openai import OpenAI

from backend.config import PROJECT_ROOT
from backend.llm_config import load_llm_config, resolve_llm_config


# ── Lazy-loaded local model (HuggingFace transformers) ──────────────────────
_local_model = None
_local_tokenizer = None
_local_model_cache_key = None


# def _clean_block(text: str) -> str:
#     text = text.strip()

#     # 去 markdown/code残留
#     text = re.sub(r"^```.*?\n|```$", "", text, flags=re.S).strip()

#     # 去最外层 []
#     if text.startswith("[") and text.endswith("]"):
#         text = text[1:-1].strip()

#     return text


def _resolve_local_model_path(raw_path: str) -> Path:
    model_path = Path(raw_path)
    if model_path.is_absolute():
        return model_path
    return PROJECT_ROOT / model_path


def _get_local_model(settings: dict[str, Any]):
    global _local_model, _local_tokenizer, _local_model_cache_key
    model_path = _resolve_local_model_path(
        settings.get("model_path", "./Qwen2.5-7B-Instruct/Qwen/Qwen2___5-7B-Instruct")
    )
    device_map = settings.get("device_map", "auto")
    torch_dtype_name = settings.get("torch_dtype", "float16")
    cache_key = (str(model_path), device_map, torch_dtype_name)

    if _local_model is None or _local_model_cache_key != cache_key:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch

        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
            "auto": "auto",
        }
        model_kwargs = {"device_map": device_map}
        torch_dtype = dtype_map.get(torch_dtype_name)
        if torch_dtype is not None:
            model_kwargs["torch_dtype"] = torch_dtype

        _local_tokenizer = AutoTokenizer.from_pretrained(model_path)
        _local_model = AutoModelForCausalLM.from_pretrained(
            model_path,
            **model_kwargs,
        )
        _local_model_cache_key = cache_key
    return _local_tokenizer, _local_model


def _chat_local(system_prompt: str, user_prompt: str, settings: dict[str, Any], config: dict[str, Any]) -> str:
    tokenizer, model = _get_local_model(settings)
    prompt = system_prompt + "\n" + user_prompt
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=int(config.get("max_tokens", 512)),
        temperature=float(config.get("temperature", 0.2)),
    )
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


# ── Ollama provider ─────────────────────────────────────────────────────────
def _chat_ollama(system_prompt: str, user_prompt: str, settings: dict[str, Any], config: dict[str, Any]) -> str:
    import ollama

    client = ollama.Client(host=settings.get("host", "http://localhost:11434"))
    request = {
        "model": settings.get("model", "qwen2.5:7b"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": float(config.get("temperature", 0.2)),
            "num_predict": int(config.get("max_tokens", 512)),
        },
    }
    if settings.get("keep_alive"):
        request["keep_alive"] = settings["keep_alive"]
    response = client.chat(**request)
    return response["message"]["content"]


# ── ModelScope / OpenAI-compatible provider ──────────────────────────────────
def _chat_modelscope(system_prompt: str, user_prompt: str, settings: dict[str, Any], config: dict[str, Any]) -> str:
    api_key = settings.get("api_key", "")
    base_url = settings.get("base_url", "")
    model_name = settings.get("model", "")

    if not api_key:
        raise ValueError(
            "Missing API key. Configure it in LLM settings or set OPENAI_API_KEY or "
            "MODELSCOPE_ACCESS_TOKEN in the process environment."
        )
    if not base_url:
        raise ValueError(
            "Missing base URL. Configure it in LLM settings or set OPENAI_BASE_URL or "
            "BASE_URL in the process environment."
        )
    if not model_name:
        raise ValueError("Missing model name.")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=int(config.get("timeout_seconds", 60)),
    )
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=float(config.get("temperature", 0.2)),
        max_tokens=int(config.get("max_tokens", 512)),
        stream=False,
    )
    return response.choices[0].message.content


# ── Provider dispatcher ─────────────────────────────────────────────────────
_PROVIDER_MAP = {
    "local": _chat_local,
    "ollama": _chat_ollama,
    "modelscope": _chat_modelscope,
}


def chat(system_prompt: str, user_prompt: str, provider: str = "modelscope") -> str:
    active_provider, config, settings = resolve_llm_config(provider)
    fn = _PROVIDER_MAP.get(active_provider)
    if fn is None:
        raise ValueError(f"Unknown LLM provider: {active_provider}. Available: {list(_PROVIDER_MAP.keys())}")

    attempts = int(config.get("retry_count", 1)) + 1
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return fn(system_prompt, user_prompt, settings, config)
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise RuntimeError("LLM call failed without an exception.")


# ── Prompt builder ───────────────────────────────────────────────────────────
def build_prompt(
    result: dict,
    group: pd.DataFrame,
    language: str = "en",
) -> tuple[str, str]:

    sample_data = group.to_dict(orient="records")

    if language == "zh":
        lang_instruction = "请用中文回答。"
    else:
        lang_instruction = f"Please answer in {language}."

    system_prompt = f"""
    *** Role ***
    You are an expert Supply Chain Analyst and MRP (Material Requirements Planning) specialist.

    *** Task Description ***
    You are designed to analyze whether there are shortages in the inventory based on the MRP data provided.
    If there are shortages, you need to analyze the potential reasons for the shortages.
    The input is a sequence of time-ordered MRP records for a specific material, including the quantity changes, MRP events, and date information.
    Also you have some support and coarse-grained result about the anomaly, based on the hand-crafted rules.
    You need to output the reason for the anomaly in detail.
    You need to output the class label, i.e., an integer in the set {{0, 1}}. 0 represents Normal, and 1 represents Anomaly.

    *** Prompt Questions: ***
    Think through the following questions based on the given MRP data and provide a concise explanation:

    1. Does the inventory fall below the safety stock level for a continuous period? If yes, describe the duration and severity.
    2. Is there a consistent decreasing trend in inventory or an increasing gap between inventory and safety stock?
    3. Are there frequent fluctuations where inventory repeatedly crosses above and below the safety stock level?
    4. Is there any sudden spike in demand compared to recent historical demand levels?
    5. Are there delays in supply arrivals compared to demand timing, leading to unmet demand or late fulfillment?
    6. Are there other abnormal patterns not covered above?
    """

    user_prompt = f"""
    *** MRP Sequence Data: ***
    Data Dictionary:
    - mrp_element_receipt_or_requirement_date: date of the MRP event (receipt or requirement)
    - Mrp Element Short Name: event type (e.g. Stock, Order, IndReq etc.)
    - Qty: quantity of the MRP event (positive for receipt, negative for requirement)
    - local_safety_stock: the local safety stock level for the material
    - inventory: the current inventory level for the material
    {
        json.dumps(sample_data, indent=2, default=str)
    }

    *** Hand-crafted Rule Result: ***
    Definition of the hand-crafted rule result:
    - interval_ranges: list of time intervals where the inventory is below safety stock
    - gradual_shortage: whether there is a consistent decreasing trend in inventory or an increasing gap between inventory and safety stock
    - fluctuation: whether there are frequent fluctuations where inventory repeatedly crosses above and below the safety stock level
    - demand_spike: whether there is any sudden spike in demand compared to recent historical demand
    - toolate: whether there are delays in supply arrivals compared to demand timing, leading to unmet demand or late fulfillment
    - delay_steps: the number of delayed steps in the supply arrivals compared to demand timing
    {
        json.dumps({
            "intervals": result.get("interval_ranges", []),
            "gradual_shortage": result.get("gradual_shortage", False),
            "fluctuation": result.get("fluctuation", False),
            "demand_spike": result.get("demand_spike", False),
            "toolate": result.get("toolate", False),
            "delay_steps": result.get("delay_steps", [])
        }, indent=2, default=str)
    }

    *** OutputLanguage: ***
    {lang_instruction}

    *** Output: ***
    Please give your output strictly in the following format:
    ```
    Reason:
    [
        Please think step by step. You can give your analysis by answering the above questions selectively.
        You should be clear that Your job is NOT to repeat the rules, but to:
        - Form your own judgment
        - Explain the most likely root causes
        - Highlight key patterns in the data

        Avoid rigid question-by-question answers. Do not explicitly mention rule names like "gradual_shortage".
        Focus on a natural, professional diagnostic explanation.
    ]
    Label:
    [ONLY the integer class label; make necessary assumptions if needed]
    Recommendation:
    [
        Provide ONLY 2-4 concise, actionable, and data-grounded recommendations.

        Requirements:
        - Each recommendation must contain:
            * a concrete operational action
            * the target object/event
            * quantitative details
            * the expected benefit

        - Use actual values from the MRP data whenever possible, including:
            * dates
            * quantities
            * inventory levels
            * safety stock levels
            * shortage durations
            * delay durations
            * percentage adjustments

        - Recommendations must directly address the detected root causes.

        - Keep each recommendation within 1 sentence.

        Focus on operational actions such as:
        - expediting delayed supply orders
        - adjusting supply or stock
        - modifying reorder points or lot sizes
        - rescheduling replenishment timing
        - mitigating demand spikes
        - reducing recurring shortages

        Avoid:
        - generic management advice
        - vague suggestions without numbers
        - repeating the analysis
        - unsupported assumptions

        Good recommendation examples:
        - Expedite the purchase order scheduled for 2025-03-18 by 4 days because inventory is projected to stay below the safety stock level of 120 units from 2025-03-14 to 2025-03-20.
        - Increase supply from 150 to 220 units during the next monthly planning cycle to absorb demand spikes exceeding recent averages by approximately 30%.
        - Reduce replenishment lot size from 800 to 500 units and switch to twice-weekly deliveries to stabilize recurring inventory oscillations.
    ]
    ```
    Please ONLY reply according to this format, don't give me any other words. Do NOT wrap Reason or Recommendation content in square brackets [ ].
    """

    return system_prompt, user_prompt


# ── Main analysis entry point ────────────────────────────────────────────────
def analyze_with_llm(
    result: dict,
    group: pd.DataFrame,
    model_name: str | None = None,
    language: str = "en",
    provider: str = "modelscope",
):
    if not load_llm_config().get("enabled", True):
        return {
            "material": result["material"],
            "error": "LLM analysis is disabled in the runtime configuration.",
        }

    system_prompt, user_prompt = build_prompt(result, group, language)

    try:
        content = chat(system_prompt, user_prompt, provider=provider)
        # remove markdown code fences
        content = re.sub(r"```(?:\w+)?", "", content).strip()
        reason = content.strip()
        label = None

        recommendation = ""
        try:
            reason_match = re.search(r"Reason:\s*(.*?)\s*Label:", content, re.S)
            if reason_match:
                # reason = _clean_block(reason_match.group(1).strip())
                reason = reason_match.group(1).strip()

            label_match = re.search(r"Label:\s*(\d+)", content)
            if label_match:
                label = int(label_match.group(1))

            recommendation_match = re.search(r"Recommendation:\s*(.*?)$", content, re.S)
            if recommendation_match:
                # recommendation = _clean_block(recommendation_match.group(1).strip())
                recommendation = recommendation_match.group(1).strip()
        except Exception:
            pass

        return {
            "material": result["material"],
            "llm_output_raw": reason,
            "llm_label": label,
            "llm_recommendation": recommendation,
        }

    except Exception as e:
        return {"material": result["material"], "error": str(e)}
