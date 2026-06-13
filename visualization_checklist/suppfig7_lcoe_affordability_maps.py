"""
Supplementary Figure 7 — Global distribution of LCOE increase, affordability,
and their ratio for islands.

Three stacked Robinson maps:
  a  LCOE Increase (USD kWh-1)             = LCOE_Climate_Stress - LCOE_Ideal
  b  Affordability                         = Affordable_Ideal / LCOE_Ideal (ratio)
  c  LCOE Increase / Affordability Ratio   = LCOE_Increase_Pct / Affordability_Ratio (%)

Data source: ../source_data.xlsx, sheet 'SuppFig7' (authoritative published values).
This sheet pre-computes LCOE_Increase, LCOE_Increase_Pct and Affordability_Ratio,
so the figure is reproduced directly from it.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, TwoSlopeNorm
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import geopandas as gpd

# --- Nature style ---
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial'],
    'font.size': 16,
    'axes.labelsize': 16,
    'axes.titlesize': 18,
    'xtick.labelsize': 14,
    'ytick.labelsize': 14,
    'legend.fontsize': 14,
    'figure.dpi': 300,
    'axes.linewidth': 0.8,
})

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'source_data.xlsx'

# --- IPCC reference regions (outlines) ---
IPCC_PATH = HERE / 'IPCC-WGI-reference-regions-v4.geojson'
ipcc_regions = gpd.read_file(IPCC_PATH) if IPCC_PATH.exists() else None
if ipcc_regions is None:
    print(f"Warning: IPCC region file not found at {IPCC_PATH}; region outlines skipped.")

# --- Load authoritative source data ---
df = pd.read_excel(SRC, sheet_name='SuppFig7')

# NOTE: the sheet column 'Affordability_Ratio' is actually LCOE / affordable
# tariff (= UN-affordability, higher = worse). True affordability is its
# inverse: affordable tariff / LCOE, where > 1 means the system is affordable.
df['Affordability'] = df['Affordable_Ideal'] / df['LCOE_Ideal']

# Panel c metric: LCOE increase (%) scaled by how affordable the island is.
# Dividing by *true* affordability => wealthy/affordable islands score low.
df['Ratio_Metric'] = df['LCOE_Increase_Pct'] / df['Affordability']

# Panel a lower bound = 5th percentile of the LCOE-increase distribution.
VMIN_A = float(np.percentile(df['LCOE_Increase'], 5))

print(f"Loaded {len(df)} islands for SuppFig7")
print(f"Panel a vmin (5th pct of LCOE_Increase) = {VMIN_A:.4f}")
print(df[['LCOE_Increase', 'Affordability', 'Ratio_Metric']].describe())

# --- Panel configuration: (column, label, cmap, norm, draw order metric) ---
panels = [
    dict(letter='a', col='LCOE_Increase',
         label='LCOE increase (USD kWh$^{-1}$)',
         cmap='RdBu_r',
         # vmin = 5th percentile of all LCOE-increase values (see VMIN_A).
         norm=Normalize(vmin=VMIN_A, vmax=0.075)),
    dict(letter='b', col='Affordable_Ideal',
         label='Maximum affordable price (USD kWh$^{-1}$)',
         cmap='RdBu',
         # blue = high affordable price (wealthier islands); USD/kWh
         norm=Normalize(vmin=0.0, vmax=4.0),
         ticks=[0, 1, 2, 3, 4]),
    dict(letter='c', col='Ratio_Metric',
         label='LCOE increase / affordability ratio',
         cmap='RdBu_r',
         norm=Normalize(vmin=0.0, vmax=12.0),
         ticks=[0, 3, 6, 9, 12]),
]


def draw_basemap(ax):
    ax.set_global()
    ax.spines['geo'].set_visible(False)   # drop the outer map frame
    ax.add_feature(cfeature.LAND, facecolor='#E8E8E8', zorder=0)
    ax.add_feature(cfeature.OCEAN, facecolor='#FFFFFF', zorder=0)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.4, edgecolor='#888888', zorder=1)
    ax.add_feature(cfeature.BORDERS, linestyle=':', linewidth=0.3,
                   edgecolor='#aaaaaa', alpha=0.6, zorder=1)
    # IPCC reference region outlines (dashed).
    if ipcc_regions is not None:
        for geom in ipcc_regions.geometry:
            ax.add_geometries([geom], crs=ccrs.PlateCarree(),
                              facecolor='none', edgecolor='#777777',
                              linewidth=0.5, linestyle='--', alpha=0.7, zorder=2)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True,
                      linewidth=0.3, color='gray', alpha=0.4, linestyle='--',
                      xlocs=range(-180, 181, 60), ylocs=range(-60, 91, 30))
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {'size': 9, 'color': '#404040'}
    gl.ylabel_style = {'size': 9, 'color': '#404040'}


fig = plt.figure(figsize=(9, 13), dpi=300)

for i, p in enumerate(panels):
    ax = fig.add_subplot(3, 1, i + 1, projection=ccrs.Robinson())
    draw_basemap(ax)

    # Plot small-value points first so extreme values sit on top.
    if p['letter'] == 'b':
        order = df[p['col']].argsort().values          # high affordability on top
    else:
        order = df[p['col']].abs().argsort().values
    d = df.iloc[order]

    sc = ax.scatter(d['Longitude'], d['Latitude'],
                    c=d[p['col']], cmap=p['cmap'], norm=p['norm'],
                    s=14, alpha=0.9, linewidths=0.2, edgecolors='white',
                    transform=ccrs.PlateCarree(), zorder=5)

    ax.text(-0.02, 1.02, p['letter'], transform=ax.transAxes,
            fontsize=20, fontweight='bold', va='bottom', ha='left')

    # Horizontal colorbar under each map (extra gap from the map).
    cax = ax.inset_axes([0.18, -0.14, 0.64, 0.035])
    cb = fig.colorbar(sc, cax=cax, orientation='horizontal', extend='both')
    if p.get('ticks') is not None:
        cb.set_ticks(p['ticks'])
    cb.set_label(p['label'], fontsize=14)
    cb.ax.tick_params(labelsize=11)

plt.subplots_adjust(hspace=0.38, top=0.98, bottom=0.04)
out = HERE / 'suppfig7_lcoe_affordability_maps.png'
fig.savefig(out, dpi=300, bbox_inches='tight')
print(f"Saved -> {out}")
