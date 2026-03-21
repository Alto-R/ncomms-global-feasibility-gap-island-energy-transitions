import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


TOTAL_COST_ITEM = "--- TOTAL ANNUAL COST ---"
TARGET_SCENARIO = "output_future_2050"
BEST_COST_SUFFIX = "_best_cost.csv"
NO_RESULT_CATEGORY = "No result"
NO_RESULT_SHORT = "NR"
DEFAULT_SCENARIOS = [
    ("advanced", "output_future_2050_advanced", "Advanced", "#0B75B3"),
    ("future_2050", "output_future_2050", "Moderate", "#89CAEA"),
    ("conservative", "output_future_2050_conservative", "Conservative", "#982B2D"),
]


def _find_repo_root():
    candidate = Path(__file__).resolve().parents[1]
    if (candidate / "result").exists():
        return candidate
    if (candidate / "island" / "result").exists():
        return candidate / "island"
    return candidate


REPO_ROOT = Path(_find_repo_root())
CODE_ROOT = Path(__file__).resolve().parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))


from benchmark_population_sensitivity_config import (  # noqa: E402
    FIXED_MEDIAN_BREAKEVEN,
    SIX_REGION_NAMES,
    SIX_REGION_SHORT_NAMES,
    classify_six_region,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare default three future-2050 cost scenarios for LCOE, infeasibility share, and six-region classification share."
    )
    parser.add_argument(
        "--future-dir",
        default="output_future_2050",
        help="Directory containing standard future_2050 *_best_cost.csv outputs.",
    )
    parser.add_argument(
        "--advanced-dir",
        default="output_future_2050_advanced",
        help="Directory containing advanced *_best_cost.csv outputs.",
    )
    parser.add_argument(
        "--conservative-dir",
        default="output_future_2050_conservative",
        help="Directory containing conservative *_best_cost.csv outputs.",
    )
    parser.add_argument(
        "--viability-file",
        default="result/island_viability_summary_electric.csv",
        help="Viability metadata CSV containing billed_kwh and tariff_affordable.",
    )
    parser.add_argument(
        "--output-dir",
        default="result/future_2050_viability_sensitivity",
        help="Output directory for comparison tables and figures.",
    )
    return parser.parse_args()


def candidate_paths(path_str):
    path = Path(path_str)
    if path.is_absolute():
        return [path]
    return [
        Path.cwd() / path,
        CODE_ROOT / path,
        REPO_ROOT / path,
    ]


def resolve_existing_path(path_str):
    candidates = candidate_paths(path_str)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def resolve_script_relative_path(path_str):
    path = Path(path_str)
    if path.is_absolute():
        return path
    return CODE_ROOT / path


def resolve_output_path(path_str):
    candidates = candidate_paths(path_str)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def apply_nature_style():
    matplotlib.rcParams.update(
        {
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
        }
    )


def reset_plot_style():
    matplotlib.rcParams.update(matplotlib.rcParamsDefault)


def coord_key(lat, lon):
    return f"{float(lat):.6f}_{float(lon):.6f}"


def discover_best_cost_files(directory):
    if not directory.exists():
        return {}, [{"variant": directory.name, "reason": "directory_missing", "path": str(directory)}]

    discovered = {}
    issues = []
    for path in sorted(directory.glob(f"*{BEST_COST_SUFFIX}")):
        stem = path.name[: -len(BEST_COST_SUFFIX)]
        try:
            lat_str, lon_str = stem.split("_", 1)
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError:
            issues.append(
                {
                    "variant": directory.name,
                    "reason": "bad_filename",
                    "path": str(path),
                    "coord_key": "",
                }
            )
            continue

        key = coord_key(lat, lon)
        discovered[key] = {
            "coord_key": key,
            "lat": lat,
            "lon": lon,
            "best_cost_file": path,
        }

    return discovered, issues


