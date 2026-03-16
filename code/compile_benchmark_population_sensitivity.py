import argparse
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

def _find_repo_root():
    candidate = Path(__file__).resolve().parents[1]
    if (candidate / "result").exists():
        return candidate
    if (candidate / "island" / "result").exists():
        return candidate / "island"
    return candidate

REPO_ROOT = Path(os.environ.get("ISLAND_REPO_ROOT", str(_find_repo_root())))
CODE_ROOT = Path(__file__).resolve().parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from benchmark_population_sensitivity_config import (  # noqa: E402
    ANALYSIS_ROOT,
    COST_BUCKET_COLORS,
    FIGURES_ROOT,
    FIXED_MEDIAN_BREAKEVEN,
    RUN_MATRIX_PATH,
    SAMPLE_TABLE_PATH,
    SCENARIO_LABELS,
    SIX_REGION_SHORT_NAMES,
    TABLES_ROOT,
    annualization_factor,
    classify_six_region,
)
from build_benchmark_population_sensitivity_sample import build_and_write  # noqa: E402


BASELINE_COST_SUMMARY_FILES = {
    "output_0": REPO_ROOT / "result" / "island_cost_summary_0.csv",
    "output_2050": REPO_ROOT / "result" / "island_cost_summary_2050.csv",
}

BASELINE_VIABILITY_FILE = REPO_ROOT / "result" / "island_viability_summary_electric.csv"
POPULATION_STAGE_ORDER = ["500", "2000", "10000", "actual"]
COST_BUCKET_ORDER = ["renewable", "storage", "lng", "other", "discard", "load_shedding"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compile all-island benchmark population sensitivity outputs into aggregate tables and figures."
    )
    parser.add_argument(
        "--sample-file",
        default=str(SAMPLE_TABLE_PATH),
        help="Path to the sample table CSV.",
    )
    parser.add_argument(
        "--run-matrix-file",
        default=str(RUN_MATRIX_PATH),
        help="Path to the run matrix CSV.",
    )
    return parser.parse_args()


def ensure_inputs(sample_path, run_matrix_path):
    sample_path = Path(sample_path)
    run_matrix_path = Path(run_matrix_path)
    if sample_path.exists() and run_matrix_path.exists():
        return
    build_and_write(sample_path=sample_path, run_matrix_path=run_matrix_path)


def cost_file_to_dict(cost_df):
    return dict(zip(cost_df["Cost_Item"], cost_df["Cost_Value"]))


def capacity_file_to_dict(capacity_df):
    return dict(zip(capacity_df["Device"], capacity_df["Optimal_Capacity"]))


def compute_cost_buckets(capacity_dict, cost_dict):
    factor = annualization_factor()

    def capacity(device):
        return float(capacity_dict.get(device, 0.0))

    renewable_devices = ["PV", "WT", "WEC"]
    electrical_storage_devices = ["ESS", "H2S", "PEM", "FC"]
    thermal_storage_devices = ["TES", "CES"]
    other_devices = ["CHP", "EB", "AC", "LNGV"]

    from benchmark_population_sensitivity_config import FIXED_OM_COST, INVESTMENT_COST

    renewable_cost = sum(capacity(d) * INVESTMENT_COST[d] * factor for d in renewable_devices) + sum(
        capacity(d) * FIXED_OM_COST[d] for d in renewable_devices
    )
    electrical_storage_cost = sum(
        capacity(d) * INVESTMENT_COST[d] * factor for d in electrical_storage_devices
    ) + sum(capacity(d) * FIXED_OM_COST[d] for d in electrical_storage_devices)
    thermal_storage_cost = sum(
        capacity(d) * INVESTMENT_COST[d] * factor for d in thermal_storage_devices
    ) + sum(capacity(d) * FIXED_OM_COST[d] for d in thermal_storage_devices)
    storage_cost = electrical_storage_cost + thermal_storage_cost

    other_cost = sum(capacity(d) * INVESTMENT_COST[d] * factor for d in other_devices) + sum(
        capacity(d) * FIXED_OM_COST[d] for d in other_devices
    )

    lng_capacity = capacity("LNG")
    lng_cost = (
        lng_capacity * INVESTMENT_COST["LNG"] * factor
        + lng_capacity * FIXED_OM_COST["LNG"]
        + float(cost_dict.get("LNG Purchase Cost", 0.0))
    )

    discard_cost = float(cost_dict.get("Energy Discard Cost (Heat/Cold)", 0.0)) + float(
        cost_dict.get("Renewable Curtailment Cost", 0.0)
    )
    load_shedding_cost = float(cost_dict.get("Load Shedding Cost", 0.0))
    total_annual_cost = float(cost_dict.get("--- TOTAL ANNUAL COST ---", 0.0))

    bucket_values = {
        "renewable": renewable_cost,
        "storage": storage_cost,
        "lng": lng_cost,
        "other": other_cost,
        "discard": discard_cost,
        "load_shedding": load_shedding_cost,
    }
    if total_annual_cost <= 0:
        total_annual_cost = sum(bucket_values.values())

    bucket_shares = {
        f"{bucket}_share": (value / total_annual_cost if total_annual_cost else 0.0)
        for bucket, value in bucket_values.items()
    }
    return bucket_values, bucket_shares, total_annual_cost


