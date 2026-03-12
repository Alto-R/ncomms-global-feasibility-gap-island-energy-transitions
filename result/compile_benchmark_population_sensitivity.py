import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = REPO_ROOT / "code"
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
    viability_lookup = viability_df.set_index(["island_id", "scenario"])
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

    baseline_viability = viability_df.set_index(["island_id", "scenario"])
    comparison_rows = []
    for scenario, baseline_cost_df in baseline_cost_frames.items():
        scenario_runs = sensitivity_500[sensitivity_500["scenario"] == scenario].copy()
        if scenario_runs.empty:
            continue

        scenario_runs = scenario_runs.merge(
            baseline_cost_df,
            left_on=["latitude", "longitude"],
            right_on=["lat", "lon"],
            how="left",
        )
        scenario_runs = scenario_runs.dropna(subset=["total_cost_per_capita"])
        for row in scenario_runs.to_dict("records"):
            baseline_tariff = float(
                baseline_viability.loc[(int(row["island_id"]), scenario), "tariff_breakeven"]
            )
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

    plt.figure(figsize=(11, 6.5), dpi=300)
    sns.boxplot(
        data=deltas,
        x="population_label",
        y="pct_delta_lcoe",
        hue="scenario_label",
        order=["2000", "10000", "actual"],
        showfliers=False,
    )
    plt.axhline(0, color="#666666", linewidth=1, linestyle="--")
    plt.xlabel("Population level")
    plt.ylabel("%Delta LCOE vs 500-person benchmark")
    plt.title("All-island LCOE sensitivity distribution across population levels")
    plt.tight_layout()
    output = FIGURES_ROOT / "Figure_Sy_lcoe_delta_distribution.png"
    plt.savefig(output, bbox_inches="tight")
    plt.close()
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

        ax.set_title(SCENARIO_LABELS[scenario])
        ax.set_xticks(list(positions))
        ax.set_xticklabels(plot_df.index.tolist())
        ax.set_ylim(0, 100)
        ax.set_ylabel("Median cost share (%)")
        ax.grid(axis="y", alpha=0.2)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=6, frameon=False)
    fig.suptitle("All-island median cost composition across population levels", y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
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
        alpha=0.6,
        s=30,
    )
    plt.xscale("log")
    plt.axhline(0, color="#666666", linewidth=1, linestyle="--")
    plt.xlabel("Actual population")
    plt.ylabel("%Delta LCOE: actual population vs 500 benchmark")
    plt.title("All-island actual-population sensitivity against island size")
    plt.tight_layout()
    output = FIGURES_ROOT / "Figure_optional_actual_population_scatter.png"
    plt.savefig(output, bbox_inches="tight")
    plt.close()
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
    print(f"Compiled {len(run_results_df)} completed sensitivity runs.")


if __name__ == "__main__":
    main()
