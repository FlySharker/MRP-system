import argparse
from numbers import Number
from pathlib import Path

import math
import pandas as pd
import plotly.graph_objects as go

from backend.anomaly_reason import analyze_with_llm
from backend.config import DATA_PATH, PROJECT_ROOT

INPUT_PATH = DATA_PATH
LLM_OUTPUTS_PATH = PROJECT_ROOT / "llm_outputs.txt"

MRP_ELEMENT_MAP = {
    "Stock": 0,
    "Order": 1,
    "IndReq": 1,
    "Fr.del": 1,
    "RelOrd": 1,
    "PlORel": 1,
    "Retrns": 1,
    "PurRqs": 2,
    "Pl.ord": 2,
    "SAFcst": 1,
    "SAgRel": 1,
    "ShipNt": 2,
    "Shpnt*": 2,
    "Deliv.": 1,
    "SchAgr": 3,
    "SAJit": 3,
    "SAFirm": 3,
    "SchAg*": 3,
    "ShLine": 4,
    "ShLne*": 4,
    "eptfen": 5,
    "AB Con": 6,
    "QM lot": 6,
    "Tr.res": 6,
}

SELECT_COLUMNS = [
    "mrp_element_receipt_or_requirement_date",
    "Mrp Element Short Name",
    "Qty",
]


def parse_mrp_dates(values: pd.Series) -> pd.Series:
    """Parse Excel serial dates and mixed date strings consistently."""
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")

    numeric_mask = values.map(lambda value: isinstance(value, Number))
    numeric_values = pd.to_numeric(values.where(numeric_mask), errors="coerce")
    excel_serial_mask = numeric_mask & numeric_values.between(1, 2_958_465)
    parsed.loc[excel_serial_mask] = pd.to_datetime(
        numeric_values.loc[excel_serial_mask],
        unit="D",
        origin="1899-12-30",
        errors="coerce",
    )

    remaining = ~excel_serial_mask
    text_values = values.loc[remaining].astype("string").str.strip()
    year_first_mask = text_values.str.match(
        r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        na=False,
    )
    parsed.loc[text_values.index[year_first_mask]] = pd.to_datetime(
        text_values.loc[year_first_mask],
        format="mixed",
        dayfirst=False,
        errors="coerce",
    )
    parsed.loc[text_values.index[~year_first_mask]] = pd.to_datetime(
        text_values.loc[~year_first_mask],
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )

    return parsed.ffill()


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip()
    df[["Material Number", "plant_id"]] = df[["Material Number", "plant_id"]].ffill()
    df["mrp_element_receipt_or_requirement_date"] = parse_mrp_dates(
        df["mrp_element_receipt_or_requirement_date"]
    )
    return df


def compute_local_safety_stock_series(
    group: pd.DataFrame,
    window_size: int,
    quantile: float,
) -> list[float]:
    demand_series = (
        group["Qty"]
        .where(
            (group["Qty"] < 0)
            & (group["Mrp Element Short Name"].map(MRP_ELEMENT_MAP) == 1)
        )
        .abs()
    )
    safety_stock_series = []
    last_valid = 0.0

    for end_idx in range(len(group)):
        if pd.isna(demand_series.iloc[end_idx]):
            current_value = last_valid
            safety_stock_series.append(current_value)
            continue
        start_idx = max(0, end_idx - window_size + 1)
        window_demands = demand_series.iloc[start_idx : end_idx + 1].dropna()

        if len(window_demands) == 0:
            current_value = last_valid
        elif len(window_demands) == 1:
            current_value = float(window_demands.iloc[0])
        else:
            current_value = float(window_demands.quantile(quantile))

        safety_stock_series.append(current_value)
        last_valid = current_value

    return safety_stock_series


def parse_window(window_str: str) -> pd.Timedelta:
    window_str = window_str.strip().upper()

    if window_str.endswith("M"):
        value = int(window_str[:-1])
        return pd.Timedelta(days=30 * value)
    elif window_str.endswith("W"):
        value = int(window_str[:-1])
        return pd.Timedelta(weeks=value)
    elif window_str.endswith("D"):
        value = int(window_str[:-1])
        return pd.Timedelta(days=value)
    elif window_str.endswith("Y"):
        value = int(window_str[:-1])
        return pd.Timedelta(days=365 * value)
    else:
        raise ValueError("Unsupported window format. Use D/W/M/Y.")


