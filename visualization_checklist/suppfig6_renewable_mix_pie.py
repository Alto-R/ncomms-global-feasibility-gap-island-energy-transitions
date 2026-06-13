"""
Supplementary Figure 6 — Regional composition of the renewable *generation* mix
on global islands.

One pie per IPCC AR6 region shows the proportional contribution of
    wind (Wind, light blue) / solar PV (Solar PV, yellow) / wave (Wave, dark cyan)
to the optimal renewable *generation* mix (not installed capacity).

The generation mix is computed from the optimisation dispatch results:
for every island in scenario output_0, the hourly WT / PV / WEC generation
columns of  result/output_0/<lat>_<lon>_results.csv  are summed over the year,
then aggregated to region totals and normalised to shares.

NOTE: this differs from the installed-capacity shares stored in
source_data.xlsx sheet 'SuppFig6'. The published caption refers to the
*generation* mix, so generation (from results.csv) is used here.
"""

from pathlib import Path
import glob
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import geopandas as gpd
from shapely.geometry import Point
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# --- Nature style ---
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial'],
    'font.size': 14,
    'figure.dpi': 300,
})

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GEO = HERE / 'IPCC-WGI-reference-regions-v4.geojson'
RESULTS_DIR = ROOT / 'result' / 'output_0'
CACHE = HERE / 'suppfig6_generation_shares.csv'

# Reference-figure colours: Wind = light blue, Solar PV = yellow, Wave = dark cyan
COLORS = ['#A6CEE3', '#F5C518', '#1F9FB5']
LABELS = ['Wind', 'Solar PV', 'Wave']

MIN_ISLANDS = 5         # only show regions with at least this many islands

ipcc = gpd.read_file(GEO)


def assign_region(lat, lon):
    p = Point(lon, lat)
    idx = list(ipcc.sindex.intersection(p.bounds))
    cand = ipcc.iloc[idx]
    hit = cand[cand.contains(p)]
    return hit.iloc[0]['Acronym'] if not hit.empty else 'Unknown'


# --- 1. Build / load per-island generation totals ---
if CACHE.exists():
    isl = pd.read_csv(CACHE)
    print(f"Loaded cached generation totals: {len(isl)} islands")
else:
    rows = []
    files = sorted(glob.glob(str(RESULTS_DIR / '*_results.csv')))
    print(f"Reading {len(files)} dispatch result files ...")
    fname_re = re.compile(r'(-?\d+\.\d+)_(-?\d+\.\d+)_results\.csv$')
    for i, f in enumerate(files):
        m = fname_re.search(f.replace('\\', '/'))
        if not m:
            continue
        lat, lon = float(m.group(1)), float(m.group(2))
        try:
            d = pd.read_csv(f, usecols=['WT', 'PV', 'WEC'])
        except Exception:
            continue
        rows.append({
            'lat': lat, 'lon': lon,
            'WT_gen': d['WT'].clip(lower=0).sum(),
            'PV_gen': d['PV'].clip(lower=0).sum(),
            'WEC_gen': d['WEC'].clip(lower=0).sum(),
        })
        if (i + 1) % 300 == 0:
            print(f"  {i + 1}/{len(files)}")
    isl = pd.DataFrame(rows)
    isl['region'] = isl.apply(lambda r: assign_region(r['lat'], r['lon']), axis=1)
    isl.to_csv(CACHE, index=False)
    print(f"Cached -> {CACHE}")

if 'region' not in isl.columns:
    isl['region'] = isl.apply(lambda r: assign_region(r['lat'], r['lon']), axis=1)

# --- 2. Aggregate to region generation mix ---
isl['total_gen'] = isl[['WT_gen', 'PV_gen', 'WEC_gen']].sum(axis=1)
agg = isl.groupby('region').agg(
    WT=('WT_gen', 'sum'), PV=('PV_gen', 'sum'), WEC=('WEC_gen', 'sum'),
    avg_total=('total_gen', 'mean'), n=('lat', 'count')).reset_index()
