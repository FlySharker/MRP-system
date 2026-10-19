"""Inventory and safety stock forecasting helpers."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

from backend.data_local_window import MRP_ELEMENT_MAP, parse_window


DEMAND_EVENT_TYPES = {1}
SUPPLY_EVENT_TYPES = {2, 4, 6}


@dataclass
class ForecastConfig:
    horizon_weeks: int = 12
    min_history_points: int = 8
    seasonal_periods: int = 12
    validation_points: int = 4
    cv_folds: int = 3
    auto_seasonal: bool = True
    ensemble: bool = True


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def build_weekly_history(
    dates: pd.Series,
    inventory: list[float],
    safety_stock: list[float],
) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(dates, errors="coerce"),
            "inventory": inventory,
            "safety_stock": safety_stock,
        }
    ).dropna(subset=["date"])
    if frame.empty:
        return frame

    frame = frame.sort_values("date").set_index("date")
    weekly = (
        frame.resample("W-MON", label="left", closed="left")
        .last()
        .ffill()
        .dropna()
        .reset_index()
    )
    return weekly


def _preprocess_series(series: pd.Series) -> pd.Series:
    cleaned = pd.to_numeric(series, errors="coerce").astype(float)
    cleaned = cleaned.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    median = float(cleaned.median()) if len(cleaned) else 0.0
    mad = float(np.median(np.abs(cleaned - median))) if len(cleaned) else 0.0
    if mad > 0:
        upper = median + 6.0 * mad
        cleaned = cleaned.clip(lower=0.0, upper=upper)
    else:
        cleaned = cleaned.clip(lower=0.0)
    return cleaned


def _is_sparse_series(cleaned: pd.Series, min_history_points: int) -> bool:
    if cleaned.empty:
        return True
    non_zero = cleaned[cleaned > 0]
    if len(non_zero) < max(3, min_history_points // 3):
        return True
    zero_ratio = float((cleaned == 0).mean())
    if zero_ratio >= 0.6:
        return True
    return False


def _baseline_forecast(series: pd.Series, horizon: int) -> list[float]:
    cleaned = pd.to_numeric(series, errors="coerce").dropna()
    if cleaned.empty:
        return [0.0 for _ in range(horizon)]

    window = min(8, len(cleaned))
    if window <= 1:
        value = _safe_float(cleaned.iloc[-1])
    else:
        value = _safe_float(cleaned.iloc[-window:].mean())
    return [round(max(value, 0.0), 2) for _ in range(horizon)]


def _normalize_forecast(values: Any, clip_min: float | None = 0.0) -> list[float]:
    normalized: list[float] = []
    for value in values:
        number = _safe_float(value)
        if clip_min is not None:
            number = max(number, clip_min)
        normalized.append(round(number, 2))
    return normalized


def _safe_interval_bounds(lower: float, upper: float, center: float) -> tuple[float, float]:
    if not np.isfinite(lower) or not np.isfinite(upper):
        return float(round(center, 2)), float(round(center, 2))
    if lower > upper:
        lower, upper = upper, lower
    return float(round(lower, 2)), float(round(upper, 2))


def _forecast_error(actual: pd.Series, predicted: list[float]) -> float:
    actual_values = pd.to_numeric(actual, errors="coerce").astype(float).to_numpy()
    predicted_values = np.asarray(predicted, dtype=float)
    if len(actual_values) == 0 or len(actual_values) != len(predicted_values):
        return float("inf")

    scale = np.maximum(np.abs(actual_values), 1.0)
    return float(np.mean(np.abs(actual_values - predicted_values) / scale))


def _best_seasonal_period(cleaned: pd.Series, candidates: list[int]) -> int | None:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    best_aic = float("inf")
    best_period = None

    for sp in candidates:
        if len(cleaned) < sp * 2:
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = ExponentialSmoothing(
                    cleaned,
                    trend="add",
                    damped_trend=True,
                    seasonal="add",
                    seasonal_periods=sp,
                    initialization_method="estimated",
                )
                fitted = model.fit(optimized=True, use_brute=False)
                if fitted.aic < best_aic:
                    best_aic = fitted.aic
                    best_period = sp
        except Exception:
            continue

    return best_period


def _holt_winters_forecast(
    series: pd.Series,
    horizon: int,
    seasonal_periods: int | None,
    seasonal_type: str = "add",
    clip_min: float | None = 0.0,
) -> tuple[list[float], float]:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    cleaned = pd.to_numeric(series, errors="coerce").astype(float)
    non_zero = cleaned[cleaned > 0]
    if cleaned.empty or cleaned.round(6).nunique() <= 1:
        raise ValueError("Holt-Winters requires non-constant history")
    if len(non_zero) < 2:
        raise ValueError("Holt-Winters requires at least two positive observations")

    use_seasonal = (
        seasonal_periods is not None
        and len(cleaned) >= seasonal_periods * 2
        and cleaned.round(4).nunique() > seasonal_periods
    )

    if use_seasonal and seasonal_type == "mul" and (cleaned <= 0).any():
        use_seasonal = False

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        model = ExponentialSmoothing(
            cleaned,
            trend="add",
            damped_trend=True,
            seasonal=seasonal_type if use_seasonal else None,
            seasonal_periods=seasonal_periods if use_seasonal else None,
            initialization_method="estimated",
        )
        fitted = model.fit(optimized=True, use_brute=False)

    forecast = fitted.forecast(horizon)
    residual_std = float(np.std(fitted.resid)) if hasattr(fitted, "resid") else 0.0
    return _normalize_forecast(forecast, clip_min=clip_min), residual_std


def _cross_validate_model(
    forecast_fn,
    cleaned: pd.Series,
    horizon: int,
    seasonal_periods: int | None,
    n_folds: int = 3,
) -> float:
    total_len = len(cleaned)
    min_train = max((seasonal_periods or 4) * 2 + 1, 8)
    test_size = max(min(horizon, 4), 1)

    if total_len < min_train + test_size:
        n_folds = 1

    errors: list[float] = []
    fold_size = max(1, (total_len - min_train) // n_folds) if n_folds > 1 else test_size

    for i in range(n_folds):
        if n_folds == 1:
            train_end = total_len - test_size
            val_size = test_size
        else:
            train_end = min_train + i * fold_size
            val_size = min(test_size, total_len - train_end)

        if train_end < min_train or val_size < 1:
            continue

        train = cleaned.iloc[:train_end]
        val = cleaned.iloc[train_end : train_end + val_size]

        try:
            pred, _ = forecast_fn(train, val_size, seasonal_periods)
            err = _forecast_error(val, pred)
            if np.isfinite(err):
                errors.append(err)
        except Exception:
            continue

    return float(np.mean(errors)) if errors else float("inf")


def _ensemble_forecasts(
    candidates: list[tuple[float, list[float], str, float]],
) -> tuple[list[float], str, float]:
    valid = [(err, vals, name, rstd) for err, vals, name, rstd in candidates if np.isfinite(err)]
    if not valid:
        return candidates[0][1], candidates[0][2], candidates[0][3]
    if len(valid) == 1:
        return valid[0][1], valid[0][2], valid[0][3]

    errors = np.asarray([max(err, 1e-3) for err, _, _, _ in valid], dtype=float)
    shifted = errors - errors.min()
    with np.errstate(under="ignore", invalid="ignore", divide="ignore"):
        weights = np.exp(-1.0 * shifted)
    weight_sum = float(weights.sum())
    if not np.isfinite(weight_sum) or weight_sum <= 0:
        best_idx = int(np.argmin(errors))
        best = valid[best_idx]
        return best[1], best[2], best[3]
    weights = weights / weight_sum

    n_points = len(valid[0][1])
    blended: list[float] = []
    for i in range(n_points):
        value = float(sum(weight * values[i] for weight, (_, values, _, _) in zip(weights, valid)))
        blended.append(round(max(value, 0.0), 2))

    model_names = "+".join(name for _, _, name, _ in valid)
    avg_rstd = float(np.mean([rstd for _, _, _, rstd in valid]))
    return blended, f"ensemble({model_names})", avg_rstd


def _prediction_intervals(
    values: list[float],
    residuals_std: float,
    confidence: float = 0.80,
) -> tuple[list[float], list[float]]:
    from scipy.stats import norm

    z = norm.ppf(1 - (1 - confidence) / 2)
    lower: list[float] = []
    upper: list[float] = []
    for i, value in enumerate(values):
        scale = residuals_std * np.sqrt(i + 1)
        lower.append(round(max(value - z * scale, 0.0), 2))
        upper.append(round(value + z * scale, 2))
    return lower, upper


def _select_forecast_model(
    cleaned: pd.Series,
    config: ForecastConfig,
    clip_min: float | None = 0.0,
) -> tuple[list[float], str, str, list[float], list[float]]:
    if config.auto_seasonal and len(cleaned) >= 8:
        seasonal_periods = _best_seasonal_period(cleaned, [4, 8, 12, 16, 26]) or config.seasonal_periods
    else:
        seasonal_periods = config.seasonal_periods

    candidates: list[tuple[float, list[float], str, float]] = []

    def _baseline(train, h, _sp):
        return _baseline_forecast(train, h), float(np.std(pd.to_numeric(train, errors="coerce").astype(float)))

    def _hw_add(train, h, sp):
        return _holt_winters_forecast(train, h, sp, seasonal_type="add", clip_min=clip_min)

    model_fns: list[tuple[str, Any]] = [
        ("baseline_moving_average", _baseline),
        ("Holt-Winters", _hw_add),
    ]

    if (cleaned > 0).all() and len(cleaned[cleaned > 0]) >= 4:
        def _hw_mul(train, h, sp):
            return _holt_winters_forecast(train, h, sp, seasonal_type="mul", clip_min=clip_min)
        model_fns.append(("Holt-Winters-Mul", _hw_mul))

    for model_name, forecast_fn in model_fns:
        try:
            error = _cross_validate_model(
                forecast_fn,
                cleaned,
                min(config.validation_points, config.horizon_weeks),
                seasonal_periods,
                config.cv_folds,
            )
            values, rstd = forecast_fn(cleaned, config.horizon_weeks, seasonal_periods)
            candidates.append((error, values, model_name, rstd))
        except Exception:
            continue

    if not candidates:
        baseline = _baseline_forecast(cleaned, config.horizon_weeks)
        return baseline, "baseline_moving_average", "low", baseline, baseline

    if config.ensemble and len(candidates) >= 2:
        values, model_name, rstd = _ensemble_forecasts(candidates)
        confidence = "high" if len(cleaned) >= max(config.min_history_points, 10) else "medium"
    else:
        candidates.sort(key=lambda item: item[0])
        _, values, model_name, rstd = candidates[0]
        confidence = "medium" if model_name == "baseline_moving_average" else "high"

    lower, upper = _prediction_intervals(values, rstd)
    return values, model_name, confidence, lower, upper


def forecast_series(
    series: pd.Series,
    config: ForecastConfig,
    clip_min: float | None = 0.0,
) -> tuple[list[float], str, str, list[float], list[float]]:
    cleaned = _preprocess_series(series)
    unique_values = cleaned.round(4).nunique()
    if len(cleaned) < config.min_history_points or unique_values <= 1 or _is_sparse_series(cleaned, config.min_history_points):
        baseline = _normalize_forecast(_baseline_forecast(cleaned, config.horizon_weeks), clip_min=clip_min)
        return baseline, "baseline_moving_average", "low", baseline, baseline
    return _select_forecast_model(cleaned, config, clip_min=clip_min)


def _week_start(date_series: pd.Series) -> pd.Series:
    dates = pd.to_datetime(date_series, errors="coerce")
    return dates.dt.normalize() - pd.to_timedelta(dates.dt.weekday, unit="D")


def build_flow_history(
    group: pd.DataFrame,
    inventory: list[float],
    safety_stock: list[float],
) -> pd.DataFrame:
    frame = group.copy()
    frame["date"] = pd.to_datetime(frame["mrp_element_receipt_or_requirement_date"], errors="coerce")
    frame["inventory"] = inventory
    frame["safety_stock"] = safety_stock
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if frame.empty:
        return pd.DataFrame()

    event_types = frame["Mrp Element Short Name"].map(MRP_ELEMENT_MAP).fillna(-1)
    qty = pd.to_numeric(frame["Qty"], errors="coerce").fillna(0.0)
    diagnostics = {
        "unknownEventRows": int((event_types == -1).sum()),
        "ignoredDemandLikeRows": int(((qty < 0) & ~event_types.isin(DEMAND_EVENT_TYPES)).sum()),
        "ignoredSupplyLikeRows": int(((qty > 0) & ~event_types.isin(SUPPLY_EVENT_TYPES) & (event_types != 0)).sum()),
    }
    frame["inbound"] = np.where(
        (event_types.isin(SUPPLY_EVENT_TYPES)) & (qty > 0),
        qty,
        0.0,
    )
    frame["outbound"] = np.where(
        (event_types.isin(DEMAND_EVENT_TYPES)) & (qty < 0),
        qty.abs(),
        0.0,
    )
    frame["week_start"] = _week_start(frame["date"])

    weekly_flow = (
        frame.groupby("week_start", as_index=False)
        .agg(
            inbound=("inbound", "sum"),
            outbound=("outbound", "sum"),
            inventory=("inventory", "last"),
            safety_stock=("safety_stock", "last"),
            last_observed_date=("date", "max"),
        )
        .sort_values("week_start")
        .reset_index(drop=True)
    )

    if weekly_flow.empty:
        return weekly_flow

    all_weeks = pd.date_range(
        start=weekly_flow["week_start"].min(),
        end=weekly_flow["week_start"].max(),
        freq="W-MON",
    )
    weekly_flow = (
        weekly_flow.set_index("week_start")
        .reindex(all_weeks)
        .rename_axis("date")
        .reset_index()
    )
    weekly_flow["inbound"] = weekly_flow["inbound"].fillna(0.0)
    weekly_flow["outbound"] = weekly_flow["outbound"].fillna(0.0)
    weekly_flow["inventory"] = weekly_flow["inventory"].ffill().fillna(0.0)
    weekly_flow["safety_stock"] = weekly_flow["safety_stock"].ffill().fillna(0.0)
    weekly_flow["last_observed_date"] = pd.to_datetime(weekly_flow["last_observed_date"], errors="coerce")
    weekly_flow["display_date"] = weekly_flow["last_observed_date"].where(
        weekly_flow["last_observed_date"].notna(),
        weekly_flow["date"],
    )
    weekly_flow["net_flow"] = weekly_flow["inbound"] - weekly_flow["outbound"]
    weekly_flow.attrs["diagnostics"] = diagnostics
    return weekly_flow


def _build_future_demand_series(weekly_flow: pd.DataFrame, future_dates: list[pd.Timestamp]) -> pd.Series:
    demand_history = weekly_flow.loc[weekly_flow["outbound"] > 0, ["date", "outbound"]].copy()
    if demand_history.empty:
        demand_history = weekly_flow.loc[:, ["date"]].copy()
        demand_history["outbound"] = 0.0

    future_frame = pd.DataFrame({"date": future_dates, "outbound": [np.nan] * len(future_dates)})
    demand_frame = pd.concat([demand_history, future_frame], ignore_index=True, sort=False)
    return demand_frame["outbound"]


def _extend_safety_stock(
    weekly_flow: pd.DataFrame,
    future_outbound: list[float],
    analysis_config: Any,
) -> tuple[list[float], list[float], list[float]]:
    window = parse_window(getattr(analysis_config, "time_window_size", "14D"))
    quantile = getattr(analysis_config, "quantile", 0.75)
    forecast_anchor = pd.to_datetime(weekly_flow["date"].max())
    future_dates = [forecast_anchor + timedelta(weeks=i + 1) for i in range(len(future_outbound))]

    demand_frame = weekly_flow.loc[:, ["date", "outbound"]].copy().sort_values("date").reset_index(drop=True)

    safety_stock: list[float] = []
    lower: list[float] = []
    upper: list[float] = []
    last_valid = _safe_float(weekly_flow["safety_stock"].iloc[-1]) if not weekly_flow.empty else 0.0

    for date in future_dates:
        start_date = date - window
        window_demands = demand_frame.loc[
            (demand_frame["date"] >= start_date)
            & (demand_frame["date"] <= forecast_anchor),
            "outbound",
        ].dropna()
        if len(window_demands) == 0:
            value = last_valid
        elif len(window_demands) == 1:
            value = _safe_float(window_demands.iloc[0], last_valid)
        else:
            value = _safe_float(window_demands.quantile(quantile), last_valid)
        if len(window_demands) >= 2:
            q_low = _safe_float(window_demands.quantile(max(0.5, quantile - 0.15)), value)
            q_high = _safe_float(window_demands.quantile(min(0.95, quantile + 0.15)), value)
        else:
            q_low = value
            q_high = value
        safety_stock.append(float(round(max(value, 0.0), 2)))
        lower.append(float(round(max(q_low, 0.0), 2)))
        upper.append(float(round(max(q_high, q_low, 0.0), 2)))
        last_valid = value

    return safety_stock, lower, upper


def _derive_confidence(labels: set[str], history_weeks: int) -> str:
    if "low" in labels:
        return "low"
    if history_weeks >= 24 and "high" in labels:
        return "high"
    return "medium"


def build_forecast_payload(
    material: str,
    group: pd.DataFrame,
    analysis_result: dict[str, Any],
    analysis_config: Any,
    config: ForecastConfig | None = None,
) -> dict[str, Any]:
    config = config or ForecastConfig()
    weekly_flow = build_flow_history(
        group,
        analysis_result.get("inventory", []),
        analysis_result.get("safety_stock_series", []),
    )
    if weekly_flow.empty:
        return {
            "material": material,
            "status": "error",
            "error_message": "历史数据不足，无法预测。",
        }

    diagnostics = dict(weekly_flow.attrs.get("diagnostics", {}))
    inbound_vals, inbound_model, inbound_conf, inbound_lower, inbound_upper = forecast_series(
        weekly_flow["inbound"], config, clip_min=0.0
    )
    outbound_vals, outbound_model, outbound_conf, outbound_lower, outbound_upper = forecast_series(
        weekly_flow["outbound"], config, clip_min=0.0
    )

    future_dates = [
        pd.to_datetime(weekly_flow["date"].max()).normalize() + timedelta(weeks=i + 1)
        for i in range(config.horizon_weeks)
    ]
    safety_stock_vals, ss_lower, ss_upper = _extend_safety_stock(
        weekly_flow,
        outbound_vals,
        analysis_config,
    )

    current_inventory = _safe_float(weekly_flow["inventory"].iloc[-1])
    inventory_vals: list[float] = []
    inventory_lower: list[float] = []
    inventory_upper: list[float] = []
    lower_state = current_inventory
    upper_state = current_inventory

    for idx in range(config.horizon_weeks):
        inbound = inbound_vals[idx]
        outbound = outbound_vals[idx]
        net_flow = inbound - outbound
        current_inventory += net_flow
        inventory_vals.append(float(round(current_inventory, 2)))

        lower_state += inbound_lower[idx] - outbound_upper[idx]
        upper_state += inbound_upper[idx] - outbound_lower[idx]
        lower_bound, upper_bound = _safe_interval_bounds(lower_state, upper_state, current_inventory)
        inventory_lower.append(lower_bound)
        inventory_upper.append(upper_bound)

    forecast_rows: list[dict[str, Any]] = []
    shortage_flags: list[bool] = []
    for idx, date in enumerate(future_dates):
        predicted_inventory = inventory_vals[idx]
        predicted_safety_stock = safety_stock_vals[idx]
        shortage = max(predicted_safety_stock - predicted_inventory, 0.0)
        shortage_ratio = shortage / max(predicted_safety_stock, 1.0)
        shortage_flags.append(shortage > 0)

        if shortage <= 0:
            risk_level = "normal"
        elif shortage_ratio >= 0.5 or (idx > 0 and shortage_flags[idx - 1]):
            risk_level = "high"
        else:
            risk_level = "watch"

        forecast_rows.append(
            {
                "week": idx + 1,
                "date": date.isoformat(),
                "predictedInventory": float(round(predicted_inventory, 2)),
                "predictedSafetyStock": float(round(predicted_safety_stock, 2)),
                "shortage": float(round(shortage, 2)),
                "suggestedReplenishment": float(round(shortage, 2)),
                "riskLevel": risk_level,
                "inventoryLower": float(round(inventory_lower[idx], 2)),
                "inventoryUpper": float(round(inventory_upper[idx], 2)),
                "safetyStockLower": float(ss_lower[idx]),
                "safetyStockUpper": float(ss_upper[idx]),
                "predictedInbound": float(round(inbound_vals[idx], 2)),
                "predictedOutbound": float(round(outbound_vals[idx], 2)),
                "predictedNetFlow": float(round(inbound_vals[idx] - outbound_vals[idx], 2)),
            }
        )

    first_shortage = next((row for row in forecast_rows if row["shortage"] > 0), None)
    max_shortage = max((row["shortage"] for row in forecast_rows), default=0.0)
    shortage_weeks = sum(1 for row in forecast_rows if row["shortage"] > 0)
    max_shortage_ratio = max(
        (
            row["shortage"] / max(row["predictedSafetyStock"], 1.0)
            for row in forecast_rows
            if row["shortage"] > 0
        ),
        default=0.0,
    )
    if shortage_weeks >= 3 or max_shortage_ratio >= 0.5:
        overall_risk = "high"
    elif max_shortage > 0:
        overall_risk = "watch"
    else:
        overall_risk = "normal"

    history_rows = [
        {
            "date": pd.to_datetime(row["display_date"]).isoformat(),
            "inventory": round(_safe_float(row["inventory"]), 2),
            "safetyStock": round(_safe_float(row["safety_stock"]), 2),
            "inbound": round(_safe_float(row["inbound"]), 2),
            "outbound": round(_safe_float(row["outbound"]), 2),
            "netFlow": round(_safe_float(row["net_flow"]), 2),
        }
        for row in weekly_flow.to_dict(orient="records")
    ]

    return {
        "material": material,
        "status": "success",
        "horizonWeeks": config.horizon_weeks,
        "grain": "week",
        "historyWeeks": int(len(weekly_flow)),
        "model": {
            "inventory": "derived_from_flow_forecast",
            "inventorySemantics": "net_inventory_position",
            "safetyStock": "rolling_quantile_rule",
            "inbound": inbound_model,
            "outbound": outbound_model,
            "confidence": _derive_confidence({inbound_conf, outbound_conf}, len(weekly_flow)),
            "weekFlowDefinition": "week_flow = predicted inbound - predicted outbound; future inventory is rolled forward from current inventory with weekly net flow.",
            "notes": [
                "Safety stock here is a rolling demand-quantile estimate, so it may differ from the source-system safety-stock field.",
                "If predicted outbound stays above predicted inbound, week_flow remains negative and inventory will keep declining.",
                "Longer horizons naturally widen intervals, so the chart may visually de-emphasize interval extremes to keep historical lines readable.",
            ],
        },
        "summary": {
            "overallRisk": overall_risk,
            "shortageWeeks": shortage_weeks,
            "maxShortage": round(max_shortage, 2),
            "firstShortageDate": first_shortage["date"] if first_shortage else None,
        },
        "diagnostics": diagnostics,
        "history": history_rows,
        "forecast": forecast_rows,
    }