def compute_local_safety_stock_series_time_window(
    group: pd.DataFrame,
    window_size: pd.Timedelta,
    quantile: float,
) -> list[float]:
    dates = pd.to_datetime(group["mrp_element_receipt_or_requirement_date"])

    demand_series = (
        group["Qty"]
        .where(
            (group["Qty"] < 0)
            & (group["Mrp Element Short Name"].map(MRP_ELEMENT_MAP) == 1)
        )
        .abs()
    )

    safety_stock_series = []
    last_valid = 0.0

    for end_idx in range(len(group)):
        current_date = dates.iloc[end_idx]

        start_date = current_date - window_size

        mask = (dates >= start_date) & (dates <= current_date)
        window_demands = demand_series[mask].dropna()

        if len(window_demands) == 0:
            current_value = last_valid
        elif len(window_demands) == 1:
            current_value = float(window_demands.iloc[0])
        else:
            current_value = float(window_demands.quantile(quantile))

        safety_stock_series.append(current_value)
        last_valid = current_value

    return safety_stock_series


def compute_inventory(group: pd.DataFrame) -> list[float]:
    inventory = []
    current = 0.0
    date_col = "mrp_element_receipt_or_requirement_date"

    # 逐行计算库存（按时间顺序），但稍后把同一天的所有行库存设为该天最后一行的结果。
    for _, row in group.iterrows():
        event = row["Mrp Element Short Name"]
        qty = row["Qty"]
        event_type = MRP_ELEMENT_MAP.get(event, -1)

        if event_type == 0:
            current = qty
        elif event_type in {1, 2, 4, 6}:
            current += qty
        elif event_type == 3:
            pass

        inventory.append(float(current))

    # 将同一天（按日期，不含时间）的所有行库存设置为该天最后一行的库存值
    try:
        dates = pd.to_datetime(group[date_col]).dt.date.tolist()
        from collections import defaultdict

        idxs_by_date = defaultdict(list)
        for idx, d in enumerate(dates):
            idxs_by_date[d].append(idx)
        for d, idxs in idxs_by_date.items():
            last_val = inventory[idxs[-1]]
            for i in idxs:
                inventory[i] = float(last_val)
    except Exception:
        # 如果按日期分组失败，则保持原始逐行库存不变
        pass

    return inventory


def collect_shortage_intervals(
    inventory: list[float],
    safety_stock_series: list[float],
    min_interval_len: int = 2,
) -> list[tuple[int, int]]:
    intervals = []
    start = None

    for idx, (inv, threshold) in enumerate(zip(inventory, safety_stock_series)):
        if inv < threshold:
            if start is None:
                start = idx
            continue

        if start is not None and idx - start >= min_interval_len:
            intervals.append((start, idx - 1))
        start = None

    if start is not None and len(inventory) - start >= min_interval_len:
        intervals.append((start, len(inventory) - 1))

    return intervals


def rule_gradual_shortage(
    inventory: list[float],
    safety_stock_series: list[float],
    dates: list | None = None,
    min_run_len: int = 3,
) -> bool:
    # 如果传入 dates，则先按日期归约（取每日期的最后一个库存/安全库存），
    # 使判断基于按日序列而不是行级序列。这避免了把同一天平坦化后的多行误导判定。
    if dates is not None:
        df_tmp = pd.DataFrame(
            {
                "date": pd.to_datetime(dates).dt.date,
                "inv": inventory,
                "ss": safety_stock_series,
            }
        )
        daily = (
            df_tmp.groupby("date", sort=True)
            .agg({"inv": "last", "ss": "last"})
            .reset_index()
        )
        inventory = daily["inv"].tolist()
        safety_stock_series = daily["ss"].tolist()
    intervals = collect_shortage_intervals(
        inventory,
        safety_stock_series,
        min_interval_len=min_run_len,
    )

    for start, end in intervals:
        inv_slice = inventory[start : end + 1]
        gap_slice = [
            safety_stock_series[idx] - inventory[idx] for idx in range(start, end + 1)
        ]

        inventory_non_increasing = all(
            inv_slice[idx] >= inv_slice[idx + 1] for idx in range(len(inv_slice) - 1)
        )
        gap_non_decreasing = all(
            gap_slice[idx] <= gap_slice[idx + 1] for idx in range(len(gap_slice) - 1)
        )

        if inventory_non_increasing and gap_non_decreasing:
            return True

    return False


