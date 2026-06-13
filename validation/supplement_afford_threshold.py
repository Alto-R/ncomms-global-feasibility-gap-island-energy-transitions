"""
Affordability Threshold Sensitivity Analysis
=============================================
Responds to Reviewer 3's request for a more systematic sensitivity analysis
of the income-based affordability threshold (6%, 8%, 10%, 12%) used to
compute tariff_affordable, including robustness of the Q1-Q6 six-region
classification.

Formula:
    tariff_affordable = income_per_capita_2020 * threshold / consumption_pc_kwh

Run from project root:
    python validation/supplement_afford_threshold.py

Outputs (all written to validation/):
    validation/Table_feasibility_threshold_sensitivity_{scenario}.csv
    validation/Table_sixregion_threshold_sensitivity_{scenario}.csv
    validation/Figure_feasibility_threshold_sensitivity.png
    validation/Figure_sixregion_threshold_sensitivity.png
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
THRESHOLDS = [0.06, 0.08, 0.10, 0.12]
THRESHOLD_LABELS = ["6%", "8%", "10%\n(baseline)", "12%"]
THRESHOLD_COLORS = ["#D6604D", "#F4A582", "#4393C3", "#2166AC"]

SCENARIOS = {
    "output_0": "Baseline",
    "output_2050": "Climate Stress 2050",
}

# From benchmark_population_sensitivity_config.py
FIXED_MEDIAN_BREAKEVEN = 0.1973

SIX_REGION_NAMES = [
    "Feasible Low Cost High Afford.",
    "Feasible High Cost High Afford.",
    "Feasible Low Cost Low Afford.",
    "Infeasible High Cost High Afford.",
    "Infeasible Low Cost Low Afford.",
    "Infeasible High Cost Low Afford.",
]

# Short labels for plots
SIX_REGION_SHORT = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]

# Colors matching the paper's existing style (feasible = blue tones, infeasible = red tones)
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
# Six-region classification (replicates benchmark_population_sensitivity_config)
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
# Core computation helpers
# ---------------------------------------------------------------------------

def recompute_ta(df: pd.DataFrame, threshold: float) -> pd.Series:
    """Re-derive tariff_affordable for a given income threshold."""
    return df["income_per_capita_2020"] * threshold / df["consumption_pc_kwh"]


def bootstrap_ci(values: np.ndarray, stat_fn, n_boot: int = 2000, ci: float = 95):
    """Return (lower, upper) bootstrap confidence interval for stat_fn(values)."""
    rng = np.random.default_rng(42)
    boot = [stat_fn(rng.choice(values, size=len(values), replace=True)) for _ in range(n_boot)]
    lo = np.percentile(boot, (100 - ci) / 2)
    hi = np.percentile(boot, 100 - (100 - ci) / 2)
    return lo, hi


def feasibility_stats(df: pd.DataFrame, threshold: float) -> dict:
    ta = recompute_ta(df, threshold)
    gap = df["tariff_breakeven"] - ta
    is_feasible = df["tariff_breakeven"] <= ta
    n = len(df)
    n_inf = int((~is_feasible).sum())
    n_feas = int(is_feasible.sum())
    is_inf_arr = (~is_feasible).astype(float).values
    ci_lo, ci_hi = bootstrap_ci(is_inf_arr, lambda x: 100.0 * x.mean())
    return {
        "threshold": threshold,
        "threshold_label": f"{int(threshold * 100)}%",
        "n_total": n,
        "n_feasible": n_feas,
        "n_infeasible": n_inf,
        "pct_feasible": round(100.0 * n_feas / n, 1),
        "pct_infeasible": round(100.0 * n_inf / n, 1),
        "pct_infeasible_ci_lo": round(ci_lo, 1),
        "pct_infeasible_ci_hi": round(ci_hi, 1),
        "median_gap": round(gap.median(), 4),
        "mean_gap": round(gap.mean(), 4),
        "gap_values": gap.values,
    }


def sixregion_counts(df: pd.DataFrame, threshold: float) -> dict:
    """Return island counts per Q1-Q6 for a given threshold."""
    ta = recompute_ta(df, threshold)
    labels = [
        classify_six_region(tb, ta_val)
        for tb, ta_val in zip(df["tariff_breakeven"].values, ta.values)
    ]
    s = pd.Series(labels)
    counts = {q: int((s == q).sum()) for q in SIX_REGION_SHORT}
    pcts = {f"{q}_pct": round(100.0 * counts[q] / len(df), 1) for q in SIX_REGION_SHORT}
    return {"threshold": threshold, "threshold_label": f"{int(threshold * 100)}%", **counts, **pcts}


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def build_feasibility_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for t in THRESHOLDS:
        s = feasibility_stats(df, t)
        rows.append({
            "Threshold": s["threshold_label"],
            "N Total": s["n_total"],
            "N Feasible": s["n_feasible"],
            "N Infeasible": s["n_infeasible"],
            "% Feasible": s["pct_feasible"],
            "% Infeasible": s["pct_infeasible"],
            "% Infeasible CI-lo (95%)": s["pct_infeasible_ci_lo"],
            "% Infeasible CI-hi (95%)": s["pct_infeasible_ci_hi"],
            "Median Viability Gap (USD kWh⁻¹)": s["median_gap"],
            "Mean Viability Gap (USD kWh⁻¹)": s["mean_gap"],
        })
    return pd.DataFrame(rows)


def build_feasibility_figure_print_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for t in THRESHOLDS:
        s = feasibility_stats(df, t)
        q10, q25, q50, q75, q90 = np.percentile(s["gap_values"], [10, 25, 50, 75, 90])
        rows.append({
            "Threshold": s["threshold_label"],
            "% Infeasible": s["pct_infeasible"],
            "% Infeasible CI-lo": s["pct_infeasible_ci_lo"],
            "% Infeasible CI-hi": s["pct_infeasible_ci_hi"],
            "Median Gap": round(q50, 4),
            "P25 Gap": round(q25, 4),
            "P75 Gap": round(q75, 4),
            "P10 Gap": round(q10, 4),
            "P90 Gap": round(q90, 4),
            "Min Gap": round(np.min(s["gap_values"]), 4),
            "Max Gap": round(np.max(s["gap_values"]), 4),
        })
    return pd.DataFrame(rows)


def build_sixregion_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for t in THRESHOLDS:
        row = sixregion_counts(df, t)
        rows.append({
            "Threshold": row["threshold_label"],
            **{q: row[q] for q in SIX_REGION_SHORT},
            **{f"{q} (%)": row[f"{q}_pct"] for q in SIX_REGION_SHORT},
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Figure 1: feasibility sensitivity
# ---------------------------------------------------------------------------

def make_feasibility_figure(scenario_data: dict) -> plt.Figure:
    """
    Two columns (one per scenario), two rows:
      Row 0: bar chart of % infeasible ± 95% CI
      Row 1: violin of feasibility gap distribution
    """
    n_sc = len(scenario_data)
    fig, axes = plt.subplots(
        2, n_sc,
        figsize=(4.5 * n_sc, 7),
        gridspec_kw={"hspace": 0.25, "wspace": 0.4},
    )
    if n_sc == 1:
        axes = axes.reshape(2, 1)

    # Bold panel labels in reading order (top row first, then bottom row).
    _PANEL = "abcdefghijklmnop"

    def _panel_label(ax, letter):
        ax.text(-0.15, 1.06, letter, transform=ax.transAxes,
                fontsize=14, fontweight="bold", va="bottom", ha="left")

    for col, (sc_key, (label, stats_list)) in enumerate(scenario_data.items()):
        ax_bar = axes[0, col]
        ax_vio = axes[1, col]
        _panel_label(ax_bar, _PANEL[col])
        _panel_label(ax_vio, _PANEL[n_sc + col])

        pct_vals = [s["pct_infeasible"] for s in stats_list]
        gap_list = [s["gap_values"] for s in stats_list]

        # CI error bars (asymmetric)
        ci_errs = np.array([
            [s["pct_infeasible"] - s["pct_infeasible_ci_lo"],
             s["pct_infeasible_ci_hi"] - s["pct_infeasible"]]
            for s in stats_list
        ]).T

        x = np.arange(len(THRESHOLDS))
        bars = ax_bar.bar(
            x, pct_vals, color=THRESHOLD_COLORS, width=0.55,
            yerr=ci_errs, capsize=3,
            error_kw={"elinewidth": 0.8, "ecolor": "black"},
        )
        # Border the 10% baseline bar
        bars[2].set_edgecolor("black")
        bars[2].set_linewidth(1.5)

        for bar, val, ci_hi in zip(bars, pct_vals, ci_errs[1]):
            ax_bar.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + ci_hi + 0.4,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=8,
            )

        ax_bar.set_xticks(x)
        ax_bar.set_xticklabels(THRESHOLD_LABELS, fontsize=9)
        ax_bar.set_ylabel("Infeasible islands (%)")
        ax_bar.set_title(label, fontsize=10, pad=4)
        ax_bar.spines[["top", "right"]].set_visible(False)
        ax_bar.set_ylim(0, max(pct_vals) * 1.25)

        # Violin
        vp = ax_vio.violinplot(
            gap_list, positions=x, widths=0.55,
            showmedians=True, showextrema=False,
        )
        for pc, color in zip(vp["bodies"], THRESHOLD_COLORS):
            pc.set_facecolor(color)
            pc.set_alpha(0.65)
            pc.set_edgecolor("black")
            pc.set_linewidth(0.5)
        vp["cmedians"].set_color("black")
        vp["cmedians"].set_linewidth(1.5)

        ax_vio.axhline(0, color="red", linestyle="--", linewidth=0.8, alpha=0.8)
        ax_vio.set_xticks(x)
        ax_vio.set_xticklabels(THRESHOLD_LABELS, fontsize=9)
        ax_vio.set_ylabel("Feasibility gap (USD kWh$^{-1}$)")
        ax_vio.set_title("", fontsize=10, pad=4)
        ax_vio.spines[["top", "right"]].set_visible(False)

    baseline_patch = mpatches.Patch(
        facecolor=THRESHOLD_COLORS[2], edgecolor="black", linewidth=1.5,
        label="10% — paper baseline",
    )
    zero_line = plt.Line2D(
        [0], [0], color="red", linestyle="--", linewidth=0.8,
        label="Break-even (gap = 0)",
    )
    fig.legend(
        handles=[baseline_patch, zero_line],
        loc="lower center", ncol=2, frameon=False, fontsize=9,
        bbox_to_anchor=(0.5, -0.03),
    )
    return fig


# ---------------------------------------------------------------------------
# Figure 2: six-region classification sensitivity
# ---------------------------------------------------------------------------

def make_sixregion_figure(scenario_data: dict) -> plt.Figure:
    """
    One row per scenario.
    Each row: grouped bar chart with 4 threshold groups, each bar split by Q1-Q6 (stacked).
    """
    n_sc = len(scenario_data)
    fig, axes = plt.subplots(
        1, n_sc,
        figsize=(6.5 * n_sc, 5.5),
        gridspec_kw={"wspace": 0.45},
    )
    if n_sc == 1:
        axes = [axes]

    q_colors = [SIX_REGION_COLORS[q] for q in SIX_REGION_SHORT]

    for ax, (sc_key, (label, tables_by_threshold)) in zip(axes, scenario_data.items()):
        # tables_by_threshold: list of dicts from sixregion_counts, one per threshold
        x = np.arange(len(THRESHOLDS))
        bar_width = 0.55
        bottoms = np.zeros(len(THRESHOLDS))

        for qi, (q, color) in enumerate(zip(SIX_REGION_SHORT, q_colors)):
            heights = np.array([row[f"{q}_pct"] for row in tables_by_threshold])
            bars = ax.bar(x, heights, bar_width, bottom=bottoms, color=color, label=q)
            # Add % label inside bar if large enough
            for xi, (h, b) in enumerate(zip(heights, bottoms)):
                if h >= 4:
                    ax.text(
                        xi, b + h / 2, f"{h:.0f}%",
                        ha="center", va="center", fontsize=7.5,
                        color="white" if qi in (0, 4, 5) else "black",
                        fontweight="bold",
                    )
            bottoms += heights

        # Outline the 10% baseline group
        ax.axvspan(x[2] - bar_width / 2, x[2] + bar_width / 2,
                   color="none", edgecolor="black", linewidth=1.5, zorder=3)

        ax.set_xticks(x)
        ax.set_xticklabels(THRESHOLD_LABELS, fontsize=10)
        ax.set_ylabel("Islands (%)")
        ax.set_ylim(0, 108)
        ax.set_title(label, fontsize=11, pad=6)
        ax.spines[["top", "right"]].set_visible(False)

        # Mark baseline
        ax.text(
            x[2], 102, "baseline", ha="center", va="bottom",
            fontsize=8, color="black",
        )

    # Shared legend for Q regions
    handles = [mpatches.Patch(facecolor=SIX_REGION_COLORS[q], label=f"{q}: {name}")
               for q, name in zip(SIX_REGION_SHORT, SIX_REGION_NAMES)]
    fig.legend(
        handles=handles,
        loc="lower center", ncol=3, frameon=False, fontsize=8.5,
        bbox_to_anchor=(0.5, -0.05),
    )
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not VIABILITY_CSV.exists():
        sys.exit(
            f"ERROR: Cannot find {VIABILITY_CSV}\n"
            "Run from project root: python validation/supplement_afford_threshold.py"
        )

    df_all = pd.read_csv(VIABILITY_CSV)
    print(f"Loaded {len(df_all)} rows, scenarios: {df_all['scenario'].unique().tolist()}")

    required = {"income_per_capita_2020", "consumption_pc_kwh", "tariff_breakeven"}
    missing = required - set(df_all.columns)
    if missing:
        sys.exit(f"ERROR: Missing columns: {missing}")

    df_all = df_all.dropna(subset=list(required))

    # Containers for figures
    feas_data = {}   # scenario_key -> (label, [feasibility_stats per threshold])
    sixr_data = {}   # scenario_key -> (label, [sixregion_counts per threshold])

    for sc_key, sc_label in SCENARIOS.items():
        df_sc = df_all[df_all["scenario"] == sc_key].copy()
        if df_sc.empty:
            print(f"WARNING: No data for '{sc_key}', skipping.")
            continue

        # ---- Feasibility table ----
        feas_table = build_feasibility_table(df_sc)
        feas_path = OUT_DIR / f"Table_feasibility_threshold_sensitivity_{sc_key}.csv"
        feas_table.to_csv(feas_path, index=False)
        print(f"\n=== Feasibility sensitivity — {sc_label} ===")
        print(feas_table.to_string(index=False))
        print(f"  → {feas_path}")
        print(f"\n=== Figure feasibility data — {sc_label} ===")
        print(build_feasibility_figure_print_table(df_sc).to_string(index=False))

        # ---- Six-region table ----
        sixr_table = build_sixregion_table(df_sc)
        sixr_path = OUT_DIR / f"Table_sixregion_threshold_sensitivity_{sc_key}.csv"
        sixr_table.to_csv(sixr_path, index=False)
        print(f"\n=== Six-region classification — {sc_label} ===")
        print(sixr_table.to_string(index=False))
        print(f"  → {sixr_path}")

        # Store for figures
        feas_data[sc_key] = (sc_label, [feasibility_stats(df_sc, t) for t in THRESHOLDS])
        sixr_data[sc_key] = (sc_label, [sixregion_counts(df_sc, t) for t in THRESHOLDS])

    if not feas_data:
        sys.exit("No valid scenarios found.")

    # ---- Figure 1: feasibility sensitivity ----
    fig1 = make_feasibility_figure(feas_data)
    p = OUT_DIR / "Figure_feasibility_threshold_sensitivity.png"
    fig1.savefig(p, bbox_inches="tight", dpi=300)
    print(f"Saved: {p}")
    plt.close(fig1)

    # ---- Figure 2: six-region classification sensitivity ----
    fig2 = make_sixregion_figure(sixr_data)
    p = OUT_DIR / "Figure_sixregion_threshold_sensitivity.png"
    fig2.savefig(p, bbox_inches="tight", dpi=300)
    print(f"Saved: {p}")
    plt.close(fig2)

    print(f"\nAll outputs written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
