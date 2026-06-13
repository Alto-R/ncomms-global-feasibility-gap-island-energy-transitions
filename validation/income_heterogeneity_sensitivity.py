"""
Income Heterogeneity Directional Sensitivity
==============================================
Responds to Reviewer 3 Comment 2: National GNI per capita may overstate
effective payment capacity on remote islands where local cash incomes fall
below national averages (tourism/remittance/urban bias).

Rather than using national Gini coefficients (which describe country-wide
inequality but do not identify the income position of specific outer-island
households), we use a stylized downward-adjustment sensitivity:

    Baseline                    100% of national-mean affordability
    Mild downward adjustment     75% of baseline
    Moderate downward adjustment  50% of baseline
    Severe downward adjustment    25% of baseline

These are NOT estimates of true island income — they illustrate the direction
and magnitude of bias if effective local payment capacity falls below the
national average.

Focus: Southeast Asia Q5/Q6 cluster (the region flagged by Reviewer 3),
with global results as supplementary context.

Formula:
    Adjusted_affordable_price = baseline_affordable * adjustment_factor
    Gap = Adjusted_affordable_price - tariff_breakeven
    Infeasible = 1 if Gap < 0 else 0

Run from project root:
    python validation/income_heterogeneity_sensitivity.py

Outputs (written to validation/output/):
    Table_income_heterogeneity_SEA.csv
    Table_income_heterogeneity_global.csv
    Figure_income_heterogeneity_SEA.png
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
VIABILITY_CSV = PROJECT_ROOT / "result" / "island_viability_summary_electric.csv"
OUT_DIR = THIS_DIR / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ADJUSTMENTS = [1.00, 0.75, 0.50, 0.25]
ADJUSTMENT_LABELS = [
    "100%\n(baseline)",
    "75%\n(mild)",
    "50%\n(moderate)",
    "25%\n(severe)",
]
ADJUSTMENT_COLORS = ["#4393C3", "#92C5DE", "#F4A582", "#D6604D"]

SCENARIOS = {
    "output_0": "Baseline",
    "output_2050": "Climate Stress 2050",
}

# Southeast Asia country codes present in the island viability data
SEA_CODES = {"IDN", "PHL", "MYS", "THA", "MMR", "KHM", "EAP"}

FIXED_MEDIAN_BREAKEVEN = 0.1973

SIX_REGION_SHORT = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]
SIX_REGION_COLORS = {
    "Q1": "#012A61",
    "Q2": "#0B75B3",
    "Q3": "#89CAEA",
    "Q4": "#F0D2D2",
    "Q5": "#DC5654",
    "Q6": "#982B2D",
}

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial"],
        "font.size": 11,
        "axes.labelsize": 11,
        "axes.titlesize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.dpi": 300,
        "axes.linewidth": 0.8,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "xtick.direction": "in",
        "ytick.direction": "in",
    }
)


# ---------------------------------------------------------------------------
# Six-region classification (replicates supplement_afford_threshold.py)
# ---------------------------------------------------------------------------
def classify_six_region(tariff_breakeven: float, tariff_affordable: float) -> str:
    median = FIXED_MEDIAN_BREAKEVEN
    is_feasible = tariff_breakeven <= tariff_affordable
    is_low_cost = tariff_breakeven <= median
    is_high_afford = tariff_affordable > median

    if is_feasible:
        if is_low_cost and is_high_afford:
            return "Q1"
        if (not is_low_cost) and is_high_afford:
            return "Q2"
        if is_low_cost and (not is_high_afford):
            return "Q3"
        return "Q6"

    if (not is_low_cost) and is_high_afford:
        return "Q4"
    if is_low_cost and (not is_high_afford):
        return "Q5"
    if (not is_low_cost) and (not is_high_afford):
        return "Q6"
    return "Q4"


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def bootstrap_ci(values: np.ndarray, stat_fn, n_boot: int = 2000, ci: float = 95):
    rng = np.random.default_rng(42)
    boot = [
        stat_fn(rng.choice(values, size=len(values), replace=True))
        for _ in range(n_boot)
    ]
    lo = np.percentile(boot, (100 - ci) / 2)
    hi = np.percentile(boot, 100 - (100 - ci) / 2)
    return lo, hi


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------
def recompute_stats(df: pd.DataFrame, factor: float) -> dict:
    """Compute feasibility statistics for a given downward adjustment factor."""
    ta_adj = df["tariff_affordable"] * factor
    gap = df["tariff_breakeven"] - ta_adj
    is_feasible = df["tariff_breakeven"] <= ta_adj
    n = len(df)
    n_inf = int((~is_feasible).sum())
    n_feas = int(is_feasible.sum())
    is_inf_arr = (~is_feasible).astype(float).values
    ci_lo, ci_hi = bootstrap_ci(is_inf_arr, lambda x: 100.0 * x.mean())
    return {
        "factor": factor,
        "factor_label": f"{int(factor * 100)}%",
        "n_total": n,
        "n_feasible": n_feas,
        "n_infeasible": n_inf,
        "pct_infeasible": round(100.0 * n_inf / n, 1),
        "pct_infeasible_ci_lo": round(ci_lo, 1),
        "pct_infeasible_ci_hi": round(ci_hi, 1),
        "median_gap": round(gap.median(), 4),
        "mean_gap": round(gap.mean(), 4),
        "gap_values": gap.values,
    }


def sixregion_adjusted(df: pd.DataFrame, factor: float) -> pd.Series:
    """Return six-region classification for each island under adjusted affordability."""
    ta_adj = df["tariff_affordable"] * factor
    return pd.Series(
        [
            classify_six_region(tb, ta)
            for tb, ta in zip(df["tariff_breakeven"].values, ta_adj.values)
        ],
        index=df.index,
    )


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------
def build_summary_table(stats_list: list) -> pd.DataFrame:
    rows = []
    for s in stats_list:
        rows.append(
            {
                "Affordability threshold": s["factor_label"],
                "N Total": s["n_total"],
                "N Feasible": s["n_feasible"],
                "N Infeasible": s["n_infeasible"],
                "% Infeasible": s["pct_infeasible"],
                "% Infeasible CI-lo (95%)": s["pct_infeasible_ci_lo"],
                "% Infeasible CI-hi (95%)": s["pct_infeasible_ci_hi"],
                "Median Viability Gap ($/kWh)": s["median_gap"],
                "Mean Viability Gap ($/kWh)": s["mean_gap"],
            }
        )
    return pd.DataFrame(rows)


def build_sixregion_shift_table(
    df: pd.DataFrame, factors: list, region_label: str
) -> pd.DataFrame:
    """Show how Q1-Q6 classification shifts under each adjustment factor."""
    rows = []
    for f in factors:
        labels = sixregion_adjusted(df, f)
        counts = {q: int((labels == q).sum()) for q in SIX_REGION_SHORT}
        pcts = {f"{q}_pct": round(100.0 * counts[q] / len(df), 1) for q in SIX_REGION_SHORT}
        rows.append(
            {
                "Region": region_label,
                "Threshold": f"{int(f * 100)}%",
                **counts,
                **pcts,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Figure: SEA infeasible share sensitivity across adjustment factors
# ---------------------------------------------------------------------------
def make_figure(sea_data: dict, global_data: dict) -> plt.Figure:
    """
    Two panels per scenario: SEA (left) and global (right), showing %
    infeasible across the four downward-adjustment factors with 95% CI bars.
    """
    scenarios_order = list(sea_data.keys())
    n_sc = len(scenarios_order)
    n_cols = n_sc * 2

    fig, axes = plt.subplots(
        1, n_cols,
        figsize=(4.8 * n_sc, 4.5),
        gridspec_kw={"wspace": 0.5},
    )
    if n_cols == 1:
        axes = [axes]

    for sci, sc_key in enumerate(scenarios_order):
        ax_sea = axes[sci * 2]
        ax_gl = axes[sci * 2 + 1]

        for ax, (label, stats_list), region_name in [
            (ax_sea, sea_data[sc_key], "SEA"),
            (ax_gl, global_data[sc_key], "Global"),
        ]:
            pct_vals = np.array([s["pct_infeasible"] for s in stats_list])
            ci_lo = np.array([s["pct_infeasible_ci_lo"] for s in stats_list])
            ci_hi = np.array([s["pct_infeasible_ci_hi"] for s in stats_list])
            ci_errs = np.array([pct_vals - ci_lo, ci_hi - pct_vals])

            x = np.arange(len(ADJUSTMENTS))
            bars = ax.bar(
                x, pct_vals, width=0.55,
                color=ADJUSTMENT_COLORS,
                edgecolor="white", linewidth=0.5,
                yerr=ci_errs, capsize=3,
                error_kw={"elinewidth": 0.8, "ecolor": "black"},
            )
            bars[0].set_edgecolor("black")
            bars[0].set_linewidth(1.5)

            for xi, val, ci_h in zip(x, pct_vals, ci_hi):
                ax.text(
                    xi, ci_h + 1.2, f"{val:.1f}%",
                    ha="center", va="bottom", fontsize=8,
                )

            ax.set_xticks(x)
            ax.set_xticklabels(ADJUSTMENT_LABELS, fontsize=9)
            ax.set_ylabel("Infeasible islands (%)")
            ax.set_title(
                f"{label}\n({region_name}, n={stats_list[0]['n_total']})",
                fontsize=10, pad=4,
            )
            ax.spines[["top", "right"]].set_visible(False)
            ymax = max(pct_vals) * 1.18
            ax.set_ylim(0, max(ymax, 100))

    fig.subplots_adjust(wspace=0.5, bottom=0.15)
    return fig


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------
def print_comparison(
    label: str, base_stats: list, sea_stats: list, scenario_name: str
):
    """Print a formatted comparison of global vs SEA infeasible shares."""
    print(f"\n{'=' * 70}")
    print(f"  {label} — {scenario_name}")
    print(f"{'=' * 70}")
    print(
        f"{'Threshold':<14} {'Global %Inf':>12} {'SEA %Inf':>12} "
        f"{'SEA CI-lo':>12} {'SEA CI-hi':>12} {'Delta':>8}"
    )
    print("-" * 62)
    for bs, ss in zip(base_stats, sea_stats):
        delta = ss["pct_infeasible"] - bs["pct_infeasible"]
        print(
            f"{bs['factor_label']:<14} {bs['pct_infeasible']:>11.1f}% "
            f"{ss['pct_infeasible']:>11.1f}% "
            f"{ss['pct_infeasible_ci_lo']:>11.1f}% "
            f"{ss['pct_infeasible_ci_hi']:>11.1f}% "
            f"{delta:>+7.1f}%"
        )

    # Additional: how many additional islands become infeasible
    base_n = base_stats[0]["n_infeasible"]
    sea_n_base = sea_stats[0]["n_infeasible"]
    print(f"\n  Baseline:      {sea_n_base} SEA islands infeasible (out of {sea_stats[0]['n_total']})")
    for ss in sea_stats[1:]:
        extra = ss["n_infeasible"] - sea_n_base
        print(
            f"  {ss['factor_label']:>6} threshold: {ss['n_infeasible']} SEA islands infeasible "
            f"(+{extra} vs baseline)"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not VIABILITY_CSV.exists():
        sys.exit(
            f"ERROR: Cannot find {VIABILITY_CSV}\n"
            "Run from project root: python validation/income_heterogeneity_sensitivity.py"
        )

    df_all = pd.read_csv(VIABILITY_CSV)
    print(f"Loaded {len(df_all)} rows, scenarios: {df_all['scenario'].unique().tolist()}")

    required = {"tariff_breakeven", "tariff_affordable", "_match_country_code"}
    missing = required - set(df_all.columns)
    if missing:
        sys.exit(f"ERROR: Missing columns: {missing}")

    df_all = df_all.dropna(subset=list(required))

    # Identify SEA islands
    sea_mask = df_all["_match_country_code"].isin(SEA_CODES)
    n_sea_islands = df_all.loc[sea_mask, "island_id"].nunique()
    sea_countries = sorted(df_all.loc[sea_mask, "_match_country_code"].unique())
    print(
        f"SEA countries: {sea_countries} "
        f"({n_sea_islands} unique islands)"
    )

    global_stats_all = {}
    sea_stats_all = {}
    q56_stats_all = {}

    for sc_key, sc_label in SCENARIOS.items():
        df_sc = df_all[df_all["scenario"] == sc_key].copy()
        if df_sc.empty:
            print(f"WARNING: No data for '{sc_key}', skipping.")
            continue

        df_sea = df_sc[df_sc["_match_country_code"].isin(SEA_CODES)].copy()
        print(f"\n{sc_label}: {len(df_sc)} global islands, {len(df_sea)} SEA islands")

        # ---- Identify baseline Q5/Q6 SEA islands ----
        sea_base_labels = sixregion_adjusted(df_sea, 1.0)
        df_sea_q56 = df_sea[sea_base_labels.isin(["Q5", "Q6"])].copy()
        print(f"  Baseline Q5/Q6 SEA: {len(df_sea_q56)} islands")

        # Compute stats for each adjustment factor (global)
        global_stats = [recompute_stats(df_sc, f) for f in ADJUSTMENTS]
        global_stats_all[sc_key] = (sc_label, global_stats)

        # Compute stats for each adjustment factor (SEA only)
        sea_stats = [recompute_stats(df_sea, f) for f in ADJUSTMENTS]
        sea_stats_all[sc_key] = (sc_label, sea_stats)

        # Compute stats for each adjustment factor (SEA Q5/Q6 only)
        if len(df_sea_q56) > 0:
            q56_stats = [recompute_stats(df_sea_q56, f) for f in ADJUSTMENTS]
            q56_stats_all[sc_key] = (sc_label, q56_stats)
        else:
            q56_stats_all[sc_key] = (sc_label, [])
            q56_stats = []

        # Print comparison
        print_comparison("Global vs SEA", global_stats, sea_stats, sc_label)

        if q56_stats:
            print(f"\n--- Baseline Q5/Q6 SEA islands (n={q56_stats[0]['n_total']}) ---")
            for s in q56_stats:
                print(
                    f"  {s['factor_label']:>6}: {s['pct_infeasible']:>5.1f}% infeasible "
                    f"[{s['pct_infeasible_ci_lo']:.1f}, {s['pct_infeasible_ci_hi']:.1f}] "
                    f"gap median={s['median_gap']}"
                )

        # ---- Save tables ----
        # SEA summary
        sea_table = build_summary_table(sea_stats)
        sea_path = OUT_DIR / f"Table_income_heterogeneity_SEA_{sc_key}.csv"
        sea_table.to_csv(sea_path, index=False)
        print(f"\n  SEA table → {sea_path}")

        # Global summary
        global_table = build_summary_table(global_stats)
        global_path = OUT_DIR / f"Table_income_heterogeneity_global_{sc_key}.csv"
        global_table.to_csv(global_path, index=False)
        print(f"  Global table → {global_path}")

        # Six-region shift table (SEA)
        sr_table = build_sixregion_shift_table(df_sea, ADJUSTMENTS, "SEA")
        sr_path = OUT_DIR / f"Table_income_heterogeneity_sixregion_SEA_{sc_key}.csv"
        sr_table.to_csv(sr_path, index=False)
        print(f"  Six-region shift table → {sr_path}")

        # Q5/Q6 SEA summary
        if q56_stats:
            q56_table = build_summary_table(q56_stats)
            q56_path = OUT_DIR / f"Table_income_heterogeneity_Q56_SEA_{sc_key}.csv"
            q56_table.to_csv(q56_path, index=False)
            print(f"  Q5/Q6 SEA table → {q56_path}")

    # ---- Figure: SEA + Global infeasible share ----
    fig = make_figure(sea_stats_all, global_stats_all)
    fig_path = OUT_DIR / "Figure_income_heterogeneity_SEA.png"
    fig.savefig(fig_path, bbox_inches="tight", dpi=300)
    print(f"\nSaved figure: {fig_path}")
    plt.close(fig)

    print(f"\nAll outputs written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