agg = agg[agg['n'] >= MIN_ISLANDS].copy()
agg['total'] = agg[['WT', 'PV', 'WEC']].sum(axis=1)
for c in ['WT', 'PV', 'WEC']:
    agg[c + '_share'] = agg[c] / agg['total']

# --- Fixed display coordinates (lat, lon) per IPCC region ---
REGION_COORDS = {
    'CAR': (20.0, -60.0), 'NAO': (40.0, -30.0), 'MED': (40.0, 18.0),
    'SSA': (-50.0, -70.0), 'NZ': (-40.0, 175.0), 'EAS': (30.0, 120.0),
    'SPO': (-40.0, -150.0), 'SEA': (0.0, 125.0), 'NEU': (61.0, 10.0),
    'GIC': (65.0, -40.0), 'AUS': (-25.0, 135.0), 'SAO': (-20.0, -10.0),
    'SAS': (20.0, 80.0), 'WAS': (15.0, 45.0), 'CAS': (45.0, 70.0),
    'ENA': (45.0, -75.0), 'WNA': (45.0, -120.0), 'CNA': (35.0, -100.0),
    'NEN': (65.0, 30.0), 'WSA': (-10.0, -60.0), 'NSA': (-5.0, -55.0),
    'NES': (-15.0, -45.0), 'SAM': (-30.0, -60.0), 'WAF': (10.0, 0.0),
    'CAF': (0.0, 20.0), 'EAF': (0.0, 40.0), 'SAF': (-30.0, 25.0),
    'MDG': (-20.0, 47.0), 'ESB': (70.0, 120.0), 'WSB': (65.0, 80.0),
    'RFE': (55.0, 135.0), 'RAR': (75.0, 105.0), 'WCA': (40.0, -10.0),
    'ECA': (50.0, 20.0), 'TIB': (32.0, 90.0), 'EEU': (55.0, 40.0),
    'SWS': (-40.0, -73.0), 'NWS': (70.0, 15.0), 'CEU': (50.0, 15.0),
    'WCE': (45.0, 5.0), 'ECE': (50.0, 25.0), 'MES': (30.0, 50.0),
    'MEN': (35.0, 35.0), 'ARO': (75.0, 0.0), 'BOB': (15.0, 90.0),
    'ARS': (15.0, 50.0), 'SCS': (15.0, 115.0), 'IOD': (-15.0, 75.0),
    'WIO': (-15.0, 60.0), 'EIO': (-15.0, 90.0), 'SIO': (-35.0, 75.0),
    'EPO': (-10.0, -120.0), 'NPO': (30.0, -150.0), 'ARP': (15.0, 50.0),
    'SAH': (24.0, 12.0), 'SCA': (10.0, -85.0), 'NWN': (60.0, -140.0),
    'NAU': (-15.0, 135.0),
}
# nudge a few overlapping placements apart so every region's pie is visible
REGION_COORDS['BOB'] = (5.0, 95.0)     # was (15, 90), collided with SAS
REGION_COORDS['SWS'] = (-35.0, -80.0)  # was (-40, -73), collided with SSA
REGION_COORDS['WCE'] = (45.0, 3.0)     # nudged NE (was 42,-3 / orig 45,5)
# fix mislabelled coords in the base table (acronyms follow IPCC AR6):
REGION_COORDS['NEN'] = (64.0, -82.0)   # N.E. North-America, NOT northern Europe
REGION_COORDS['WCA'] = (42.0, 57.0)    # West Central Asia, NOT the Atlantic
# coordinates for smaller regions (5-9 islands) not in the base table
REGION_COORDS['NCA'] = (20.0, -102.0)
REGION_COORDS['SAU'] = (-35.0, 138.0)
REGION_COORDS['ESAF'] = (-28.0, 32.0)
REGION_COORDS['SEAF'] = (-10.0, 40.0)