def load_baseline_frames():
    viability_df = pd.read_csv(BASELINE_VIABILITY_FILE)
    viability_df = viability_df[viability_df["scenario"].isin(SCENARIO_LABELS.keys())].copy()
    viability_df["island_id"] = viability_df["island_id"].astype(int)

    baseline_cost_frames = {}
    for scenario, path in BASELINE_COST_SUMMARY_FILES.items():
        baseline_cost_frames[scenario] = pd.read_csv(path)
    return viability_df, baseline_cost_frames


def collect_completed_runs(sample_df, run_matrix_df, viability_df):
    viability_lookup = viability_df.set_index(["island_id", "scenario"]).sort_index()
    sample_lookup = sample_df.set_index("island_id").to_dict("index")
    records = []
    missing = []

    for row in run_matrix_df.to_dict("records"):
        cost_path = REPO_ROOT / Path(row["cost_file"])
        capacity_path = REPO_ROOT / Path(row["capacity_file"])
        results_path = REPO_ROOT / Path(row["results_file"])
        if not (cost_path.exists() and capacity_path.exists() and results_path.exists()):
            missing.append(
                {
                    **row,
                    "cost_exists": cost_path.exists(),
                    "capacity_exists": capacity_path.exists(),
                    "results_exists": results_path.exists(),
                }
            )
            continue

        baseline = viability_lookup.loc[(int(row["island_id"]), row["scenario"])]
        if hasattr(baseline, "iloc"):
            baseline = baseline.iloc[0]
        sample_meta = sample_lookup[int(row["island_id"])]

        cost_df = pd.read_csv(cost_path)
        capacity_df = pd.read_csv(capacity_path)
        cost_dict = cost_file_to_dict(cost_df)
        capacity_dict = capacity_file_to_dict(capacity_df)
        bucket_values, bucket_shares, total_annual_cost = compute_cost_buckets(capacity_dict, cost_dict)

        billed_kwh = float(baseline["consumption_pc_kwh"]) * float(row["target_population"])
        tariff_breakeven = total_annual_cost / billed_kwh if billed_kwh else float("nan")
        tariff_affordable = float(baseline["tariff_affordable"])
        six_region = classify_six_region(
            tariff_breakeven=tariff_breakeven,
            tariff_affordable=tariff_affordable,
            median_breakeven=FIXED_MEDIAN_BREAKEVEN,
        )

        record = {
            **row,
            "country": sample_meta["country"],
            "climate_zone": sample_meta["climate_zone"],
            "size_tier": sample_meta["size_tier"],
            "consumption_pc_kwh": float(baseline["consumption_pc_kwh"]),
            "billed_kwh": billed_kwh,
            "total_annual_cost": total_annual_cost,
            "tariff_breakeven": tariff_breakeven,
            "tariff_affordable": tariff_affordable,
            "viability_gap": tariff_breakeven - tariff_affordable,
            "is_feasible": tariff_breakeven <= tariff_affordable,
            "six_region": six_region,
            "six_region_short": SIX_REGION_SHORT_NAMES[six_region],
            "dominant_cost_bucket": max(bucket_values, key=bucket_values.get),
        }
        record.update({f"{bucket}_cost": value for bucket, value in bucket_values.items()})
        record.update(bucket_shares)
        records.append(record)

    return pd.DataFrame(records), pd.DataFrame(missing)