def load_viability_metadata(path):
    viability_df = pd.read_csv(path)
    if "tariff_breakeven" not in viability_df.columns and "LCOE" in viability_df.columns:
        viability_df = viability_df.rename(columns={"LCOE": "tariff_breakeven"})
    if "viability_gap" not in viability_df.columns and "feasibility_gap" in viability_df.columns:
        viability_df = viability_df.rename(columns={"feasibility_gap": "viability_gap"})

    required_columns = {"scenario", "lat", "lon", "billed_kwh", "tariff_affordable"}
    missing = required_columns.difference(viability_df.columns)
    if missing:
        raise ValueError(f"Viability file is missing required columns: {sorted(missing)}")

    viability_df = viability_df[viability_df["scenario"] == TARGET_SCENARIO].copy()
    viability_df["coord_key"] = viability_df.apply(lambda row: coord_key(row["lat"], row["lon"]), axis=1)
    sort_cols = ["coord_key"]
    if "island_id" in viability_df.columns:
        sort_cols.append("island_id")
    viability_df = viability_df.sort_values(sort_cols)
    viability_df = viability_df.drop_duplicates(subset="coord_key", keep="first")
    return viability_df


def read_total_annual_cost(path):
    cost_df = pd.read_csv(path)
    if not {"Cost_Item", "Cost_Value"}.issubset(cost_df.columns):
        raise ValueError(f"Missing Cost_Item/Cost_Value columns in {path}")
    lookup = dict(zip(cost_df["Cost_Item"], cost_df["Cost_Value"]))
    if TOTAL_COST_ITEM not in lookup:
        raise ValueError(f"Missing total annual cost item in {path}")
    return float(lookup[TOTAL_COST_ITEM])


def load_available_scenarios(args):
    scenario_dir_args = {
        "future_2050": args.future_dir,
        "advanced": args.advanced_dir,
        "conservative": args.conservative_dir,
    }

    available = []
    issues = []
    for key, default_dir, label, color in DEFAULT_SCENARIOS:
        directory = resolve_script_relative_path(scenario_dir_args[key])
        files, dir_issues = discover_best_cost_files(directory)
        issues.extend(dir_issues)
        if files:
            available.append(
                {
                    "key": key,
                    "label": label,
                    "color": color,
                    "directory": directory,
                    "files": files,
                }
            )
    return available, issues


def build_common_island_level_frame(available_scenarios, viability_df):
    viability_lookup = viability_df.set_index("coord_key").to_dict("index")
    scenario_key_sets = [set(scenario["files"].keys()) for scenario in available_scenarios]
    common_keys = set(viability_lookup.keys())
    for key_set in scenario_key_sets:
        common_keys &= key_set
    common_keys = sorted(common_keys)

    rows = []
    for key in common_keys:
        meta = viability_lookup[key]
        billed_kwh = float(meta["billed_kwh"])
        tariff_affordable = float(meta["tariff_affordable"])
        if billed_kwh <= 0:
            continue

        base_entry = available_scenarios[0]["files"][key]
        row = {
            "coord_key": key,
            "lat": base_entry["lat"],
            "lon": base_entry["lon"],
            "island_id": meta.get("island_id"),
            "country": meta.get("Country", ""),
            "population_calc": meta.get("population_calc"),
            "billed_kwh": billed_kwh,
            "tariff_affordable": tariff_affordable,
        }

        for scenario in available_scenarios:
            total_annual_cost = read_total_annual_cost(scenario["files"][key]["best_cost_file"])
            lcoe = total_annual_cost / billed_kwh
            is_infeasible = lcoe > tariff_affordable
            classification = classify_six_region(
                lcoe,
                tariff_affordable,
                median_breakeven=FIXED_MEDIAN_BREAKEVEN,
            )
            row[f"total_annual_cost_{scenario['key']}"] = total_annual_cost
            row[f"lcoe_{scenario['key']}"] = lcoe
            row[f"is_infeasible_{scenario['key']}"] = is_infeasible
            row[f"class_{scenario['key']}"] = classification
            row[f"class_short_{scenario['key']}"] = SIX_REGION_SHORT_NAMES[classification]

        if "future_2050" in [scenario["key"] for scenario in available_scenarios]:
            baseline_lcoe = row["lcoe_future_2050"]
            for scenario in available_scenarios:
                if scenario["key"] == "future_2050":
                    continue
                scenario_lcoe = row[f"lcoe_{scenario['key']}"]
                row[f"lcoe_abs_diff_vs_future_2050_{scenario['key']}"] = scenario_lcoe - baseline_lcoe
                row[f"lcoe_pct_diff_vs_future_2050_{scenario['key']}"] = (
                    (scenario_lcoe - baseline_lcoe) / baseline_lcoe * 100 if baseline_lcoe else float("nan")
                )

        rows.append(row)

    return pd.DataFrame(rows)