cent = {r['Acronym']: (r['geometry'].centroid.y, r['geometry'].centroid.x)
        for _, r in ipcc.iterrows()}


def coord_for(reg):
    return REGION_COORDS.get(reg, cent.get(reg, (np.nan, np.nan)))


agg['clat'] = agg['region'].map(lambda r: coord_for(r)[0])
agg['clon'] = agg['region'].map(lambda r: coord_for(r)[1])
agg = agg.dropna(subset=['clat', 'clon'])

print("\nRegion generation mix (shares):")
print(agg[['region', 'n', 'WT_share', 'PV_share', 'WEC_share']]
      .round(3).sort_values('n', ascending=False).to_string(index=False))

# --- 3. Plot pies on a Robinson map ---
fig = plt.figure(figsize=(16, 9), dpi=300)
ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())
ax.set_global()
ax.spines['geo'].set_visible(False)   # drop the outer map frame
ax.add_feature(cfeature.LAND, facecolor='#CFCFCF', zorder=0)
ax.add_feature(cfeature.OCEAN, facecolor='#FFFFFF', zorder=0)
ax.add_feature(cfeature.COASTLINE, linewidth=0.4, edgecolor='#6f6f6f', zorder=1)

# lat/lon graticule with labels (same style as the other supplementary maps)
gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True,
                  linewidth=0.3, color='gray', alpha=0.4, linestyle='--',
                  xlocs=range(-180, 181, 60), ylocs=range(-60, 91, 30))
gl.top_labels = False
gl.right_labels = False
gl.xlabel_style = {'size': 13, 'color': '#404040'}
gl.ylabel_style = {'size': 13, 'color': '#404040'}

# IPCC AR6 reference-region boundaries (the grid of polygons on the map)
for geom in ipcc.geometry:
    ax.add_geometries([geom], crs=ccrs.PlateCarree(), facecolor='none',
                      edgecolor='#4d4d4d', linewidth=0.6, zorder=2)

# pie radius scales with the regional average per-island generation
s_min, s_max = agg['avg_total'].min(), agg['avg_total'].max()


def zoom_for(v):
    t = (np.sqrt(v) - np.sqrt(s_min)) / (np.sqrt(s_max) - np.sqrt(s_min) + 1e-9)
    return 0.09 + 0.10 * t        # OffsetImage zoom range (min .09 -> max .19)


for _, row in agg.sort_values('avg_total').iterrows():
    shares = [row['WT_share'], row['PV_share'], row['WEC_share']]
    vals = [(s, c) for s, c in zip(shares, COLORS) if s > 0]
    sizes = [v[0] for v in vals]
    cols = [v[1] for v in vals]

    fig_t, ax_t = plt.subplots(figsize=(2, 2), dpi=150)
    fig_t.patch.set_alpha(0)
    ax_t.pie(sizes, colors=cols,
             wedgeprops={'edgecolor': 'white', 'linewidth': 1.2}, startangle=90)
    ax_t.set_aspect('equal')
    ax_t.axis('off')
    fig_t.tight_layout(pad=0)
    fig_t.canvas.draw()
    img = np.array(fig_t.canvas.renderer.buffer_rgba())
    plt.close(fig_t)

    x, y = ax.projection.transform_point(row['clon'], row['clat'], ccrs.Geodetic())
    ab = AnnotationBbox(OffsetImage(img, zoom=zoom_for(row['avg_total'])), (x, y),
                        frameon=False, pad=0, zorder=10)
    ax.add_artist(ab)

# legend — horizontal, centred below the map
handles = [mpatches.Patch(color=COLORS[i], label=LABELS[i]) for i in range(3)]
ax.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.5, -0.10),
          ncol=3, frameon=False, fontsize=15, columnspacing=2.2,
          handletextpad=0.6)

out = HERE / 'suppfig6_renewable_mix_pie.png'
fig.savefig(out, dpi=300, bbox_inches='tight')
print(f"\nSaved -> {out}")