def rule_fluctuation(
    inventory: list[float],
    safety_stock_series: list[float],
    dates: list | None = None,
    min_switches: int = 2,
) -> bool:
    # 可选按日归约：如果传入 dates，则先按日期取每日期的最后一条库存/安全库存，再在日序列上计算波动开关数
    if dates is not None:
        df_tmp = pd.DataFrame(
            {
                "date": pd.to_datetime(dates).dt.date,
                "inv": inventory,
                "ss": safety_stock_series,
            }
        )
        daily = (
            df_tmp.groupby("date", sort=True)
            .agg({"inv": "last", "ss": "last"})
            .reset_index()
        )
        inventory = daily["inv"].tolist()
        safety_stock_series = daily["ss"].tolist()

    above_local_threshold = [
        inv > threshold for inv, threshold in zip(inventory, safety_stock_series)
    ]

    switches = sum(
        above_local_threshold[idx] != above_local_threshold[idx + 1]
        for idx in range(len(above_local_threshold) - 1)
    )

    return switches >= min_switches


def rule_demand_spike(
    group: pd.DataFrame,
    window_size: int,
    spike_factor: float = 3.0,
    dates: list | None = None,
) -> bool:
    # 如果传入 dates，则按日归约需求（同日需求累加）后在日序列上检测突发
    if dates is not None:
        demand_df = group.loc[
            (group["Qty"] < 0)
            & (group["Mrp Element Short Name"].map(MRP_ELEMENT_MAP) == 1),
            ["mrp_element_receipt_or_requirement_date", "Qty"],
        ].copy()
        if demand_df.empty:
            return False
        demand_by_date = (
            demand_df.assign(
                date=pd.to_datetime(
                    demand_df["mrp_element_receipt_or_requirement_date"]
                ).dt.date
            )
            .groupby("date", sort=True)["Qty"]
            .sum()
            .abs()
            .tolist()
        )
        demand = demand_by_date
    else:
        demand = (
            group.loc[
                (group["Qty"] < 0)
                & (group["Mrp Element Short Name"].map(MRP_ELEMENT_MAP) == 1),
                "Qty",
            ]
            .abs()
            .tolist()
        )

    if len(demand) < 2:
        return False

    for idx in range(1, len(demand)):
        start_idx = max(0, idx - window_size)
        baseline_window = demand[start_idx:idx]
        if len(baseline_window) == 0:
            continue
        baseline = sum(baseline_window) / len(baseline_window)

        if baseline > 0 and demand[idx] > spike_factor * baseline:
            return True

    return False


def rule_demand_spike_time_window(
    group: pd.DataFrame,
    window_size: pd.Timedelta,
    spike_factor: float = 2.0,
) -> bool:
    demand_df = group.loc[
        (group["Qty"] < 0)
        & (group["Mrp Element Short Name"].map(MRP_ELEMENT_MAP) == 1),
        ["mrp_element_receipt_or_requirement_date", "Qty"],
    ].copy()

    if demand_df.empty:
        return False

    demand_df["date"] = pd.to_datetime(
        demand_df["mrp_element_receipt_or_requirement_date"]
    )
    demand_df["demand"] = demand_df["Qty"].abs()

    demand_df = demand_df.sort_values("date")

    dates = demand_df["date"].tolist()
    demands = demand_df["demand"].tolist()

    for idx in range(len(demand_df)):
        current_date = dates[idx]
        current_demand = demands[idx]

        start_date = current_date - window_size

        baseline_values = [
            demands[i]
            for i in range(idx)
            if dates[i] >= start_date
        ]

        if len(baseline_values) == 0:
            continue

        baseline = sum(baseline_values) / len(baseline_values)

        if baseline > 0 and current_demand > spike_factor * baseline:
            return True

    return False