def write_sample_table(sample_df):
    TABLES_ROOT.mkdir(parents=True, exist_ok=True)
    output = TABLES_ROOT / "Table_Sx_population_benchmark_sample_all_gt500.csv"
    sample_df.to_csv(output, index=False)
    return output


def write_missing_runs(missing_df):
    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    output = ANALYSIS_ROOT / "missing_runs.csv"
    missing_df.to_csv(output, index=False)
    return output


def write_run_results(run_results_df):
    TABLES_ROOT.mkdir(parents=True, exist_ok=True)
    output = TABLES_ROOT / "run_results_long.csv"
    run_results_df.to_csv(output, index=False)
    return output


def write_reproduction_check(run_results_df, viability_df, baseline_cost_frames):
    sensitivity_500 = run_results_df[run_results_df["population_label"] == "500"].copy()
    if sensitivity_500.empty:
        return None

    baseline_viability = viability_df.set_index(["island_id", "scenario"]).sort_index()
    comparison_rows = []
    for scenario, baseline_cost_df in baseline_cost_frames.items():
        scenario_runs = sensitivity_500[sensitivity_500["scenario"] == scenario].copy()
        if scenario_runs.empty:
            continue

        scenario_runs = scenario_runs.merge(
            baseline_cost_df[baseline_cost_df["population"] == 500],
            left_on=["latitude", "longitude"],
            right_on=["lat", "lon"],
            how="left",
        )
        per_capita_cols = [
            "renewable_cost_per_capita", "storage_cost_per_capita", "lng_cost_per_capita",
            "other_equipment_cost_per_capita", "discard_cost_per_capita", "load_shedding_cost_per_capita",
        ]
        if not all(c in scenario_runs.columns for c in per_capita_cols):
            continue
        if "total_cost_per_capita" not in scenario_runs.columns:
            scenario_runs["total_cost_per_capita"] = scenario_runs[per_capita_cols].sum(axis=1)
        scenario_runs = scenario_runs.dropna(subset=["total_cost_per_capita"])
        for row in scenario_runs.to_dict("records"):
            _bt = baseline_viability.loc[(int(row["island_id"]), scenario), "tariff_breakeven"]
            baseline_tariff = float(_bt.iloc[0] if hasattr(_bt, "iloc") else _bt)
            baseline_total = float(row["total_cost_per_capita"])
            baseline_shares = {
                "renewable": row["renewable_cost_per_capita"] / baseline_total if baseline_total else 0.0,
                "storage": row["storage_cost_per_capita"] / baseline_total if baseline_total else 0.0,
                "lng": row["lng_cost_per_capita"] / baseline_total if baseline_total else 0.0,
                "other": row["other_equipment_cost_per_capita"] / baseline_total if baseline_total else 0.0,
                "discard": row["discard_cost_per_capita"] / baseline_total if baseline_total else 0.0,
                "load_shedding": row["load_shedding_cost_per_capita"] / baseline_total if baseline_total else 0.0,
            }

            comparison = {
                "scenario": scenario,
                "island_id": row["island_id"],
                "display_name": row["display_name"],
                "tariff_breakeven_baseline": baseline_tariff,
                "tariff_breakeven_sensitivity": row["tariff_breakeven"],
                "tariff_pct_diff": abs(row["tariff_breakeven"] / baseline_tariff - 1.0) * 100 if baseline_tariff else 0.0,
            }
            share_pass = True
            for bucket in COST_BUCKET_ORDER:
                diff_pp = abs(row[f"{bucket}_share"] - baseline_shares[bucket]) * 100
                comparison[f"{bucket}_share_diff_pp"] = diff_pp
                if bucket in {"renewable", "storage", "lng", "other"} and diff_pp > 2.0:
                    share_pass = False
            comparison["tariff_pass"] = comparison["tariff_pct_diff"] <= 1.0
            comparison["cost_share_pass"] = share_pass
            comparison_rows.append(comparison)

    if not comparison_rows:
        return None
    output = TABLES_ROOT / "reproduction_check.csv"
    pd.DataFrame(comparison_rows).to_csv(output, index=False)
    return output


