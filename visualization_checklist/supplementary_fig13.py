"""
Supplementary Figure 13. Regional evolution of per-capita energy system costs
across scenarios.

Panel grid of IPCC AR6 reference regions containing MORE THAN 10 islands. Each
subplot shows the mean per-capita energy-system cost of islands in that region,
evolving across six scenarios (Ideal, Baseline, Climate Stress, TP2030, TP2040,
TP2050). Stacked bars give the cost composition; the black line traces the total
per-capita cost from the Baseline scenario onwards. Each y-axis is scaled
individually to accommodate the wide between-region cost variation.

Run from the visualization_checklist/ directory:
    python supplementary_fig13.py
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# --- Global style (academic) ---
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['mathtext.fontset'] = 'custom'
plt.rcParams['mathtext.rm'] = 'Arial'
plt.rcParams['mathtext.it'] = 'Arial:italic'
plt.rcParams['mathtext.default'] = 'regular'

# --- Scenarios (ordered) and their cost-summary files ---
RESULT_DIR = os.path.join('..', 'result')
SCENARIOS = [
    ('Ideal',          'island_cost_summary_0.csv'),
    ('Baseline',       'island_cost_summary_2020.csv'),
    ('Climate Stress', 'island_cost_summary_2050.csv'),
    ('TP2030',         'island_cost_summary_future_2030.csv'),
    ('TP2040',         'island_cost_summary_future_2040.csv'),
    ('TP2050',         'island_cost_summary_future_2050.csv'),
]
SCEN_LABELS = [s[0] for s in SCENARIOS]

# --- Cost components: (column, legend label, colour) ---
COST_COMPONENTS = [
    ('renewable_cost_per_capita',       'Renewable Generation Cost',   '#4C72B0'),
    ('storage_cost_per_capita',         'Energy Storage System Cost',  '#DDAA33'),
    ('lng_cost_per_capita',             'Conventional Generation Cost', '#808080'),
    ('other_equipment_cost_per_capita', 'Sector-Coupling System Cost', '#8172B3'),
    ('discard_cost_per_capita',         'Penalty Cost of Curtailment', '#d47d49'),
    ('load_shedding_cost_per_capita',   'Cost of Unserved Energy',     '#C44E52'),
]
COST_COLS = [c[0] for c in COST_COMPONENTS]

# --- Load all scenarios and stack into one long frame ---
frames = []
for label, fname in SCENARIOS:
    df = pd.read_csv(os.path.join(RESULT_DIR, fname))
    df['Scenario'] = label
    frames.append(df)
all_df = pd.concat(frames, ignore_index=True)

# --- Regions with MORE THAN 10 islands (per Ideal scenario), alphabetical ---
ideal_counts = all_df[all_df['Scenario'] == 'Ideal']['IPCC_Region_Code'].value_counts()
regions = sorted(ideal_counts[ideal_counts > 10].index.tolist())
print(f'Regions (> 10 islands): {len(regions)} -> {regions}')

# --- Mean per-capita cost per region x scenario x component ---
# means[region][scenario] = array of 6 component means
means = (all_df[all_df['IPCC_Region_Code'].isin(regions)]
         .groupby(['IPCC_Region_Code', 'Scenario'])[COST_COLS]
         .mean())

# --- Figure layout ---
n = len(regions)
n_cols = 6
n_rows = int(np.ceil(n / n_cols))
fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 11), dpi=300)
axes = axes.flatten()

x = np.arange(len(SCEN_LABELS))

for idx, region in enumerate(regions):
    ax = axes[idx]

    # Component means for this region, in scenario order
    comp = np.array([means.loc[(region, s)].values for s in SCEN_LABELS])  # (6 scen, 6 comp)
    totals = comp.sum(axis=1)

    # Stacked bars
    bottom = np.zeros(len(SCEN_LABELS))
    for j, (_, _, color) in enumerate(COST_COMPONENTS):
        ax.bar(x, comp[:, j], bottom=bottom, width=0.7,
               color=color, edgecolor='white', linewidth=0.3, zorder=2)
        bottom += comp[:, j]

    # Total-cost trend line across all scenarios (incl. Ideal)
    ax.plot(x, totals, color='black', linewidth=1.4,
            marker='o', markersize=3.5, markerfacecolor='black',
            markeredgecolor='black', zorder=4)

    ymax = totals.max()
    ax.set_ylim(0, ymax * 1.28)

    # Dollar annotations above every bar ("$0.7k")
    for xi, tot in zip(x, totals):
        ax.text(xi, tot + ymax * 0.04, f'${tot / 1000:.1f}k',
                ha='center', va='bottom', fontsize=6.5, color='#222222',
                rotation=0, zorder=5)

    # Title = region code
    ax.set_title(region, fontsize=12, fontweight='bold', pad=4)

    # Aesthetics
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(axis='y', labelsize=8, length=3, width=0.8)
    ax.tick_params(axis='x', length=3, width=0.8)
    ax.set_xlim(-0.6, len(SCEN_LABELS) - 0.4)
    ax.margins(x=0)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=4))

    # X tick labels only on the lowest used subplot of each column
    if idx + n_cols >= n:
        ax.set_xticks(x)
        ax.set_xticklabels(SCEN_LABELS, rotation=45, ha='right', fontsize=9)
    else:
        ax.set_xticks(x)
        ax.set_xticklabels([])

# Hide unused subplot slots
for k in range(n, len(axes)):
    axes[k].set_visible(False)

# Shared y-axis label
fig.supylabel('Mean per-capita cost (USD capita$^{-1}$)', fontsize=13, x=0.005)

# --- Shared legend (bottom): trend line + 6 cost components ---
legend_handles = [
    Line2D([0], [0], color='black', linewidth=1.4, marker='o',
           markersize=4, label='Total Cost Trend')
]
legend_handles += [Patch(facecolor=color, label=label)
                   for _, label, color in COST_COMPONENTS]

fig.legend(handles=legend_handles, loc='lower center',
           bbox_to_anchor=(0.5, -0.02), ncol=3, frameon=False, fontsize=14,
           handlelength=1.6, columnspacing=2.0, handletextpad=0.6)

plt.tight_layout(rect=[0.015, 0.07, 1, 1])

out_png = 'supplementary_fig13.png'
out_pdf = 'supplementary_fig13.pdf'
fig.savefig(out_png, dpi=300, bbox_inches='tight')
fig.savefig(out_pdf, dpi=300, bbox_inches='tight')
print(f'Saved: {out_png}, {out_pdf}')