def rule_late_matching(
    group: pd.DataFrame,
    max_delay_days: int = 7,
) -> tuple[bool, list[float]]:
    demands = []
    supplies = []

    initial_stock = 0.0
    for _, row in group.iterrows():
        if row["Mrp Element Short Name"] == "Stock":
            initial_stock = float(row["Qty"])
            break

    for _, row in group.iterrows():
        qty = row["Qty"]
        event = row["Mrp Element Short Name"]
        date = row["mrp_element_receipt_or_requirement_date"]
        event_type = MRP_ELEMENT_MAP.get(event, -1)

        if qty < 0 and event_type == 1:
            demands.append([date, -float(qty)])
        elif qty > 0 and event_type == 2:
            supplies.append([date, float(qty)])

    delays = []
    supply_idx = 0

    for demand_date, demand_qty in demands:
        remaining = demand_qty

        if initial_stock > 0:
            used_from_stock = min(remaining, initial_stock)
            remaining -= used_from_stock
            initial_stock -= used_from_stock

        first_supply_date = None

        while supply_idx < len(supplies) and remaining > 0:
            supply_date, supply_qty = supplies[supply_idx]

            if supply_date < demand_date:
                supply_idx += 1
                continue

            used = min(remaining, supply_qty)
            if used > 0 and first_supply_date is None:
                first_supply_date = supply_date

            remaining -= used
            supplies[supply_idx][1] -= used

            if supplies[supply_idx][1] == 0:
                supply_idx += 1

        if remaining == 0:
            delay_days = (
                (first_supply_date - demand_date).days
                if first_supply_date is not None
                else 0
            )
            delays.append(delay_days)
        else:
            delays.append(float("inf"))

    return any(delay > max_delay_days for delay in delays), delays


# def compute_inventory_risk_score(
#     inventory,
#     safety_stock,
#     dates,
#     k=2.0,
#     eps=1e-6,
#     min_gap_threshold=0.01,
# ):
#     """Compute inventory risk score with improved sensitivity.
    
#     Args:
#         k: Exponential decay factor (higher = more sensitive to small gaps)
#         eps: Small value to avoid division by zero
#         min_gap_threshold: Minimum gap ratio to consider (avoids floating point noise)
#     """
#     dates = pd.to_datetime(dates)

#     weighted_risk = 0.0
#     total_time = 0.0

#     for i in range(len(inventory) - 1):
#         gap = max(
#             0.0,
#             safety_stock[i] - inventory[i]
#         )
        
#         # Normalize gap by safety stock to get relative shortage
#         ratio = gap / (safety_stock[i] + eps)
        
#         # Apply minimum threshold to filter out numerical noise
#         if ratio < min_gap_threshold:
#             ratio = 0.0

#         # Exponential severity: higher k means faster ramp-up for small gaps
#         severity = 1 - math.exp(-k * ratio)

#         delta_days = (
#             dates.iloc[i + 1] - dates.iloc[i]
#         ).total_seconds() / (24 * 3600)

#         weighted_risk += severity * delta_days
#         total_time += delta_days

#     if total_time == 0:
#         return 0.0

#     # Normalize to 0-1 range
#     score = weighted_risk / total_time
    
#     # Round to avoid excessive precision (e.g., 0.0000)
#     return round(score, 4)


