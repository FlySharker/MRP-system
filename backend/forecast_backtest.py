from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd

from backend.analysis import AnalysisConfig, AnalysisService
from backend.config import DATA_PATH
from backend.forecast import (
    ForecastConfig,
    _extend_safety_stock,
    build_flow_history,
    forecast_series,
)
from backend.service import BackendConfig, BackendService


def _safe_mean(values: list[float]) -> float | None:
    valid = [value for value in values if value is not None and math.isfinite(value)]
    return float(mean(valid)) if valid else None


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator / denominator)


def _compute_wape(actual: list[float], predicted: list[float]) -> float | None:
    numerator = sum(
        abs(actual_val - predicted_val)
        for actual_val, predicted_val in zip(actual, predicted)
        if math.isfinite(actual_val) and math.isfinite(predicted_val)
    )
    denominator = sum(abs(actual_val) for actual_val in actual if math.isfinite(actual_val))
    return _safe_div(numerator, denominator)


def _rolling_backtest_for_material(
    material: str,
    group: pd.DataFrame,
    analysis_config: AnalysisConfig,
    forecast_config: ForecastConfig,
    horizon_weeks: int,
    min_history_weeks: int,
) -> list[dict[str, Any]]:
    analysis_result = AnalysisService(analysis_config).analyze_single(material, group)
    if analysis_result.get("status") == "error":
        return []

    weekly = build_flow_history(
        group,
        analysis_result.get("inventory", []),
        analysis_result.get("safety_stock_series", []),
    )
    if len(weekly) < min_history_weeks + horizon_weeks:
        return []

    diagnostics = dict(weekly.attrs.get("diagnostics", {}))
    rows: list[dict[str, Any]] = []
    for split_end in range(min_history_weeks, len(weekly) - horizon_weeks + 1):
        train = weekly.iloc[:split_end].copy()
        actual = weekly.iloc[split_end : split_end + horizon_weeks].copy()
        if len(actual) < horizon_weeks:
            continue

        inbound_vals, _, _, _, _ = forecast_series(
            train["inbound"],
            forecast_config,
            clip_min=0.0,
        )
        outbound_vals, _, _, _, _ = forecast_series(
            train["outbound"],
            forecast_config,
            clip_min=0.0,
        )
        safety_stock_vals, _, _ = _extend_safety_stock(
            train,
            outbound_vals,
            analysis_config,
        )

        predicted_inventory: list[float] = []
        inventory_state = float(train["inventory"].iloc[-1])
        for idx in range(horizon_weeks):
            inventory_state += inbound_vals[idx] - outbound_vals[idx]
            predicted_inventory.append(float(inventory_state))

        actual_inventory = actual["inventory"].astype(float).tolist()
        actual_safety_stock = actual["safety_stock"].astype(float).tolist()
        actual_shortage = [max(ss - inv, 0.0) for inv, ss in zip(actual_inventory, actual_safety_stock)]
        predicted_shortage = [
            max(ss - inv, 0.0)
            for inv, ss in zip(predicted_inventory, safety_stock_vals[:horizon_weeks])
        ]

        inventory_ae = [
            abs(actual_val - predicted_val)
            for actual_val, predicted_val in zip(actual_inventory, predicted_inventory)
            if math.isfinite(actual_val) and math.isfinite(predicted_val)
        ]
        shortage_ae = [
            abs(actual_val - predicted_val)
            for actual_val, predicted_val in zip(actual_shortage, predicted_shortage)
            if math.isfinite(actual_val) and math.isfinite(predicted_val)
        ]

        tp = sum(1 for a, p in zip(actual_shortage, predicted_shortage) if a > 0 and p > 0)
        fp = sum(1 for a, p in zip(actual_shortage, predicted_shortage) if a <= 0 and p > 0)
        fn = sum(1 for a, p in zip(actual_shortage, predicted_shortage) if a > 0 and p <= 0)
        tn = sum(1 for a, p in zip(actual_shortage, predicted_shortage) if a <= 0 and p <= 0)

        rows.append(
            {
                "material": material,
                "train_weeks": int(len(train)),
                "forecast_start": pd.to_datetime(actual["date"].iloc[0]).isoformat(),
                "inventory_wape": _compute_wape(actual_inventory, predicted_inventory),
                "inventory_mae": _safe_mean(inventory_ae),
                "shortage_mae": _safe_mean(shortage_ae),
                "shortage_accuracy": _safe_mean(
                    [float((a > 0) == (p > 0)) for a, p in zip(actual_shortage, predicted_shortage)]
                ),
                "shortage_precision": _safe_div(tp, tp + fp),
                "shortage_recall": _safe_div(tp, tp + fn),
                "shortage_f1": (
                    None
                    if _safe_div(tp, tp + fp) is None or _safe_div(tp, tp + fn) is None
                    else _safe_div(
                        2 * _safe_div(tp, tp + fp) * _safe_div(tp, tp + fn),
                        _safe_div(tp, tp + fp) + _safe_div(tp, tp + fn),
                    )
                ),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "actual_shortage_any": any(value > 0 for value in actual_shortage),
                "predicted_shortage_any": any(value > 0 for value in predicted_shortage),
                "unknown_event_rows": diagnostics.get("unknownEventRows", 0),
                "ignored_demand_like_rows": diagnostics.get("ignoredDemandLikeRows", 0),
                "ignored_supply_like_rows": diagnostics.get("ignoredSupplyLikeRows", 0),
            }
        )
    return rows