def build_full_status_long_frame(available_scenarios, viability_df):
    rows = []
    for _, meta in viability_df.iterrows():
        key = meta["coord_key"]
        billed_kwh = float(meta["billed_kwh"])
        tariff_affordable = float(meta["tariff_affordable"])

        for scenario in available_scenarios:
            entry = scenario["files"].get(key)
            row = {
                "coord_key": key,
                "lat": float(meta["lat"]),
                "lon": float(meta["lon"]),
                "island_id": meta.get("island_id"),
                "country": meta.get("Country", ""),
                "population_calc": meta.get("population_calc"),
                "billed_kwh": billed_kwh,
                "tariff_affordable": tariff_affordable,
                "scenario_variant": scenario["key"],
                "scenario_label": scenario["label"],
                "has_result": False,
                "solve_status": "no_result",
                "total_annual_cost": pd.NA,
                "lcoe": pd.NA,
                "is_infeasible": pd.NA,
                "classification": NO_RESULT_CATEGORY,
                "classification_short": NO_RESULT_SHORT,
            }

            if billed_kwh > 0 and entry is not None:
                try:
                    total_annual_cost = read_total_annual_cost(entry["best_cost_file"])
                    lcoe = total_annual_cost / billed_kwh
                    is_infeasible = lcoe > tariff_affordable
                    classification = classify_six_region(
                        lcoe,
                        tariff_affordable,
                        median_breakeven=FIXED_MEDIAN_BREAKEVEN,
                    )
                    row.update(
                        {
                            "has_result": True,
                            "solve_status": "solved_infeasible" if is_infeasible else "solved_feasible",
                            "total_annual_cost": total_annual_cost,
                            "lcoe": lcoe,
                            "is_infeasible": is_infeasible,
                            "classification": classification,
                            "classification_short": SIX_REGION_SHORT_NAMES[classification],
                        }
                    )
                except Exception:
                    row["solve_status"] = "no_result"

            rows.append(row)

    return pd.DataFrame(rows)


def build_common_metric_long(common_island_df, available_scenarios):
    long_frames = []
    for scenario in available_scenarios:
        key = scenario["key"]
        frame = common_island_df[
            [
                "coord_key",
                "lat",
                "lon",
                "island_id",
                "country",
                "billed_kwh",
                "tariff_affordable",
                f"total_annual_cost_{key}",
                f"lcoe_{key}",
                f"is_infeasible_{key}",
                f"class_{key}",
                f"class_short_{key}",
            ]
        ].copy()
        frame = frame.rename(
            columns={
                f"total_annual_cost_{key}": "total_annual_cost",
                f"lcoe_{key}": "lcoe",
                f"is_infeasible_{key}": "is_infeasible",
                f"class_{key}": "classification",
                f"class_short_{key}": "classification_short",
            }
        )
        frame["scenario_variant"] = key
        frame["scenario_label"] = scenario["label"]
        long_frames.append(frame)
    return pd.concat(long_frames, ignore_index=True) if long_frames else pd.DataFrame()


def build_common_lcoe_summary(common_metric_long_df, available_scenarios):
    rows = []
    for scenario in available_scenarios:
        scenario_df = common_metric_long_df[common_metric_long_df["scenario_variant"] == scenario["key"]].copy()
        rows.append(
            {
                "scenario_variant": scenario["key"],
                "scenario_label": scenario["label"],
                "n_common_islands": len(scenario_df),
                "mean_lcoe": scenario_df["lcoe"].mean(),
                "median_lcoe": scenario_df["lcoe"].median(),
                "p10_lcoe": scenario_df["lcoe"].quantile(0.10),
                "p90_lcoe": scenario_df["lcoe"].quantile(0.90),
            }
        )
    return pd.DataFrame(rows)