def compute_inventory_risk_score(
    inventory: list[float],
    safety_stock: list[float],
    dates: list,
    intervals: list[tuple[int, int]] | None = None,
    min_delta: float = 1e-3,
) -> float:
    """
    Risk score =
        abnormal shortage exposure area
        --------------------------------
              total timeline area

    Range: [0,1]
    """

    dates = pd.to_datetime(dates)

    if len(dates) <= 1:
        return 0.0

    weighted_sum = 0.0
    overall_total_time = 0.0

    # ===== 总时间 =====
    c = 0
    for i in range(len(dates) - 1):
        delta_days = (
            dates.iloc[i + 1] - dates.iloc[i]
        ).total_seconds() / (24 * 3600)

        delta_days = max(delta_days, min_delta)

        overall_total_time += delta_days
        
        c += 1

    if overall_total_time <= c * min_delta:
        return 0.0

    # ===== 异常暴露 =====
    if intervals:
        for start, end in intervals:

            for i in range(start, end + 1):

                if i < len(dates) - 1:
                    delta_days = (
                        dates.iloc[i + 1] - dates.iloc[i]
                    ).total_seconds() / (24 * 3600)

                    delta_days = max(delta_days, min_delta)

                else:
                    delta_days = min_delta

                ss = safety_stock[i]
                inv = inventory[i]

                if ss > 0 and inv < ss:

                    effective_inv = max(inv, 0.0)

                    ratio = (
                        ss - effective_inv
                    ) / ss

                    weighted_sum += ratio * delta_days

    score = weighted_sum / overall_total_time
    score = min(max(score, 0.0), 1.0) # 虽然进行截断了，但是最大值为1.0010
    return round(score, 4)


def classify_risk_level(score: float) -> str:
    """Classify risk level with adjusted thresholds to reduce L1/L4 skew.
    
    Thresholds are tuned so that:
    - L1 (Low): score < 0.20 (truly normal/low risk)
    - L2 (Moderate-Low): 0.20 <= score < 0.5
    - L3 (Moderate-High): 0.50 <= score < 0.80
    - L4 (High): score >= 0.80 (severe risk requiring immediate action)
    """
    if score < 0.2:
        return "L1"
    elif score < 0.5:
        return "L2"
    elif score < 0.8:
        return "L3"
    else:
        return "L4"


def interval_to_date_ranges(
    group: pd.DataFrame,
    intervals: list[tuple[int, int]],
) -> list[dict]:
    date_ranges = []

    for start, end in intervals:
        start_date = group.iloc[start]["mrp_element_receipt_or_requirement_date"]
        end_date = group.iloc[end]["mrp_element_receipt_or_requirement_date"]
        date_ranges.append(
            {
                "start_idx": start,
                "end_idx": end,
                "start_date": start_date,
                "end_date": end_date,
            }
        )

    return date_ranges


def summarize_delay_steps(delays: list[float]) -> str | None:
    if not delays:
        return None
    if any(delay == float("inf") for delay in delays):
        return "inf"
    return str(int(max(delays)))


def format_interval_preview(interval_ranges: list[dict]) -> str | None:
    if not interval_ranges:
        return None

    first_interval = interval_ranges[0]
    start_date = first_interval["start_date"].strftime("%Y-%m-%d")
    end_date = first_interval["end_date"].strftime("%Y-%m-%d")
    return f"{start_date} -> {end_date}"


def plot_inventory_and_safety_stock_with_intervals(
    group: pd.DataFrame,
    inventory: list[float],
    safety_stock_series: list[float],
    intervals: list[tuple[int, int]],
    material: str,
) -> None:

    dates = pd.to_datetime(group["mrp_element_receipt_or_requirement_date"])
    fig = go.Figure()
    events = group["Mrp Element Short Name"]
    qty = group["Qty"]

    # Inventory曲线
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=inventory,
            mode="lines+markers",
            name="Inventory",
            marker=dict(symbol="circle"),
            text=events,
            customdata=qty,
            hovertemplate="Date: %{x}<br>"
            + "Inventory: %{y}<br>"
            + "Event: %{text}<extra></extra>"
            + "Qty: %{customdata}<extra></extra>",
        )
    )

    # Safety Stock曲线
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=safety_stock_series,
            mode="lines+markers",
            name="Local Safety Stock",
            marker=dict(symbol="x"),
            hovertemplate="Date: %{x}<br>Safety Stock: %{y}<extra></extra>",
        )
    )

    # 异常区间
    for start, end in intervals:
        fig.add_vrect(
            x0=dates.iloc[start],
            x1=dates.iloc[end],
            fillcolor="red",
            opacity=0.3,
            line_width=0,
        )

    fig.update_layout(
        title=f"Inventory and Safety Stock for Material: {material}",
        xaxis_title="Date",
        yaxis_title="Quantity",
        hovermode="closest",
    )

    # fig.show()
    html_figure = fig.to_html(full_html=False, include_plotlyjs="cdn")
    return html_figure