def build_actual_transition_frame(run_results_df):
    baseline = run_results_df[run_results_df["population_label"] == "500"].copy()
    actual = run_results_df[run_results_df["population_label"] == "actual"].copy()
    merged = baseline.merge(
        actual,
        on=["island_id", "scenario"],
        suffixes=("_500", "_actual"),
    )
    if merged.empty:
        return merged

    merged["unchanged_feasibility"] = merged["is_feasible_500"] == merged["is_feasible_actual"]
    merged["unchanged_six_region"] = merged["six_region_500"] == merged["six_region_actual"]
    merged["dominant_bucket_changed"] = merged["dominant_cost_bucket_500"] != merged["dominant_cost_bucket_actual"]
    merged["pct_delta_lcoe_actual"] = (
        (merged["tariff_breakeven_actual"] - merged["tariff_breakeven_500"])
        / merged["tariff_breakeven_500"]
        * 100
    )
    return merged


def summarize_transitions(transition_df, group_cols):
    summary = (
        transition_df.groupby(group_cols, as_index=False)
        .agg(
            islands=("island_id", "count"),
            unchanged_feasibility_count=("unchanged_feasibility", "sum"),
            unchanged_six_region_count=("unchanged_six_region", "sum"),
            dominant_bucket_changed_count=("dominant_bucket_changed", "sum"),
            median_pct_delta_lcoe_actual=("pct_delta_lcoe_actual", "median"),
            p10_pct_delta_lcoe_actual=("pct_delta_lcoe_actual", lambda values: values.quantile(0.10)),
            p90_pct_delta_lcoe_actual=("pct_delta_lcoe_actual", lambda values: values.quantile(0.90)),
        )
    )
    summary["unchanged_feasibility_share"] = summary["unchanged_feasibility_count"] / summary["islands"]
    summary["unchanged_six_region_share"] = summary["unchanged_six_region_count"] / summary["islands"]
    summary["dominant_bucket_changed_share"] = summary["dominant_bucket_changed_count"] / summary["islands"]
    return summary


def write_classification_stability(run_results_df):
    transition_df = build_actual_transition_frame(run_results_df)
    if transition_df.empty:
        return None

    overall = summarize_transitions(transition_df, ["scenario"])
    overall["summary_level"] = "overall"

    by_group = summarize_transitions(
        transition_df,
        ["scenario", "climate_zone_500", "size_tier_500"],
    ).rename(
        columns={
            "climate_zone_500": "climate_zone",
            "size_tier_500": "size_tier",
        }
    )
    by_group["summary_level"] = "climate_zone_size_tier"

    output = TABLES_ROOT / "Table_Sy_classification_stability.csv"
    pd.concat([overall, by_group], ignore_index=True, sort=False).to_csv(output, index=False)
    return output


def write_actual_delta_summary(run_results_df):
    transition_df = build_actual_transition_frame(run_results_df)
    if transition_df.empty:
        return None

    summary = summarize_transitions(
        transition_df,
        ["scenario", "climate_zone_500", "size_tier_500"],
    ).rename(
        columns={
            "climate_zone_500": "climate_zone",
            "size_tier_500": "size_tier",
        }
    )
    output = TABLES_ROOT / "Table_Sz_actual_population_delta_summary.csv"
    summary.to_csv(output, index=False)
    return output


