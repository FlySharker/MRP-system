"""Analysis helpers used by the API layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from backend.data_local_window import (
    SELECT_COLUMNS,
    collect_shortage_intervals,
    compute_inventory,
    compute_local_safety_stock_series,
    parse_window,
    compute_local_safety_stock_series_time_window,
    interval_to_date_ranges,
    rule_demand_spike,
    rule_demand_spike_time_window,
    rule_fluctuation,
    rule_gradual_shortage,
    rule_late_matching,
    plot_inventory_and_safety_stock_with_intervals,
    compute_inventory_risk_score,
    classify_risk_level
)


@dataclass
class AnalysisConfig:
    window_size: int = 5
    time_window_size: str = "14D"
    quantile: float = 0.75
    min_interval_len: int = 1


class AnalysisService:
    def __init__(self, config: AnalysisConfig | None = None) -> None:
        self.config = config or AnalysisConfig()

    def analyze_single(self, material: str, group: pd.DataFrame) -> dict[str, Any]:
        group = group[SELECT_COLUMNS].copy()
        if len(group) <= 1:
            return {
                "material": material,
                "status": "error",
                "error_message": "数据量不足，无法分析",
            }
        
        time_window_size = parse_window(self.config.time_window_size)
        safety_stock_series = compute_local_safety_stock_series_time_window(
            group,
            window_size=time_window_size,
            quantile=self.config.quantile,
        )
        
        # safety_stock_series = compute_local_safety_stock_series(
        #     group,
        #     window_size=self.config.window_size,
        #     quantile=self.config.quantile,
        # )
        
        inventory = compute_inventory(group)

        intervals = collect_shortage_intervals(
            inventory,
            safety_stock_series,
            min_interval_len=self.config.min_interval_len,
        )
        
        risk_score = compute_inventory_risk_score(
            inventory=inventory,
            safety_stock=safety_stock_series,
            dates=group["mrp_element_receipt_or_requirement_date"],
            intervals=intervals
        )

        risk_level = classify_risk_level(risk_score)
        
        interval_ranges = interval_to_date_ranges(group, intervals)
        is_normal = len(intervals) == 0

        html_figure = plot_inventory_and_safety_stock_with_intervals(
            group, inventory, safety_stock_series, intervals, material
        )

        result: dict[str, Any] = {
            "material": material,
            "status": "normal" if is_normal else "anomaly",
            "safety_stock_series": safety_stock_series,
            "inventory": inventory,
            "intervals": intervals,
            "interval_ranges": interval_ranges,
            "Normal": is_normal,
            "rules": {},
            "HtmlFigure": html_figure,
            "risk_score": round(risk_score, 4),
            "risk_level": risk_level,
        }

        if is_normal:
            return result

        late_flag, delays = rule_late_matching(group)
        rules_result = {
            "gradual_shortage": rule_gradual_shortage(
                inventory,
                safety_stock_series,
                dates=group["mrp_element_receipt_or_requirement_date"],
            ),
            "fluctuation": rule_fluctuation(
                inventory,
                safety_stock_series,
                dates=group["mrp_element_receipt_or_requirement_date"],
            ),
            # "demand_spike": rule_demand_spike(
            #     group,
            #     window_size=self.config.window_size,
            #     dates=group["mrp_element_receipt_or_requirement_date"],
            # ),
            "demand_spike": rule_demand_spike_time_window(
                group,
                window_size=time_window_size,
            ),
            "toolate": late_flag,
            "delay_steps": delays,
        }
        result["rules"] = rules_result
        result.update(rules_result)
        return result