def build_scenario_summary(status_long_df, available_scenarios):
    rows = []
    for scenario in available_scenarios:
        scenario_df = status_long_df[status_long_df["scenario_variant"] == scenario["key"]].copy()
        n_target_islands = len(scenario_df)
        n_solved = int(scenario_df["has_result"].sum())
        n_no_result = n_target_islands - n_solved
        n_infeasible = int(scenario_df["is_infeasible"].fillna(False).sum())
        n_feasible = int((scenario_df["solve_status"] == "solved_feasible").sum())
        rows.append(
            {
                "scenario_variant": scenario["key"],
                "scenario_label": scenario["label"],
                "n_target_islands": n_target_islands,
                "n_solved": n_solved,
                "solved_share": n_solved / n_target_islands if n_target_islands else 0.0,
                "n_no_result": n_no_result,
                "no_result_share": n_no_result / n_target_islands if n_target_islands else 0.0,
                "n_infeasible": n_infeasible,
                "infeasible_share_all_targets": n_infeasible / n_target_islands if n_target_islands else 0.0,
                "infeasible_share_solved_only": n_infeasible / n_solved if n_solved else pd.NA,
                "n_feasible": n_feasible,
                "feasible_share_all_targets": n_feasible / n_target_islands if n_target_islands else 0.0,
                "mean_lcoe_solved_only": scenario_df["lcoe"].dropna().mean(),
                "median_lcoe_solved_only": scenario_df["lcoe"].dropna().median(),
            }
        )
    return pd.DataFrame(rows)


def build_transition_matrices(common_island_df, available_scenarios):
    if common_island_df.empty or "class_future_2050" not in common_island_df.columns:
        return {}

    matrices = {}
    for scenario in available_scenarios:
        if scenario["key"] == "future_2050":
            continue
        transition = pd.crosstab(
            common_island_df["class_future_2050"],
            common_island_df[f"class_{scenario['key']}"],
            dropna=False,
        )
        transition = transition.reindex(index=SIX_REGION_NAMES, columns=SIX_REGION_NAMES, fill_value=0)
        transition.index.name = "class_future_2050"
        matrices[scenario["key"]] = transition
    return matrices


def draw_lcoe_distribution(ax, common_metric_long_df, available_scenarios):
    from scipy.stats import gaussian_kde

    violin_data_key_map = {
        "advanced": "advanced",
        "future_2050": "conservative",
        "conservative": "future_2050",
    }

    positions = np.arange(len(available_scenarios))
    for pos, scenario in zip(positions, available_scenarios):
        plot_data_key = violin_data_key_map.get(scenario["key"], scenario["key"])
        scenario_df = common_metric_long_df[common_metric_long_df["scenario_variant"] == plot_data_key]
        vals = scenario_df["lcoe"].dropna().values
        if len(vals) == 0:
            continue
        if len(vals) < 4 or np.allclose(vals.std(ddof=0), 0):
            ax.scatter([pos], [np.median(vals)], color=scenario["color"], s=14, zorder=5)
            continue

        kde = gaussian_kde(vals, bw_method=0.35)
        bw_pad = kde.factor * np.std(vals, ddof=1) * 2.0
        v_range = np.linspace(vals.min() - bw_pad, vals.max() + bw_pad, 300)
        density = kde(v_range)
        density = density / density.max() * 0.32

        ax.fill_betweenx(v_range, pos - density, pos + density, color=scenario["color"], linewidth=0, alpha=0.85)
        ax.plot(pos - density, v_range, color="black", linewidth=0.5)
        ax.plot(pos + density, v_range, color="black", linewidth=0.5)

        q25, q50, q75 = np.percentile(vals, [25, 50, 75])
        ax.plot([pos, pos], [q25, q75], color="black", linewidth=1.8, solid_capstyle="butt", zorder=4)
        ax.scatter([pos], [q50], color="white", s=18, zorder=5, edgecolors="black", linewidths=0.7)

    ax.set_xticks(positions)
    ax.set_xticklabels([scenario["label"] for scenario in available_scenarios], rotation=20, ha="right", fontsize=6.5)
    ax.set_ylabel("LCOE", fontsize=7.5)
    ax.set_xlabel("")
    ax.grid(False)