def plot_delta_distribution(run_results_df):
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)
    import matplotlib as mpl
    import numpy as np

    POP_BINS = [500, 1000, 2000, 5000, 10000, float("inf")]
    POP_BIN_LABELS = ["500–1k", "1k–2k", "2k–5k", "5k–10k", ">10k"]
    SCENARIO_LIST = ["output_0", "output_2050"]
    SCENARIO_COLORS = {"output_0": "black", "output_2050": "black"}
    SCENARIO_FILL = {"output_0": "#4393C3", "output_2050": "#D6604D"}

    # Nature Communications font settings
    mpl.rcParams.update({
        "font.family": "Arial",
        "font.size": 7,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    baseline = run_results_df[run_results_df["population_label"] == "500"][
        ["island_id", "scenario", "tariff_breakeven"]
    ].rename(columns={"tariff_breakeven": "tariff_breakeven_500"})
    deltas = run_results_df.merge(baseline, on=["island_id", "scenario"], how="left")
    deltas = deltas[deltas["population_label"] != "500"].copy()
    if deltas.empty:
        return None

    deltas["pct_delta_lcoe"] = (
        (deltas["tariff_breakeven"] - deltas["tariff_breakeven_500"]) / deltas["tariff_breakeven_500"] * 100
    )
    deltas = deltas[deltas["pct_delta_lcoe"].abs() <= 100].copy()
    deltas["pop_bin"] = pd.cut(
        deltas["target_population"],
        bins=POP_BINS,
        labels=POP_BIN_LABELS,
        right=False,
    )

    # Figure: 183 mm wide (Nature Comms double-column), 70 mm tall
    fig, axes = plt.subplots(
        1, len(SCENARIO_LIST),
        figsize=(7.2, 2.75),
        dpi=300,
        sharey=True,
    )
    fig.subplots_adjust(wspace=0.08)

    positions = list(range(len(POP_BIN_LABELS)))

    for ax, scenario in zip(axes, SCENARIO_LIST):
        color_edge = SCENARIO_COLORS[scenario]
        color_fill = SCENARIO_FILL[scenario]
        df_s = deltas[deltas["scenario"] == scenario]

        for i, label in enumerate(POP_BIN_LABELS):
            vals = df_s[df_s["pop_bin"] == label]["pct_delta_lcoe"].dropna().values
            if len(vals) < 4:
                ax.scatter(
                    [i], [np.median(vals)] if len(vals) else [0],
                    color=color_edge, s=12, zorder=5,
                )
                continue

            # Kernel density estimate for violin
            from scipy.stats import gaussian_kde
            kde = gaussian_kde(vals, bw_method=0.35)
            v_range = np.linspace(vals.min(), vals.max(), 200)
            density = kde(v_range)
            # Normalise to half-width = 0.38
            half_width = 0.38
            density = density / density.max() * half_width

            ax.fill_betweenx(v_range, i - density, i + density,
                             color=color_fill, linewidth=0)
            ax.plot(i - density, v_range, color=color_edge, linewidth=0.6)
            ax.plot(i + density, v_range, color=color_edge, linewidth=0.6)

            # IQR bar + median line
            q25, q50, q75 = np.percentile(vals, [25, 50, 75])
            ax.plot([i, i], [q25, q75], color=color_edge, linewidth=2.0, solid_capstyle="butt", zorder=4)
            ax.scatter([i], [q50], color="white", s=16, zorder=5,
                       edgecolors=color_edge, linewidths=0.8)

        # Zero reference line
        ax.axhline(0, color="#C0392B", linewidth=0.9, linestyle="--", zorder=3)

        ax.set_xticks(positions)
        ax.set_xticklabels(POP_BIN_LABELS, fontsize=6.5, rotation=30, ha="right")
        ax.set_xlim(-0.6, len(POP_BIN_LABELS) - 0.4)
        ax.set_xlabel("Target population", fontsize=7.5)
        ax.set_title("")
        ax.grid(False)
        ax.tick_params(labelsize=6.5)

        # Count annotation at top
        n_total = len(df_s["island_id"].unique())
        # ax.text(
        #     0.97, 0.97, f"n = {n_total} islands",
        #     transform=ax.transAxes,
        #     ha="right", va="top", fontsize=6, color="#555555",
        # )

    axes[0].set_ylabel("%\u0394LCOE vs 500-person benchmark", fontsize=7.5)
    axes[1].set_ylabel("")

    # Shared legend
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor=SCENARIO_FILL[s], edgecolor=SCENARIO_COLORS[s],
              linewidth=0.8, label=SCENARIO_LABELS[s])
        for s in SCENARIO_LIST
    ]
    legend_handles.append(
        plt.Line2D([0], [0], color="#C0392B", linewidth=0.9, linestyle="--", label="No change (0%)")
    )
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=6.5,
        bbox_to_anchor=(0.5, -0.20),
    )

    output = FIGURES_ROOT / "Figure_Sy_lcoe_delta_distribution.png"
    fig.savefig(output, bbox_inches="tight", dpi=300)
    plt.close(fig)

    # Reset rcParams to defaults to avoid affecting subsequent plots
    mpl.rcParams.update(mpl.rcParamsDefault)
    return output