def analyze_material_group(
    material: str,
    group: pd.DataFrame,
    window_size: int,
    quantile: float,
    min_interval_len: int,
    if_plot: bool = False,
) -> dict:
    '''
    local_safety_stock = compute_local_safety_stock_series(
        group,
        window_size=window_size,
        quantile=quantile,
    )
    '''
    local_safety_stock = compute_local_safety_stock_series_time_window(
        group,
        window_size=window_size,
        quantile=quantile,
    )
    inventory = compute_inventory(group)

    intervals = collect_shortage_intervals(
        inventory,
        local_safety_stock,
        min_interval_len=min_interval_len,
    )

    risk_score = compute_inventory_risk_score(
        inventory=inventory,
        safety_stock=local_safety_stock,
        dates=group["mrp_element_receipt_or_requirement_date"],
        intervals=intervals
    )

    risk_level = classify_risk_level(risk_score)

    result = {
        "material": material,
        "window_size": window_size,
        "safety_stock_series": local_safety_stock,
        "inventory": inventory,
        "intervals": intervals,
        "interval_ranges": interval_to_date_ranges(group, intervals),
        "Normal": len(intervals) == 0,
        "risk_score": round(risk_score, 6),
        "risk_level": risk_level,
    }

    # 可选绘图（不应在 build_results 中误插入）
    if if_plot:
        try:
            plot_inventory_and_safety_stock_with_intervals(
                group, inventory, local_safety_stock, intervals, material
            )
        except Exception as _e:
            print("Plot failed:", _e)

    if len(intervals) == 0:
        return result

    late_flag, delays = rule_late_matching(group)
    result.update(
        {
            "toolate": late_flag,
            "delay_steps": delays,
            "gradual_shortage": rule_gradual_shortage(
                inventory,
                local_safety_stock,
                group["mrp_element_receipt_or_requirement_date"],
            ),
            "fluctuation": rule_fluctuation(
                inventory,
                local_safety_stock,
                dates=group["mrp_element_receipt_or_requirement_date"],
            ),
            # "demand_spike": rule_demand_spike(
            #     group,
            #     window_size=window_size,
            #     dates=group["mrp_element_receipt_or_requirement_date"],
            # ),
            "demand_spike": rule_demand_spike_time_window(
                group,
                window_size=window_size,
            )
        }
    )
    return result


def build_results(
    df: pd.DataFrame,
    window_size: pd.Timedelta | int,
    quantile: float,
    max_materials: int | None,
    min_interval_len: int,
    if_plot: bool = False,
    include_llm: bool = False,
    language: str = "en",
) -> list[dict]:
    results = []
    material_count = 0

    for material, raw_group in df.groupby("Material Number", sort=False):
        if max_materials is not None and material_count >= max_materials:
            break

        group = raw_group.sort_values("mrp_element_receipt_or_requirement_date")
        group = group[SELECT_COLUMNS].copy()

        if len(group) <= 1:
            continue

        result = analyze_material_group(
            material=material,
            group=group,
            window_size=window_size,
            quantile=quantile,
            min_interval_len=min_interval_len,
            if_plot=if_plot,
        )

        # print(group)
        # print(result)
        '''
        local_safety_stock = compute_local_safety_stock_series(
            group,
            window_size=window_size,
            quantile=quantile,
        )
        '''
        local_safety_stock = compute_local_safety_stock_series_time_window(
            group,
            window_size=window_size,
            quantile=quantile,
        )
        
        inventory = compute_inventory(group)

        # local_safety_stock 和 inventory 作为新列加入 group，方便后续分析与输出
        try:
            group["local_safety_stock"] = local_safety_stock
            group["inventory"] = inventory
        except Exception:
            # 若长度或索引不匹配则回退为逐元素赋值（更健壮）
            for i, val in enumerate(local_safety_stock):
                if i < len(group):
                    group.at[group.index[i], "local_safety_stock"] = val
            for i, val in enumerate(inventory):
                if i < len(group):
                    group.at[group.index[i], "inventory"] = val

        if include_llm:
            llm_output = analyze_with_llm(result, group, language=language)
            print(llm_output)
            # 将大模型输出追加存入文本文件，便于后续审阅
            try:
                with open(LLM_OUTPUTS_PATH, "a", encoding="utf-8") as f:
                    f.write(f"--- Material: {material} ---\n")
                    # 有些 llm_output 可能不是纯字符串，保证以可读形式写入
                    f.write(llm_output if isinstance(llm_output, str) else repr(llm_output))
                    f.write("\n\n")
            except Exception as _e:
                # 写入失败不影响主流程，但打印日志便于排查
                print("Failed to write llm output:", _e)

        results.append(result)
        material_count += 1

    return results