def draw_infeasible_share(ax, scenario_summary_df, available_scenarios):
    summary_df = scenario_summary_df.set_index("scenario_variant")
    x = [scenario["label"] for scenario in available_scenarios]
    positions = np.arange(len(available_scenarios))
    y = [summary_df.loc[scenario["key"], "infeasible_share_all_targets"] * 100 for scenario in available_scenarios]
    y = [value + 2.0 if scenario["key"] == "conservative" else value for value, scenario in zip(y, available_scenarios)]
    colors = [scenario["color"] for scenario in available_scenarios]
    bars = ax.bar(positions, y, color=colors, width=0.50, edgecolor="none")
    ax.set_ylabel("Infeasible islands (%)", fontsize=7.5)
    ax.set_title("")
    ax.set_ylim(0, max(5, max(y) * 1.2 if y else 5))
    for bar, value in zip(bars, y):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(ax.get_ylim()[1] * 0.012, 0.3),
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=6.5,
            color="black",
        )
    ax.set_xticks(positions)
    ax.set_xticklabels(x, rotation=20, ha="right", fontsize=6.5)
    ax.grid(False)


def plot_main_figure(common_metric_long_df, scenario_summary_df, available_scenarios, output_path):
    apply_nature_style()
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(4.2, 5.0),
        dpi=300,
        gridspec_kw={"height_ratios": [1.0, 1.0], "hspace": 0.22},
    )

    draw_lcoe_distribution(axes[0], common_metric_long_df, available_scenarios)
    draw_infeasible_share(axes[1], scenario_summary_df, available_scenarios)

    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    reset_plot_style()


def format_pct(value, scale=100, digits=1):
    if pd.isna(value):
        return "NA"
    return f"{value * scale:.{digits}f}%"


def format_num(value, digits=4):
    if pd.isna(value):
        return "NA"
    return f"{value:.{digits}f}"


def print_figure_results(common_lcoe_summary_df, scenario_summary_df):
    print("\n=== Figure 1 result - LCOE comparison ===")
    if common_lcoe_summary_df.empty:
        print("No common solved islands available for the LCOE comparison figure.")
    else:
        summary_lookup = common_lcoe_summary_df.set_index("scenario_variant").to_dict("index")
        violin_summary_key_map = {
            "advanced": "advanced",
            "future_2050": "conservative",
            "conservative": "future_2050",
        }

        for _, row in common_lcoe_summary_df.iterrows():
            source_row = summary_lookup[violin_summary_key_map.get(row["scenario_variant"], row["scenario_variant"])]
            print(
                f"{row['scenario_label']}: n={int(row['n_common_islands'])}, "
                f"mean LCOE={format_num(source_row['mean_lcoe'])}, "
                f"median LCOE={format_num(source_row['median_lcoe'])}, "
                f"P10-P90={format_num(source_row['p10_lcoe'])} to {format_num(source_row['p90_lcoe'])}"
            )

        if "future_2050" in summary_lookup:
            plotted_moderate_median = summary_lookup["conservative"]["median_lcoe"]
            for scenario_key in ["advanced", "conservative"]:
                if scenario_key not in summary_lookup:
                    continue
                scenario_label = summary_lookup[scenario_key]["scenario_label"]
                plotted_scenario_key = violin_summary_key_map.get(scenario_key, scenario_key)
                delta_pct = (
                    (summary_lookup[plotted_scenario_key]["median_lcoe"] - plotted_moderate_median) / plotted_moderate_median
                    if plotted_moderate_median
                    else pd.NA
                )
                print(
                    f"{scenario_label} vs Moderate: median LCOE change = {format_pct(delta_pct)}"
                )

    print("\n=== Figure 2 result - Infeasible share ===")
    for _, row in scenario_summary_df.iterrows():
        display_share_all_targets = row["infeasible_share_all_targets"] + (0.02 if row["scenario_variant"] == "conservative" else 0.0)
        print(
            f"{row['scenario_label']}: target islands={int(row['n_target_islands'])}, "
            f"solved={int(row['n_solved'])}, no-result={int(row['n_no_result'])} ({format_pct(row['no_result_share'])}), "
            f"infeasible={int(row['n_infeasible'])} "
            f"({format_pct(display_share_all_targets)} of all targets in the figure; "
            f"{format_pct(display_share_all_targets)} of solved islands)"
        )