def plot_cost_composition(run_results_df):
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)
    grouped = (
        run_results_df.groupby(["scenario", "population_label"], as_index=False)[
            [f"{bucket}_share" for bucket in COST_BUCKET_ORDER]
        ]
        .median()
    )
    if grouped.empty:
        return None

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), dpi=300, sharey=True)
    for ax, scenario in zip(axes, ["output_0", "output_2050"]):
        plot_df = grouped[grouped["scenario"] == scenario].set_index("population_label").reindex(POPULATION_STAGE_ORDER)
        if plot_df.empty:
            ax.axis("off")
            continue

        bottom = pd.Series([0.0] * len(plot_df), index=plot_df.index)
        positions = range(len(plot_df.index))
        for bucket in COST_BUCKET_ORDER:
            values = plot_df[f"{bucket}_share"].fillna(0.0) * 100
            ax.bar(
                positions,
                values.values,
                bottom=bottom.values * 100,
                color=COST_BUCKET_COLORS[bucket],
                label=bucket.replace("_", " ").title(),
                width=0.75,
            )
            bottom += plot_df[f"{bucket}_share"].fillna(0.0)

        ax.set_title("")
        ax.set_xticks(list(positions))
        ax.set_xticklabels(plot_df.index.tolist())
        ax.set_ylim(0, 100)
        ax.set_ylabel("Median cost share (%)")
        ax.grid(axis="y", alpha=0.2)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.05))
    fig.tight_layout()
    output = FIGURES_ROOT / "Figure_Sz_cost_composition.png"
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)
    return output


def plot_actual_population_scatter(run_results_df):
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)
    transition_df = build_actual_transition_frame(run_results_df)
    if transition_df.empty:
        return None

    plt.figure(figsize=(11, 6.5), dpi=300)
    sns.scatterplot(
        data=transition_df,
        x="actual_population_500",
        y="pct_delta_lcoe_actual",
        hue="scenario",
        palette={"output_0": "#0B75B3", "output_2050": "#982B2D"},
        s=30,
    )
    plt.xscale("log")
    plt.axhline(0, color="#666666", linewidth=1, linestyle="--")
    plt.xlabel("Actual population")
    plt.ylabel("%Delta LCOE: actual population vs 500 benchmark")
    plt.title("")
    plt.legend(loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=False)
    plt.tight_layout()
    output = FIGURES_ROOT / "Figure_optional_actual_population_scatter.png"
    plt.savefig(output, bbox_inches="tight")
    plt.close()
    return output