def run_backtest(
    data_path: str | Path,
    horizon_weeks: int,
    min_history_weeks: int,
    max_materials: int | None,
) -> dict[str, Any]:
    backend = BackendService(BackendConfig(data_path=str(Path(data_path).resolve())))
    df = backend.get_data()
    if df.empty:
        raise ValueError(f"Unable to load data from {data_path}")

    analysis_config = AnalysisConfig()
    forecast_config = ForecastConfig(horizon_weeks=horizon_weeks, cv_folds=2)

    materials = [str(value) for value in df["Material Number"].dropna().astype(str).unique().tolist()]
    if max_materials is not None:
        materials = materials[:max_materials]

    rows: list[dict[str, Any]] = []
    for material in materials:
        group = (
            df[df["Material Number"].astype(str) == material]
            .sort_values("mrp_element_receipt_or_requirement_date")
            .copy()
        )
        rows.extend(
            _rolling_backtest_for_material(
                material=material,
                group=group,
                analysis_config=analysis_config,
                forecast_config=forecast_config,
                horizon_weeks=horizon_weeks,
                min_history_weeks=min_history_weeks,
            )
        )

    inventory_wape_values = [row["inventory_wape"] for row in rows if row["inventory_wape"] is not None]
    inventory_mae_values = [row["inventory_mae"] for row in rows if row["inventory_mae"] is not None]
    shortage_mae_values = [row["shortage_mae"] for row in rows if row["shortage_mae"] is not None]
    shortage_accuracy_values = [row["shortage_accuracy"] for row in rows if row["shortage_accuracy"] is not None]
    shortage_precision_values = [row["shortage_precision"] for row in rows if row["shortage_precision"] is not None]
    shortage_recall_values = [row["shortage_recall"] for row in rows if row["shortage_recall"] is not None]
    shortage_f1_values = [row["shortage_f1"] for row in rows if row["shortage_f1"] is not None]

    summary = {
        "dataPath": str(Path(data_path).resolve()),
        "materialsRequested": len(materials),
        "windowsEvaluated": len(rows),
        "horizonWeeks": horizon_weeks,
        "minHistoryWeeks": min_history_weeks,
        "inventoryWAPE": _safe_mean(inventory_wape_values),
        "inventoryMAE": _safe_mean(inventory_mae_values),
        "shortageMAE": _safe_mean(shortage_mae_values),
        "shortageAccuracy": _safe_mean(shortage_accuracy_values),
        "shortagePrecision": _safe_mean(shortage_precision_values),
        "shortageRecall": _safe_mean(shortage_recall_values),
        "shortageF1": _safe_mean(shortage_f1_values),
        "unknownEventRows": int(sum(row["unknown_event_rows"] for row in rows)),
        "ignoredDemandLikeRows": int(sum(row["ignored_demand_like_rows"] for row in rows)),
        "ignoredSupplyLikeRows": int(sum(row["ignored_supply_like_rows"] for row in rows)),
    }

    by_material: list[dict[str, Any]] = []
    material_rows = pd.DataFrame(rows)
    if not material_rows.empty:
        for material, group in material_rows.groupby("material", sort=False):
            by_material.append(
                {
                    "material": material,
                    "windowsEvaluated": int(len(group)),
                    "inventoryWAPE": _safe_mean(group["inventory_wape"].tolist()),
                    "inventoryMAE": _safe_mean(group["inventory_mae"].tolist()),
                    "shortageMAE": _safe_mean(group["shortage_mae"].tolist()),
                    "shortageAccuracy": _safe_mean(group["shortage_accuracy"].tolist()),
                    "shortagePrecision": _safe_mean(group["shortage_precision"].dropna().tolist()),
                    "shortageRecall": _safe_mean(group["shortage_recall"].dropna().tolist()),
                    "shortageF1": _safe_mean(group["shortage_f1"].dropna().tolist()),
                    "unknownEventRows": int(group["unknown_event_rows"].sum()),
                    "ignoredDemandLikeRows": int(group["ignored_demand_like_rows"].sum()),
                    "ignoredSupplyLikeRows": int(group["ignored_supply_like_rows"].sum()),
                }
            )
        by_material.sort(
            key=lambda item: (item["inventoryWAPE"] is None, item["inventoryWAPE"]),
        )

    return {
        "summary": summary,
        "byMaterial": by_material,
        "windows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run rolling backtest for forecast accuracy.")
    parser.add_argument(
        "--data-path",
        default=str(DATA_PATH),
        help="Path to source Excel file.",
    )
    parser.add_argument(
        "--horizon-weeks",
        type=int,
        default=4,
        help="Forecast horizon for each rolling window.",
    )
    parser.add_argument(
        "--min-history-weeks",
        type=int,
        default=8,
        help="Minimum number of weekly history points before evaluating a window.",
    )
    parser.add_argument(
        "--max-materials",
        type=int,
        default=None,
        help="Optional cap on the number of materials to evaluate.",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="",
        help="Optional path to write the full backtest result as JSON.",
    )
    args = parser.parse_args()

    result = run_backtest(
        data_path=args.data_path,
        horizon_weeks=args.horizon_weeks,
        min_history_weeks=args.min_history_weeks,
        max_materials=args.max_materials,
    )

    print("Backtest summary")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")

    print("\nTop materials by inventory WAPE")
    for item in result["byMaterial"][:10]:
        print(json.dumps(item, ensure_ascii=False))

    if args.output_json:
        output_path = Path(args.output_json).resolve()
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved JSON report to {output_path}")


if __name__ == "__main__":
    main()