def build_summary_frame(results: list[dict]) -> pd.DataFrame:
    summary_rows = []

    for result in results:
        safety_stock_series = result["safety_stock_series"]
        interval_ranges = result["interval_ranges"]
        delay_steps = result.get("delay_steps", [])

        summary_rows.append(
            {
                "material": result["material"],
                "window_size": result["window_size"],
                "latest_safety_stock": round(safety_stock_series[-1], 2),
                "mean_safety_stock": round(
                    sum(safety_stock_series) / len(safety_stock_series), 2
                ),
                "shortage_interval_count": len(result["intervals"]),
                "first_interval": format_interval_preview(interval_ranges),
                "Normal": result["Normal"],
                "toolate": result.get("toolate"),
                "max_delay_days": summarize_delay_steps(delay_steps),
                "gradual_shortage": result.get("gradual_shortage"),
                "fluctuation": result.get("fluctuation"),
                "demand_spike": result.get("demand_spike"),
                "risk_score": result.get("risk_score"),
                "risk_level": result.get("risk_level"),
            }
        )

    return pd.DataFrame(summary_rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local-window safety stock analysis.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_PATH,
        help="Input Excel file.",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=5,
        help="Sliding window size over ordered events.",
    )
    parser.add_argument(
        "--time-window-size",
        type=str,
        default="14D",
        help="Time window size over ordered events.",
    )
    parser.add_argument(
        "--quantile",
        type=float,
        default=0.75,
        help="Quantile used inside each local window.",
    )
    parser.add_argument(
        "--max-materials",
        type=int,
        default=20,
        help="Maximum number of materials to process. Use -1 for all.",
    )
    parser.add_argument(
        "--min-interval-len",
        type=int,
        default=1,
        help="Minimum shortage interval length.",
    )
    parser.add_argument(
        "--show-detail",
        action="store_true",
        help="Print the full detail table instead of the compact summary.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Plot inventory and safety stock curves with highlighted shortage intervals.",
        default=False,
    )
    args = parser.parse_args()

    time_window_size = parse_window(args.time_window_size)

    if args.window_size <= 0:
        raise ValueError("--window-size must be positive")
    if not 0 < args.quantile <= 1: 
        raise ValueError("--quantile must be in (0, 1]")
    if args.min_interval_len <= 0:
        raise ValueError("--min-interval-len must be positive")

    max_materials = None if args.max_materials == -1 else args.max_materials

    df = load_data(args.input)
    results = build_results(
        df,
        # window_size=args.window_size,
        window_size=time_window_size,
        quantile=args.quantile,
        max_materials=max_materials,
        min_interval_len=args.min_interval_len,
        if_plot=args.plot,
    )

    pd.set_option("display.max_colwidth", 200)
    if args.show_detail:
        print(pd.DataFrame(results).to_string(index=False))
    else:
        print(build_summary_frame(results).to_string(index=False))


if __name__ == "__main__":
    main()