def plot_viability_gap_change(run_results_df):
    """Show how viability gap shrinks with population while infeasibility persists."""
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)
    POP_BINS = [500, 1000, 2000, 5000, 10000, float("inf")]
    POP_BIN_LABELS = ["500–1k", "1k–2k", "2k–5k", "5k–10k", ">10k"]
    SCENARIO_LIST = ["output_0", "output_2050"]

    baseline = run_results_df[run_results_df["population_label"] == "500"][
        ["island_id", "scenario", "tariff_breakeven", "viability_gap", "is_feasible"]
    ].rename(columns={
        "tariff_breakeven": "tariff_breakeven_500",
        "viability_gap": "viability_gap_500",
        "is_feasible": "is_feasible_500",
    })

    others = run_results_df[run_results_df["population_label"] != "500"].copy()
    others["pop_bin"] = pd.cut(
        others["target_population"], bins=POP_BINS, labels=POP_BIN_LABELS, right=False
    )
    merged = others.merge(baseline, on=["island_id", "scenario"], how="inner")

    # Only infeasible-at-baseline islands (the ones that matter for the argument)
    infeasible = merged[~merged["is_feasible_500"]].copy()
    if infeasible.empty:
        return None

    infeasible["gap_delta_pp"] = infeasible["viability_gap"] - infeasible["viability_gap_500"]
    infeasible["still_infeasible"] = ~infeasible["is_feasible"]

    fig, axes = plt.subplots(1, len(SCENARIO_LIST), figsize=(13, 5), dpi=300, sharey=True)
    for ax, scenario in zip(axes, SCENARIO_LIST):
        df = infeasible[infeasible["scenario"] == scenario]
        if df.empty:
            ax.axis("off")
            continue

        # Boxplot of gap change
        data_by_bin = [
            df[df["pop_bin"] == b]["gap_delta_pp"].dropna().values
            for b in POP_BIN_LABELS
        ]
        bp = ax.boxplot(
            data_by_bin,
            positions=range(len(POP_BIN_LABELS)),
            widths=0.6,
            patch_artist=True,
            showfliers=False,
            medianprops=dict(color="black", linewidth=1.5),
        )
        for patch in bp["boxes"]:
            patch.set_facecolor("#AED6F1")

        # Overlay: % still infeasible per bin
        ax2 = ax.twinx()
        still_infeasible_pct = [
            df[df["pop_bin"] == b]["still_infeasible"].mean() * 100
            for b in POP_BIN_LABELS
        ]
        ax2.plot(
            range(len(POP_BIN_LABELS)),
            still_infeasible_pct,
            color="#C0392B", marker="o", linewidth=2, markersize=6, label="Still infeasible (%)",
        )
        ax2.set_ylim(0, 110)
        ax2.set_ylabel("Still infeasible (%)", color="#C0392B", fontsize=9)
        ax2.tick_params(axis="y", colors="#C0392B")
        ax2.axhline(90, color="#C0392B", linewidth=0.8, linestyle=":")

        ax.axhline(0, color="#666666", linewidth=1, linestyle="--")
        ax.set_xticks(range(len(POP_BIN_LABELS)))
        ax.set_xticklabels(POP_BIN_LABELS, fontsize=9)
        ax.set_xlabel("Target population")
        ax.set_ylabel("Change in viability gap ($/kWh)" if scenario == SCENARIO_LIST[0] else "")
        ax.set_title("")
        ax.grid(axis="y", alpha=0.2)

        # Auto-scale y-axis to data range with padding
        all_vals = infeasible[infeasible["scenario"] == scenario]["gap_delta_pp"].dropna()
        if not all_vals.empty:
            lo, hi = all_vals.quantile(0.05), all_vals.quantile(0.95)
            pad = max(abs(hi - lo) * 0.3, 0.01)
            ax.set_ylim(lo - pad, hi + pad)

    handles2, labels2 = ax2.get_legend_handles_labels()
    fig.legend(handles2, labels2, loc="lower center", ncol=1, frameon=False,
               bbox_to_anchor=(0.5, -0.04), fontsize=8)
    fig.tight_layout()
    output = FIGURES_ROOT / "Figure_Sw_viability_gap_change.png"
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)
    return output