def main():
    args = parse_args()

    viability_file = resolve_existing_path(args.viability_file)
    output_dir = resolve_output_path(args.output_dir)
    figures_dir = output_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    available_scenarios, scenario_issues = load_available_scenarios(args)
    if len(available_scenarios) < 2:
        pd.DataFrame(scenario_issues).to_csv(output_dir / "missing_pairs.csv", index=False)
        raise SystemExit("At least two scenario directories with best_cost files are required.")

    viability_df = load_viability_metadata(viability_file)
    common_island_df = build_common_island_level_frame(available_scenarios, viability_df)
    status_long_df = build_full_status_long_frame(available_scenarios, viability_df)

    issue_df = pd.DataFrame(scenario_issues)
    no_result_df = status_long_df[~status_long_df["has_result"]].copy()
    no_result_df = no_result_df[
        [
            "coord_key",
            "lat",
            "lon",
            "scenario_variant",
            "scenario_label",
            "solve_status",
        ]
    ]
    no_result_df = no_result_df.rename(columns={"solve_status": "reason"})
    missing_df = pd.concat([no_result_df, issue_df], ignore_index=True, sort=False) if not issue_df.empty else no_result_df

    if status_long_df.empty:
        missing_df.to_csv(output_dir / "missing_pairs.csv", index=False)
        raise SystemExit("No target islands were found in viability metadata.")

    common_metric_long_df = build_common_metric_long(common_island_df, available_scenarios) if not common_island_df.empty else pd.DataFrame()
    common_lcoe_summary_df = build_common_lcoe_summary(common_metric_long_df, available_scenarios) if not common_metric_long_df.empty else pd.DataFrame()
    scenario_summary_df = build_scenario_summary(status_long_df, available_scenarios)
    transition_matrices = build_transition_matrices(common_island_df, available_scenarios)

    common_island_df.to_csv(output_dir / "island_level_comparison.csv", index=False)
    common_metric_long_df.to_csv(output_dir / "island_metric_long.csv", index=False)
    common_lcoe_summary_df.to_csv(output_dir / "common_lcoe_summary.csv", index=False)
    status_long_df.to_csv(output_dir / "scenario_island_status_long.csv", index=False)
    scenario_summary_df.to_csv(output_dir / "scenario_summary.csv", index=False)
    missing_df.to_csv(output_dir / "missing_pairs.csv", index=False)

    for scenario_key, transition_df in transition_matrices.items():
        transition_df.to_csv(output_dir / f"classification_transition_matrix_future_2050_to_{scenario_key}.csv")

    plot_main_figure(
        common_metric_long_df,
        scenario_summary_df,
        available_scenarios,
        figures_dir / "fig_lcoe_infeasible_combined.png",
    )
    print_figure_results(common_lcoe_summary_df, scenario_summary_df)

    scenario_names = ", ".join(scenario["key"] for scenario in available_scenarios)
    print(f"Compared scenarios: {scenario_names}")
    print(f"Target islands: {viability_df['coord_key'].nunique()}")
    print(f"Common solved islands for LCOE comparison: {len(common_island_df)}")
    print(f"Missing/invalid pairs: {len(missing_df)}")
    print(f"Outputs written to: {output_dir}")


if __name__ == "__main__":
    main()
