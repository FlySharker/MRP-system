"""Backend-facing services for the Next.js API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any

import pandas as pd

from backend.analysis import AnalysisConfig, AnalysisService
from backend.anomaly_reason import analyze_with_llm
from backend.config import DATA_PATH
from backend.data_local_window import build_results, build_summary_frame, load_data, parse_window
from backend.forecast import ForecastConfig, build_forecast_payload


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = normalized.columns.map(lambda col: str(col).strip())
    return normalized


def _find_column(df: pd.DataFrame, *candidates: str) -> str:
    normalized_map = {
        str(column).strip().casefold().replace("_", " ").replace("-", " "): str(column)
        for column in df.columns
    }
    for candidate in candidates:
        key = candidate.strip().casefold().replace("_", " ").replace("-", " ")
        if key in normalized_map:
            return normalized_map[key]
    raise KeyError(candidates[0])


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _serialize_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {key: _serialize_value(val) for key, val in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _build_chart_series(
    group: pd.DataFrame,
    inventory: list[float],
    safety_stock: list[float],
) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for row, inv, stock in zip(group.to_dict(orient="records"), inventory, safety_stock):
        series.append(
            {
                "date": _serialize_value(row["mrp_element_receipt_or_requirement_date"]),
                "event": row["Mrp Element Short Name"],
                "qty": _serialize_value(row["Qty"]),
                "inventory": _serialize_value(inv),
                "safetyStock": _serialize_value(stock),
            }
        )
    return series


@dataclass
class BackendConfig:
    data_path: str | None = None


class AnalysisHistoryStore:
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []
        self._lock = Lock()

    def add(self, result: dict[str, Any]) -> None:
        entry = {
            "material": result.get("material"),
            "status": result.get("status"),
            "llm_label": result.get("llm_label", result.get("llmLabel")),
            "analyzed_at": datetime.now().isoformat(timespec="milliseconds"),
        }
        with self._lock:
            self._items.append(entry)
            self._items = self._items[-50:]

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._items[-limit:]))


class BackendService:
    def __init__(self, config: BackendConfig | None = None) -> None:
        self.config = config or BackendConfig()
        self.data_path = self.config.data_path or DATA_PATH
        self.history = AnalysisHistoryStore()
        self._data_cache: pd.DataFrame | None = None
        self._data_lock = Lock()

    def get_data(self) -> pd.DataFrame:
        with self._data_lock:
            if self._data_cache is None:
                if not self.data_path:
                    return pd.DataFrame()
                try:
                    self._data_cache = _normalize_columns(load_data(self.data_path))
                except Exception:
                    return pd.DataFrame()
            return _normalize_columns(self._data_cache)

    def set_data(self, df: pd.DataFrame):
        """用上传的数据替换原始数据"""
        with self._data_lock:
            self._data_cache = _normalize_columns(df)

    def get_materials(self, query: str = "", limit: int = 20) -> list[str]:
        df = self.get_data()
        if df.empty:
            return []
        material_col = _find_column(df, "Material Number", "material number", "material")
        materials = df[material_col].dropna().astype(str).unique().tolist()
        if query:
            lowered = query.lower()
            materials = [material for material in materials if lowered in material.lower()]
        return materials[:limit]

    def get_overview(self) -> dict[str, Any]:
        
        df = self.get_data()
        
        if df.empty:
            return {
                "materialsCount": 0,
                "recordsCount": 0,
                "plantsCount": 0,
                "dateRange": {"start": None, "end": None},
                "recentHistory": self.history.list_recent(),
            }
        
        material_col = _find_column(df, "Material Number", "material number", "material")
        materials = df[material_col].dropna().astype(str).unique().tolist()
        return {
            "materialsCount": len(materials),
            "recordsCount": int(len(df)),
            "plantsCount": int(df["plant_id"].nunique()),
            "dateRange": {
                "start": _serialize_value(df["mrp_element_receipt_or_requirement_date"].min()),
                "end": _serialize_value(df["mrp_element_receipt_or_requirement_date"].max()),
            },
            "recentHistory": self.history.list_recent(),
        }

    def analyze_material(
        self,
        material: str,
        analysis_config: AnalysisConfig,
        include_llm: bool = True,
        language: str = "en",
        llm_provider: str = "modelscope",
    ) -> dict[str, Any]:
        df = self.get_data()
        if df.empty:
            return {
                "material": material,
                "status": "error",
                "error_message": "当前未加载数据，请先上传数据文件。",
            }
        try:
            material_col = _find_column(df, "Material Number", "material number", "material")
        except KeyError:
            return {
                "material": material,
                "status": "error",
                "error_message": "数据缺少 Material Number 字段，请检查上传文件。",
            }
        group = (
            df[df[material_col].astype(str) == str(material)]
            .sort_values("mrp_element_receipt_or_requirement_date")
            .copy()
        )
        if len(group) <= 1:
            return {
                "material": material,
                "status": "error",
                "error_message": "未找到材料的有效数据，请检查材料编号是否正确。",
            }

        result = AnalysisService(analysis_config).analyze_single(material, group)
        html_figure = result.get("HtmlFigure", "")
        # print(html_figure)
        # llm_output = "库存状态正常，无需LLM深度分析。"
        llm_output = None
        llm_label = 0 if result.get("status") == "normal" else None
        llm_recommendation = ""

        if include_llm and result.get("status") == "anomaly":
            group_for_llm = group.copy()
            group_for_llm["local_safety_stock"] = result.get("safety_stock_series", [])
            group_for_llm["inventory"] = result.get("inventory", [])
            llm_result = analyze_with_llm(result, group_for_llm, language=language, provider=llm_provider)
            llm_output = llm_result.get("llm_output_raw") or llm_result.get("error", "")
            llm_label = llm_result.get("llm_label")
            llm_recommendation = llm_result.get("llm_recommendation", "")

        time_window_size = parse_window(analysis_config.time_window_size)
        payload = {
            "material": result.get("material"),
            "status": result.get("status"),
            "error_message": result.get("error_message"),
            "intervals": result.get("intervals", []),
            "intervalRanges": [
                {
                    "start_idx": interval["start_idx"],
                    "end_idx": interval["end_idx"],
                    "start_date": _serialize_value(interval["start_date"]),
                    "end_date": _serialize_value(interval["end_date"]),
                }
                for interval in result.get("interval_ranges", [])
            ],
            "risk_score": result.get("risk_score"),
            "risk_level": result.get("risk_level"),
            "rules": {
                "gradual_shortage": result.get("gradual_shortage", False),
                "fluctuation": result.get("fluctuation", False),
                "demand_spike": result.get("demand_spike", False),
                "toolate": result.get("toolate", False),
                "delay_steps": [_serialize_value(x) for x in result.get("delay_steps", [])],
            },
            "chartSeries": _build_chart_series(
                group,
                result.get("inventory", []),
                result.get("safety_stock_series", []),
            ),
            "llmOutput": llm_output,
            "llmLabel": llm_label,
            "llmRecommendation": llm_recommendation,
            "config": {
                # "windowSize": analysis_config.window_size,
                "windowSize": time_window_size,
                "quantile": analysis_config.quantile,
                "minIntervalLen": analysis_config.min_interval_len,
            },
            "HtmlFigure": html_figure,
        }
        if payload["status"] != "error":
            self.history.add(payload)
        return payload

    def analyze_batch(
        self,
        material_prefix: str,
        statuses: list[str],
        max_materials: int,
        analysis_config: AnalysisConfig,
    ) -> dict[str, Any]:
        df = self.get_data()
        if df.empty:
            return {
                "metrics": {"total": 0, "normal": 0, "anomaly": 0, "riskRatio": 0},
                "reasonCounts": {
                    "delayedSupply": 0,
                    "demandSpike": 0,
                    "fluctuation": 0,
                    "gradualShortage": 0,
                },
                "summary": [],
                "history": self.history.list_recent(),
                "results": [],
            }
        try:
            material_col = _find_column(df, "Material Number", "material number", "material")
        except KeyError:
            return {
                "metrics": {"total": 0, "normal": 0, "anomaly": 0, "riskRatio": 0},
                "reasonCounts": {
                    "delayedSupply": 0,
                    "demandSpike": 0,
                    "fluctuation": 0,
                    "gradualShortage": 0,
                },
                "summary": [],
                "history": self.history.list_recent(),
                "results": [],
            }
        if material_prefix and material_prefix != "全部":
            df = df[df[material_col].astype(str).str.startswith(material_prefix)]
        
        time_window_size = parse_window(analysis_config.time_window_size)
        results = build_results(
            df=df,
            window_size=time_window_size,
            quantile=analysis_config.quantile,
            max_materials=max_materials if max_materials > 0 else None,
            min_interval_len=analysis_config.min_interval_len,
            if_plot=False,
            include_llm=False,
        )
        summary_df = build_summary_frame(results)
        summary_df = summary_df.sort_values(
            by="risk_score",
            ascending=False,
        ).reset_index(drop=True)

        if statuses:
            status_map = {"正常": True, "异常": False, "normal": True, "anomaly": False}
            allowed = {status_map[item] for item in statuses if item in status_map}
            summary_df = summary_df[summary_df["Normal"].isin(allowed)] if allowed else summary_df.iloc[0:0]
        else:
            summary_df = summary_df.iloc[0:0]

        total = int(len(summary_df))
        normal_count = int(summary_df["Normal"].sum()) if total else 0
        anomaly_count = total - normal_count
        
        filtered_materials = set(summary_df["material"].astype(str).tolist()) if total else set()
        result_map = {
            str(result.get("material")): result
            for result in results
        }

        filtered_results = [
            result_map[material]
            for material in filtered_materials
            if material in result_map
        ]

        # filtered_results = [
        #     result for result in results if str(result.get("material")) in filtered_materials
        # ]

        return {
            "metrics": {
                "total": total,
                "normal": normal_count,
                "anomaly": anomaly_count,
                "riskRatio": round((anomaly_count / total * 100), 2) if total else 0,
            },
            "reasonCounts": {
                "delayedSupply": sum(1 for result in filtered_results if result.get("toolate")),
                "demandSpike": sum(1 for result in filtered_results if result.get("demand_spike")),
                "fluctuation": sum(1 for result in filtered_results if result.get("fluctuation")),
                "gradualShortage": sum(1 for result in filtered_results if result.get("gradual_shortage")),
            },
            "summary": _serialize_records(summary_df),
            "history": self.history.list_recent(),
            "results": [
                {
                    "material": result.get("material"),
                    "status": "normal" if result.get("Normal") else "anomaly",
                    "risk_score": result.get("risk_score"),
                    "risk_level": result.get("risk_level"),
                    "intervalRanges": [
                        {
                            "start_date": _serialize_value(interval["start_date"]),
                            "end_date": _serialize_value(interval["end_date"]),
                        }
                        for interval in result.get("interval_ranges", [])
                    ],
                    "rules": {
                        "toolate": result.get("toolate", False),
                        "gradual_shortage": result.get("gradual_shortage", False),
                        "fluctuation": result.get("fluctuation", False),
                        "demand_spike": result.get("demand_spike", False),
                    },
                }
                for result in filtered_results
            ],
        }

    def get_key_materials(self, limit: int = 20) -> list[dict[str, Any]]:
        df = self.get_data()
        if df.empty:
            return []

        candidates: list[dict[str, Any]] = []
        try:
            material_col = _find_column(df, "Material Number", "material number", "material")
        except KeyError:
            return []
        for material, group in df.groupby(material_col, sort=False):
            clean_group = group.dropna(subset=["mrp_element_receipt_or_requirement_date"])
            if len(clean_group) <= 1:
                continue

            demand_rows = clean_group[
                clean_group["Mrp Element Short Name"].astype(str).isin(["IndReq", "DepReq", "ResOrd"])
            ]
            demand_volume = float(demand_rows["Qty"].abs().sum()) if not demand_rows.empty else float(clean_group["Qty"].abs().sum())
            candidates.append(
                {
                    "material": str(material),
                    "records": int(len(clean_group)),
                    "demandVolume": round(demand_volume, 2),
                    "lastDate": _serialize_value(clean_group["mrp_element_receipt_or_requirement_date"].max()),
                }
            )

        candidates.sort(key=lambda item: (item["demandVolume"], item["records"]), reverse=True)
        return candidates[:limit]

    def forecast_material(
        self,
        material: str,
        analysis_config: AnalysisConfig,
        forecast_config: ForecastConfig | None = None,
    ) -> dict[str, Any]:
        df = self.get_data()
        if df.empty:
            return {
                "material": material,
                "status": "error",
                "error_message": "当前未加载数据，请先上传数据文件。",
            }
        try:
            material_col = _find_column(df, "Material Number", "material number", "material")
        except KeyError:
            return {
                "material": material,
                "status": "error",
                "error_message": "数据缺少 Material Number 字段，请检查上传文件。",
            }
        group = (
            df[df[material_col].astype(str) == str(material)]
            .sort_values("mrp_element_receipt_or_requirement_date")
            .copy()
        )
        if len(group) <= 1:
            return {
                "material": material,
                "status": "error",
                "error_message": "未找到材料的有效数据，请检查材料编号是否正确。",
            }

        result = AnalysisService(analysis_config).analyze_single(material, group)
        if result.get("status") == "error":
            return {
                "material": material,
                "status": "error",
                "error_message": result.get("error_message", "数据量不足，无法预测。"),
            }

        return build_forecast_payload(
            material=material,
            group=group,
            analysis_result=result,
            analysis_config=analysis_config,
            config=forecast_config,
        )


        