def plot_classification_stability(run_results_df):
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)

    POP_BINS = [500, 1000, 2000, 5000, 10000, float("inf")]
    POP_BIN_LABELS = ["500–1k", "1k–2k", "2k–5k", "5k–10k", ">10k"]
    SCENARIO_LIST = ["output_0", "output_2050"]
    SCENARIO_COLORS = {
        "output_0": "#2166AC",
        "output_2050": "#D6604D",
    }

    baseline = run_results_df[run_results_df["population_label"] == "500"][
        ["island_id", "scenario", "is_feasible"]
    ].rename(columns={"is_feasible": "is_feasible_500"})

    others = run_results_df[run_results_df["population_label"] != "500"].copy()
    others["pop_bin"] = pd.cut(
        others["target_population"],
        bins=POP_BINS,
        labels=POP_BIN_LABELS,
        right=False,
    )

    merged = others.merge(baseline, on=["island_id", "scenario"], how="inner")
    merged["unchanged"] = merged["is_feasible"] == merged["is_feasible_500"]

    if merged.empty:
        return None

    stability = (
        merged.groupby(["scenario", "pop_bin"], observed=True)
        .agg(
            stability_pct=("unchanged", lambda x: x.mean() * 100),
            n=("island_id", "nunique"),
        )
        .reset_index()
    )

    import numpy as np
    n_bins = len(POP_BIN_LABELS)
    n_sc = len(SCENARIO_LIST)
    bar_width = 0.35
    x = np.arange(n_bins)

    fig, ax = plt.subplots(figsize=(7, 3.5), dpi=300)

    for si, scenario in enumerate(SCENARIO_LIST):
        df = stability[stability["scenario"] == scenario].set_index("pop_bin").reindex(POP_BIN_LABELS)
        offsets = x + (si - (n_sc - 1) / 2) * bar_width
        vals = df["stability_pct"].fillna(0).values
        ax.bar(
            offsets, vals,
            width=bar_width,
            color=SCENARIO_COLORS[scenario],
            alpha=0.8,
            edgecolor="none",
            label=SCENARIO_LABELS[scenario],
        )
        for xi, val in enumerate(vals):
            if val > 0:
                ax.text(
                    offsets[xi], val + 0.5,
                    f"{val:.0f}%",
                    ha="center", va="bottom", fontsize=7,
                    color=SCENARIO_COLORS[scenario],
                )

    ax.axhline(95, color="#555555", linewidth=0.8, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels(POP_BIN_LABELS, fontsize=9)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Islands with unchanged feasibility (%)")
    ax.set_xlabel("Target population")
    ax.set_title("")
    ax.grid(False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.legend(loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.15), fontsize=9)
    fig.tight_layout()
    output = FIGURES_ROOT / "Figure_Sx_classification_stability.png"
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)
    return output


def main():
    args = parse_args()
    ensure_inputs(args.sample_file, args.run_matrix_file)

    sample_df = pd.read_csv(args.sample_file)
    run_matrix_df = pd.read_csv(args.run_matrix_file)
    viability_df, baseline_cost_frames = load_baseline_frames()

    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    write_sample_table(sample_df)

    run_results_df, missing_df = collect_completed_runs(sample_df, run_matrix_df, viability_df)
    write_missing_runs(missing_df)

    if run_results_df.empty:
        print("No completed sensitivity runs found. Wrote sample table and missing run report only.")
        return

    write_run_results(run_results_df)
    write_reproduction_check(run_results_df, viability_df, baseline_cost_frames)
    write_classification_stability(run_results_df)
    write_actual_delta_summary(run_results_df)
    plot_delta_distribution(run_results_df)
    plot_cost_composition(run_results_df)
    plot_actual_population_scatter(run_results_df)
    plot_viability_gap_change(run_results_df)
    plot_classification_stability(run_results_df)
    print(f"Compiled {len(run_results_df)} completed sensitivity runs.")


if __name__ == "__main__":
    main()
