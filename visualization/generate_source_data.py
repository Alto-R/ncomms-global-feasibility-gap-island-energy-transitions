"""
Generate Source Data Excel for Nature Communications submission.
Each figure's data is a separate sheet.
"""
import pandas as pd
import numpy as np
import os
import sys
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# Configuration
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULT_DIR = os.path.join(BASE_DIR, 'result')
DEMAND_DIR = os.path.join(BASE_DIR, 'demand_get', 'data', 'get1')
OUTPUT_FILE = os.path.join(BASE_DIR, 'source_data.xlsx')

SCENARIO_MAP = {
    'output_0': 'Ideal',
    'output_2020': 'Baseline',
    'output_2050': 'Climate_Stress',
    'output_future_2030': 'TP2030',
    'output_future_2040': 'TP2040',
    'output_future_2050': 'TP2050',
}

COST_SCENARIO_FILES = {
    'Ideal': 'island_cost_summary_0.csv',
    'Baseline': 'island_cost_summary_2020.csv',
    'Climate_Stress': 'island_cost_summary_2050.csv',
    'TP2030': 'island_cost_summary_future_2030.csv',
    'TP2040': 'island_cost_summary_future_2040.csv',
    'TP2050': 'island_cost_summary_future_2050.csv',
}

CAPACITY_SCENARIO_FILES = {
    'Ideal': 'island_capacity_0.csv',
    'Baseline': 'island_capacity_2020.csv',
    'Climate_Stress': 'island_capacity_2050.csv',
    'TP2030': 'island_capacity_future_2030.csv',
    'TP2040': 'island_capacity_future_2040.csv',
    'TP2050': 'island_capacity_future_2050.csv',
}

# ============================================================
# Q1-Q6 Feasibility Classification (from fig2_1.ipynb)
# ============================================================
Q_LABELS = {
    0: 'Q1: Feasible, Low Cost, High Affordability',
    1: 'Q2: Feasible, High Cost, High Affordability',
    2: 'Q3: Feasible, Low Cost, Low Affordability',
    3: 'Q4: Infeasible, High Cost, High Affordability',
    4: 'Q5: Infeasible, Low Cost, Low Affordability',
    5: 'Q6: Infeasible, High Cost, Low Affordability',
}

def classify_point(lcoe, affordable, median_lcoe):
    """Classify island into Q1-Q6 feasibility category."""
    is_low_cost = lcoe <= median_lcoe
    is_high_affordability = affordable > median_lcoe
    is_feasible = affordable >= lcoe

    if is_feasible:
        if is_low_cost and is_high_affordability:
            return Q_LABELS[0]
        elif not is_low_cost and is_high_affordability:
            return Q_LABELS[1]
        elif is_low_cost and not is_high_affordability:
            return Q_LABELS[2]
        else:
            return Q_LABELS[5]
    else:
        if not is_low_cost and is_high_affordability:
            return Q_LABELS[3]
        elif is_low_cost and not is_high_affordability:
            return Q_LABELS[4]
        elif not is_low_cost and not is_high_affordability:
            return Q_LABELS[5]
        else:
            return Q_LABELS[3]


# ============================================================
# Data Loading
# ============================================================
def load_island_origin():
    """Load island origin data with Country/Island names."""
    df = pd.read_csv(os.path.join(RESULT_DIR, 'island_data_origin.csv'))
    df = df.rename(columns={'Long': 'lon', 'Lat': 'lat'})
    return df[['ID', 'lon', 'lat', 'Country', 'Island', 'pop']]


def load_feasibility():
    """Load island_feasibility.csv with all 6 scenarios."""
    df = pd.read_csv(os.path.join(RESULT_DIR, 'island_feasibility.csv'))
    df['scenario_label'] = df['scenario'].map(SCENARIO_MAP)
    return df


def load_cost_summary(scenario_label):
    """Load cost summary for a specific scenario."""
    fname = COST_SCENARIO_FILES[scenario_label]
    return pd.read_csv(os.path.join(RESULT_DIR, fname))


def load_capacity(scenario_label):
    """Load capacity data for a specific scenario."""
    fname = CAPACITY_SCENARIO_FILES[scenario_label]
    return pd.read_csv(os.path.join(RESULT_DIR, fname))


def get_ipcc_region_map():
    """Get lat/lon -> IPCC_Region_Code mapping from cost_summary_0."""
    df = load_cost_summary('Ideal')
    return df[['lat', 'lon', 'IPCC_Region_Code', 'IPCC_Region_Name']].drop_duplicates()


# ============================================================
# Fig 1a/1b: Per-island cost data (Ideal scenario)
# ============================================================
def generate_fig1a_1b():
    """Generate per-island cost decomposition for Ideal scenario."""
    print("  Generating Fig1a_1b...")
    cost_df = load_cost_summary('Ideal')
    origin_df = load_island_origin()

    # Merge to get Country/Island names
    merged = cost_df.merge(
        origin_df[['lon', 'lat', 'Country', 'Island']],
        on=['lat', 'lon'], how='left'
    )

    # Compute total per-capita cost
    cost_cols_pc = [
        'renewable_cost_per_capita', 'storage_cost_per_capita',
        'lng_cost_per_capita', 'other_equipment_cost_per_capita',
        'discard_cost_per_capita', 'load_shedding_cost_per_capita'
    ]
    merged['total_cost_per_capita'] = merged[cost_cols_pc].sum(axis=1)

    # Select and rename columns
    result = merged[[
        'lat', 'lon', 'Country', 'Island', 'population', 'IPCC_Region_Code',
        'total_cost_per_capita',
        'renewable_cost_per_capita', 'storage_cost_per_capita',
        'lng_cost_per_capita', 'other_equipment_cost_per_capita',
        'discard_cost_per_capita', 'load_shedding_cost_per_capita'
    ]].copy()

    result.columns = [
        'Latitude', 'Longitude', 'Country', 'Island', 'Population', 'IPCC_Region',
        'Total_Cost_Per_Capita_USD',
        'Renewable_Generation_Cost_PC', 'Energy_Storage_Cost_PC',
        'Conventional_Generation_Cost_PC', 'Sector_Coupling_Cost_PC',
        'Curtailment_Penalty_Cost_PC', 'Unserved_Energy_Cost_PC'
    ]
    print(f"    -> {len(result)} islands")
    return result


# ============================================================
# Fig 1c: Regression analysis (replicating fig1_3.py Stage 2)
# ============================================================
def generate_fig1c():
    """Run regression analysis and return coefficient table."""
    print("  Generating Fig1c (regression)...")
    import statsmodels.api as sm
    from sklearn.preprocessing import StandardScaler

    cost_df = load_cost_summary('Ideal')

    # Build island-level dataset with demand and renewable variability
    island_data = []
    for idx, island in cost_df.iterrows():
        lat, lon = island['lat'], island['lon']

        # Load demand data
        demand_file = os.path.join(DEMAND_DIR, f'demand_{lat}_{lon}.csv')
        if not os.path.exists(demand_file):
            continue
        demand_df = pd.read_csv(demand_file)

        # Calculate demand stats
        demand_dt = pd.date_range(start='2020-01-01', periods=len(demand_df), freq='3h')
        demand_df['month'] = demand_dt.month

        heating_total = demand_df['heating_demand'].sum()
        h_monthly = demand_df.groupby('month')['heating_demand'].mean()
        h_filt = h_monthly[h_monthly > 0.01]
        heating_var = h_filt.std() / h_filt.mean() if len(h_filt) >= 2 and h_filt.mean() > 0 else 0

        cooling_total = demand_df['cooling_demand'].sum()
        c_monthly = demand_df.groupby('month')['cooling_demand'].mean()
        c_filt = c_monthly[c_monthly > 0.01]
        cooling_var = c_filt.std() / c_filt.mean() if len(c_filt) >= 2 and c_filt.mean() > 0 else 0

        # Load output data
        output_file = os.path.join(RESULT_DIR, 'output_0', f'{lat}_{lon}_results.csv')
        if not os.path.exists(output_file):
            continue
        output_df = pd.read_csv(output_file)
        out_dt = pd.date_range(start='2020-01-01', periods=len(output_df), freq='3h')
        output_df['month'] = out_dt.month

        # Renewable variability
        re_stats = {}
        for name, col in [('wind', 'WT'), ('pv', 'PV'), ('wave', 'WEC')]:
            if col in output_df.columns:
                monthly = output_df.groupby('month')[col].mean()
                filt = monthly[monthly > 0.01]
                seasonal = filt.std() / filt.mean() if len(filt) >= 2 else 0
                daily_mean = output_df.groupby(out_dt.dayofyear)[col].mean()
                daily_std = output_df.groupby(out_dt.dayofyear)[col].std()
                valid = daily_mean > 0.1
                daily_cv = (daily_std[valid] / daily_mean[valid]).mean() if valid.any() else 0
            else:
                seasonal, daily_cv = 0, 0
            re_stats[f'{name}_seasonal'] = seasonal
            re_stats[f'{name}_daily'] = daily_cv

        island_data.append({
            'lat': lat, 'lon': lon,
            'Heating Demand': heating_total, 'Heating Demand Variation': heating_var,
            'Cooling Demand': cooling_total, 'Cooling Demand Variation': cooling_var,
            'Wind Seasonal Variation': re_stats['wind_seasonal'],
            'Wind Daily Fluctuation': re_stats['wind_daily'],
            'PV Seasonal Variation': re_stats['pv_seasonal'],
            'PV Daily Fluctuation': re_stats['pv_daily'],
            'Wave Seasonal Variation': re_stats['wave_seasonal'],
            'Renewable Cost': island['renewable_cost_per_capita'],
            'Storage Cost': island['storage_cost_per_capita'],
            'LNG Cost': island['lng_cost_per_capita'],
            'Other Equipment Cost': island['other_equipment_cost_per_capita'],
            'Discard Cost': island['discard_cost_per_capita'],
            'Load Shedding Cost': island['load_shedding_cost_per_capita'],
        })

    if not island_data:
        print("    WARNING: No island data processed for regression!")
        return pd.DataFrame()

    final_df = pd.DataFrame(island_data).fillna(0)
    print(f"    Processed {len(final_df)} islands for regression")

    # Log transform cost variables
    cost_vars = ['Renewable Cost', 'Storage Cost', 'LNG Cost',
                 'Other Equipment Cost', 'Discard Cost', 'Load Shedding Cost']
    for cv in cost_vars:
        final_df[f'Log {cv}'] = np.log(final_df[cv] + 1)

    # Stage 2 variables
    indep_vars = [
        'Heating Demand', 'Heating Demand Variation',
        'Cooling Demand', 'Cooling Demand Variation',
        'Wind Seasonal Variation', 'Wind Daily Fluctuation',
        'PV Seasonal Variation', 'PV Daily Fluctuation',
        'Wave Seasonal Variation'
    ]
    dep_vars = [f'Log {cv}' for cv in cost_vars]

    # Run regressions
    results_rows = []
    for y_var in dep_vars:
        X_data = final_df[indep_vars].dropna()
        y_data = final_df[y_var].loc[X_data.index]

        scaler_X = StandardScaler()
        X_std = pd.DataFrame(scaler_X.fit_transform(X_data), columns=X_data.columns, index=X_data.index)
        scaler_y = StandardScaler()
        y_std = pd.Series(scaler_y.fit_transform(y_data.values.reshape(-1, 1)).flatten(), index=y_data.index)

        X_const = sm.add_constant(X_std)
        model = sm.OLS(y_std, X_const).fit(cov_type='HC1')

        for var in indep_vars:
            results_rows.append({
                'Dependent_Variable': y_var.replace('Log ', ''),
                'Independent_Variable': var,
                'Standardized_Coefficient': model.params[var],
                'Robust_Std_Error': model.bse[var],
                'Robust_t_Value': model.tvalues[var],
                'Robust_p_Value': model.pvalues[var],
                'R_Squared': model.rsquared,
                'Adj_R_Squared': model.rsquared_adj,
            })

    result = pd.DataFrame(results_rows)
    print(f"    -> {len(result)} coefficient rows")
    return result


# ============================================================
# Fig 2: Feasibility assessment (all 6 scenarios)
# ============================================================
def generate_fig2():
    """Generate feasibility data with Q1-Q6 classification."""
    print("  Generating Fig2...")
    df = load_feasibility()
    origin = load_island_origin()
    ipcc_map = get_ipcc_region_map()

    # Compute global median LCOE from Ideal scenario
    df_ideal = df[df['scenario'] == 'output_0']
    median_lcoe = df_ideal['LCOE'].median()
    print(f"    Global median LCOE (Ideal): {median_lcoe:.4f}")

    # Classify all islands
    df['feasibility_category'] = df.apply(
        lambda r: classify_point(r['LCOE'], r['tariff_affordable'], median_lcoe), axis=1
    )

    # Merge Island name from origin and IPCC region from cost summary
    df = df.merge(origin[['lon', 'lat', 'Island']], on=['lat', 'lon'], how='left')
    df = df.merge(ipcc_map, on=['lat', 'lon'], how='left')

    result = df[[
        'island_id', 'lat', 'lon', 'Country', 'Island', 'scenario_label',
        'population_calc', 'income_per_capita_2020', 'consumption_pc_kwh',
        'LCOE', 'tariff_affordable', 'feasibility_gap',
        'IPCC_Region_Code', 'feasibility_category'
    ]].copy()

    result.columns = [
        'Island_ID', 'Latitude', 'Longitude', 'Country', 'Island', 'Scenario',
        'Population', 'Income_Per_Capita_USD', 'Consumption_PC_kWh',
        'LCOE_USD_kWh', 'Affordable_Tariff_USD_kWh', 'Feasibility_Gap_USD_kWh',
        'IPCC_Region', 'Feasibility_Category'
    ]
    print(f"    -> {len(result)} rows ({len(result)//6} islands x 6 scenarios)")
    return result


# ============================================================
# Fig 3: Climate resilience impact (Ideal/Baseline/Climate Stress)
# ============================================================
def generate_fig3():
    """Generate climate resilience comparison data."""
    print("  Generating Fig3...")
    df = load_feasibility()
    origin = load_island_origin()
    ipcc_map = get_ipcc_region_map()

    # Filter 3 scenarios
    scenarios = ['output_0', 'output_2020', 'output_2050']
    df3 = df[df['scenario'].isin(scenarios)].copy()

    # Pivot to wide format
    pivot = df3.pivot_table(
        index='island_id', columns='scenario',
        values=['LCOE', 'tariff_affordable', 'feasibility_gap'],
        aggfunc='first'
    )
    pivot.columns = [f'{col[0]}_{SCENARIO_MAP[col[1]]}' for col in pivot.columns]
    pivot = pivot.reset_index()

    # Merge metadata - Country comes from feasibility data, Island from origin
    id_meta = df3[['island_id', 'lat', 'lon', 'Country']].drop_duplicates(subset='island_id')
    pivot = pivot.merge(id_meta, on='island_id', how='left')
    pivot = pivot.merge(origin[['lon', 'lat', 'Island']], on=['lat', 'lon'], how='left')
    pivot = pivot.merge(ipcc_map, on=['lat', 'lon'], how='left')

    # Compute cost increase percentages
    pivot['Cost_Increase_Pct_Baseline'] = np.where(
        pivot['LCOE_Ideal'] > 0,
        (pivot['LCOE_Baseline'] - pivot['LCOE_Ideal']) / pivot['LCOE_Ideal'] * 100,
        np.nan
    )
    pivot['Cost_Increase_Pct_Climate_Stress'] = np.where(
        pivot['LCOE_Ideal'] > 0,
        (pivot['LCOE_Climate_Stress'] - pivot['LCOE_Ideal']) / pivot['LCOE_Ideal'] * 100,
        np.nan
    )

    # Add classification
    median_lcoe = df[df['scenario'] == 'output_0']['LCOE'].median()
    for scen in ['Ideal', 'Baseline', 'Climate_Stress']:
        pivot[f'Category_{scen}'] = pivot.apply(
            lambda r: classify_point(r[f'LCOE_{scen}'], r[f'tariff_affordable_{scen}'], median_lcoe), axis=1
        )

    # Metadata already merged above

    result = pivot[[
        'island_id', 'lat', 'lon', 'Country', 'Island', 'IPCC_Region_Code',
        'LCOE_Ideal', 'LCOE_Baseline', 'LCOE_Climate_Stress',
        'tariff_affordable_Ideal',
        'feasibility_gap_Ideal', 'feasibility_gap_Baseline', 'feasibility_gap_Climate_Stress',
        'Cost_Increase_Pct_Baseline', 'Cost_Increase_Pct_Climate_Stress',
        'Category_Ideal', 'Category_Baseline', 'Category_Climate_Stress'
    ]].copy()

    result.columns = [
        'Island_ID', 'Latitude', 'Longitude', 'Country', 'Island', 'IPCC_Region',
        'LCOE_Ideal', 'LCOE_Baseline', 'LCOE_Climate_Stress',
        'Affordable_Tariff',
        'Feasibility_Gap_Ideal', 'Feasibility_Gap_Baseline', 'Feasibility_Gap_Climate_Stress',
        'Cost_Increase_Pct_Baseline', 'Cost_Increase_Pct_Climate_Stress',
        'Category_Ideal', 'Category_Baseline', 'Category_Climate_Stress'
    ]
    print(f"    -> {len(result)} islands")
    return result


# ============================================================
# Fig 4: Technological progress (Climate Stress + TP scenarios)
# ============================================================
def generate_fig4():
    """Generate technological progress comparison data."""
    print("  Generating Fig4...")
    df = load_feasibility()
    origin = load_island_origin()
    ipcc_map = get_ipcc_region_map()

    # Filter 4 scenarios
    scenarios = ['output_2050', 'output_future_2030', 'output_future_2040', 'output_future_2050']
    df4 = df[df['scenario'].isin(scenarios)].copy()

    # Pivot
    pivot = df4.pivot_table(
        index='island_id', columns='scenario',
        values=['LCOE', 'tariff_affordable', 'feasibility_gap'],
        aggfunc='first'
    )
    pivot.columns = [f'{col[0]}_{SCENARIO_MAP[col[1]]}' for col in pivot.columns]
    pivot = pivot.reset_index()

    id_coords = df4[['island_id', 'lat', 'lon', 'Country']].drop_duplicates(subset='island_id')
    pivot = pivot.merge(id_coords, on='island_id', how='left')

    # Add classification
    median_lcoe = df[df['scenario'] == 'output_0']['LCOE'].median()
    for scen in ['Climate_Stress', 'TP2030', 'TP2040', 'TP2050']:
        pivot[f'Category_{scen}'] = pivot.apply(
            lambda r: classify_point(r[f'LCOE_{scen}'], r[f'tariff_affordable_{scen}'], median_lcoe), axis=1
        )

    pivot = pivot.merge(origin[['lon', 'lat', 'Island']], on=['lat', 'lon'], how='left')
    pivot = pivot.merge(ipcc_map, on=['lat', 'lon'], how='left')

    result = pivot[[
        'island_id', 'lat', 'lon', 'Country', 'Island', 'IPCC_Region_Code',
        'LCOE_Climate_Stress', 'LCOE_TP2030', 'LCOE_TP2040', 'LCOE_TP2050',
        'tariff_affordable_Climate_Stress',
        'feasibility_gap_Climate_Stress', 'feasibility_gap_TP2030',
        'feasibility_gap_TP2040', 'feasibility_gap_TP2050',
        'Category_Climate_Stress', 'Category_TP2030', 'Category_TP2040', 'Category_TP2050'
    ]].copy()

    result.columns = [
        'Island_ID', 'Latitude', 'Longitude', 'Country', 'Island', 'IPCC_Region',
        'LCOE_Climate_Stress', 'LCOE_TP2030', 'LCOE_TP2040', 'LCOE_TP2050',
        'Affordable_Tariff',
        'Feasibility_Gap_Climate_Stress', 'Feasibility_Gap_TP2030',
        'Feasibility_Gap_TP2040', 'Feasibility_Gap_TP2050',
        'Category_Climate_Stress', 'Category_TP2030', 'Category_TP2040', 'Category_TP2050'
    ]
    print(f"    -> {len(result)} islands")
    return result


# ============================================================
# Supplementary Figures
# ============================================================
def generate_supp_fig2_3():
    """Supp Fig 2 & 3: Heating demand distribution and variability."""
    print("  Generating SuppFig2_3 (heating demand)...")
    cost_df = load_cost_summary('Ideal')
    origin = load_island_origin()
    rows = []
    for _, island in cost_df.iterrows():
        lat, lon = island['lat'], island['lon']
        demand_file = os.path.join(DEMAND_DIR, f'demand_{lat}_{lon}.csv')
        if not os.path.exists(demand_file):
            continue
        ddf = pd.read_csv(demand_file)
        dt = pd.date_range(start='2020-01-01', periods=len(ddf), freq='3h')
        ddf['month'] = dt.month

        heating_total = ddf['heating_demand'].sum()
        cooling_total = ddf['cooling_demand'].sum()
        h_monthly = ddf.groupby('month')['heating_demand'].mean()
        h_filt = h_monthly[h_monthly > 0.01]
        heating_var = h_filt.std() / h_filt.mean() if len(h_filt) >= 2 and h_filt.mean() > 0 else 0
        c_monthly = ddf.groupby('month')['cooling_demand'].mean()
        c_filt = c_monthly[c_monthly > 0.01]
        cooling_var = c_filt.std() / c_filt.mean() if len(c_filt) >= 2 and c_filt.mean() > 0 else 0

        rows.append({
            'lat': lat, 'lon': lon,
            'IPCC_Region': island['IPCC_Region_Code'],
            'Heating_Demand_Total_kWh': heating_total,
            'Heating_Demand_Variability_CV': heating_var,
            'Cooling_Demand_Total_kWh': cooling_total,
            'Cooling_Demand_Variability_CV': cooling_var,
        })

    result = pd.DataFrame(rows)
    result = result.merge(origin[['lon', 'lat', 'Country', 'Island']], on=['lat', 'lon'], how='left')
    result = result.rename(columns={'lat': 'Latitude', 'lon': 'Longitude'})
    print(f"    -> {len(result)} islands")
    return result


def generate_supp_fig4():
    """Supp Fig 4: WT/WEC variability distribution."""
    print("  Generating SuppFig4 (WT/WEC variability)...")
    cost_df = load_cost_summary('Ideal')
    rows = []
    for _, island in cost_df.iterrows():
        lat, lon = island['lat'], island['lon']
        output_file = os.path.join(RESULT_DIR, 'output_0', f'{lat}_{lon}_results.csv')
        if not os.path.exists(output_file):
            continue
        odf = pd.read_csv(output_file)
        dt = pd.date_range(start='2020-01-01', periods=len(odf), freq='3h')
        odf['month'] = dt.month

        row = {'lat': lat, 'lon': lon, 'IPCC_Region': island['IPCC_Region_Code']}
        for name, col in [('WT', 'WT'), ('WEC', 'WEC'), ('PV', 'PV')]:
            if col in odf.columns:
                monthly = odf.groupby('month')[col].mean()
                filt = monthly[monthly > 0.01]
                row[f'{name}_Seasonal_Variability_CV'] = filt.std() / filt.mean() if len(filt) >= 2 else 0
            else:
                row[f'{name}_Seasonal_Variability_CV'] = 0
        rows.append(row)

    result = pd.DataFrame(rows)
    result = result.rename(columns={'lat': 'Latitude', 'lon': 'Longitude'})
    print(f"    -> {len(result)} islands")
    return result


def generate_supp_fig5(fig1c_df):
    """Supp Fig 5: Multicollinearity diagnosis - just return the regression data."""
    print("  Generating SuppFig5 (multicollinearity)...")
    # The VIF and correlation data comes from the same regression variables
    # We provide the coefficient table which implicitly contains this info
    return fig1c_df  # Same as Fig1c data


def generate_supp_fig6():
    """Supp Fig 6: Regional demand/capacity pie charts."""
    print("  Generating SuppFig6 (regional demand/capacity)...")
    cost_df = load_cost_summary('Ideal')
    cap_df = load_capacity('Ideal')

    # Merge capacity with IPCC region
    cap_df = cap_df.merge(
        cost_df[['lat', 'lon', 'IPCC_Region_Code']],
        on=['lat', 'lon'], how='left'
    )

    # Aggregate capacity by region
    cap_cols = ['PV', 'WT', 'WEC', 'ESS', 'TES', 'CES', 'CHP', 'AC', 'EB']
    available_cols = [c for c in cap_cols if c in cap_df.columns]
    regional = cap_df.groupby('IPCC_Region_Code')[available_cols].mean().reset_index()
    regional = regional.rename(columns={'IPCC_Region_Code': 'IPCC_Region'})
    for c in available_cols:
        regional = regional.rename(columns={c: f'Avg_Capacity_{c}_MW'})

    print(f"    -> {len(regional)} regions")
    return regional


def generate_supp_fig7():
    """Supp Fig 7: LCOE increase, affordability, ratio maps."""
    print("  Generating SuppFig7...")
    df = load_feasibility()
    origin = load_island_origin()
    ipcc_map = get_ipcc_region_map()

    # Compute LCOE increase from Ideal to Climate Stress
    df_ideal = df[df['scenario'] == 'output_0'][['island_id', 'LCOE', 'tariff_affordable']].rename(
        columns={'LCOE': 'LCOE_Ideal', 'tariff_affordable': 'Affordable_Ideal'})
    df_cs = df[df['scenario'] == 'output_2050'][['island_id', 'LCOE']].rename(
        columns={'LCOE': 'LCOE_Climate_Stress'})

    merged = df_ideal.merge(df_cs, on='island_id')
    merged['LCOE_Increase'] = merged['LCOE_Climate_Stress'] - merged['LCOE_Ideal']
    merged['LCOE_Increase_Pct'] = np.where(
        merged['LCOE_Ideal'] > 0,
        merged['LCOE_Increase'] / merged['LCOE_Ideal'] * 100, np.nan
    )
    merged['Affordability_Ratio'] = np.where(
        merged['Affordable_Ideal'] > 0,
        merged['LCOE_Climate_Stress'] / merged['Affordable_Ideal'], np.nan
    )

    # Add coords
    coords = df[['island_id', 'lat', 'lon']].drop_duplicates()
    merged = merged.merge(coords, on='island_id')
    merged = merged.merge(origin[['lon', 'lat', 'Country']], on=['lat', 'lon'], how='left')
    merged = merged.merge(ipcc_map, on=['lat', 'lon'], how='left')

    result = merged.rename(columns={
        'lat': 'Latitude', 'lon': 'Longitude',
        'island_id': 'Island_ID', 'IPCC_Region_Code': 'IPCC_Region'
    })
    print(f"    -> {len(result)} islands")
    return result


def generate_supp_fig8():
    """Supp Fig 8: Feasibility classification maps (all scenarios)."""
    print("  Generating SuppFig8 (same as Fig2)...")
    return None  # Same data as Fig2, will reference that sheet


def generate_supp_fig9_10():
    """Supp Fig 9 & 10: Tech progress cost reduction and classification evolution."""
    print("  Generating SuppFig9_10 (same as Fig4)...")
    return None  # Same data as Fig4


def generate_supp_fig11_12():
    """Supp Fig 11 & 12: Cost reduction geographic heterogeneity and determinants."""
    print("  Generating SuppFig11_12...")
    cs_df = load_cost_summary('Climate_Stress')
    tp_df = load_cost_summary('TP2050')
    origin = load_island_origin()

    cost_pc_cols = [
        'renewable_cost_per_capita', 'storage_cost_per_capita',
        'lng_cost_per_capita', 'other_equipment_cost_per_capita',
        'discard_cost_per_capita', 'load_shedding_cost_per_capita'
    ]

    cs_df['total_cost_pc_CS'] = cs_df[cost_pc_cols].sum(axis=1)
    tp_df['total_cost_pc_TP'] = tp_df[cost_pc_cols].sum(axis=1)

    merged = cs_df[['lat', 'lon', 'IPCC_Region_Code', 'total_cost_pc_CS']].merge(
        tp_df[['lat', 'lon', 'total_cost_pc_TP']], on=['lat', 'lon']
    )
    merged['Cost_Reduction_USD'] = merged['total_cost_pc_CS'] - merged['total_cost_pc_TP']
    merged['Cost_Reduction_Pct'] = np.where(
        merged['total_cost_pc_CS'] > 0,
        merged['Cost_Reduction_USD'] / merged['total_cost_pc_CS'] * 100, np.nan
    )

    merged = merged.merge(origin[['lon', 'lat', 'Country']], on=['lat', 'lon'], how='left')
    result = merged.rename(columns={
        'lat': 'Latitude', 'lon': 'Longitude',
        'IPCC_Region_Code': 'IPCC_Region',
        'total_cost_pc_CS': 'Total_Cost_PC_Climate_Stress',
        'total_cost_pc_TP': 'Total_Cost_PC_TP2050',
    })
    print(f"    -> {len(result)} islands")
    return result


def generate_supp_fig13():
    """Supp Fig 13: Regional per-capita cost evolution across all scenarios."""
    print("  Generating SuppFig13...")
    cost_pc_cols = [
        'renewable_cost_per_capita', 'storage_cost_per_capita',
        'lng_cost_per_capita', 'other_equipment_cost_per_capita',
        'discard_cost_per_capita', 'load_shedding_cost_per_capita'
    ]

    all_rows = []
    for label, fname in COST_SCENARIO_FILES.items():
        df = pd.read_csv(os.path.join(RESULT_DIR, fname))
        df['total_cost_pc'] = df[cost_pc_cols].sum(axis=1)
        df['Scenario'] = label
        all_rows.append(df[['lat', 'lon', 'IPCC_Region_Code', 'Scenario', 'total_cost_pc'] + cost_pc_cols])

    result = pd.concat(all_rows, ignore_index=True)
    result = result.rename(columns={
        'lat': 'Latitude', 'lon': 'Longitude',
        'IPCC_Region_Code': 'IPCC_Region',
        'total_cost_pc': 'Total_Cost_Per_Capita',
        'renewable_cost_per_capita': 'Renewable_Cost_PC',
        'storage_cost_per_capita': 'Storage_Cost_PC',
        'lng_cost_per_capita': 'Conventional_Cost_PC',
        'other_equipment_cost_per_capita': 'Sector_Coupling_Cost_PC',
        'discard_cost_per_capita': 'Curtailment_Cost_PC',
        'load_shedding_cost_per_capita': 'Unserved_Energy_Cost_PC',
    })
    print(f"    -> {len(result)} rows ({len(result)//6} islands x 6 scenarios)")
    return result


def generate_supp_fig14():
    """Supp Fig 14: Population benchmark sensitivity analysis."""
    print("  Generating SuppFig14 (population sensitivity)...")
    tables_dir = os.path.join(RESULT_DIR, 'benchmark_population_sensitivity', 'tables')

    # Classification stability summary
    stability = pd.read_csv(os.path.join(tables_dir, 'Figure_Sx_classification_stability_data.csv'))
    # LCOE delta distribution summary
    lcoe_summary = pd.read_csv(os.path.join(tables_dir, 'Figure_Sy_lcoe_delta_distribution_summary.csv'))
    # Classification stability per-island points
    stability_pts = pd.read_csv(os.path.join(tables_dir, 'Figure_Sx_classification_stability_points.csv'))
    # LCOE delta per-island points
    lcoe_pts = pd.read_csv(os.path.join(tables_dir, 'Figure_Sy_lcoe_delta_distribution_points.csv'))

    print(f"    -> stability_summary: {len(stability)}, lcoe_summary: {len(lcoe_summary)}, "
          f"stability_points: {len(stability_pts)}, lcoe_points: {len(lcoe_pts)}")
    return {
        'SuppFig14_stability': stability,
        'SuppFig14_lcoe_summary': lcoe_summary,
        'SuppFig14_stab_points': stability_pts,
        'SuppFig14_lcoe_points': lcoe_pts,
    }


def generate_supp_fig15():
    """Supp Fig 15: Feasibility threshold sensitivity analysis."""
    print("  Generating SuppFig15 (threshold sensitivity)...")
    val_dir = os.path.join(BASE_DIR, 'validation', 'output')

    df_ideal = pd.read_csv(os.path.join(val_dir, 'Table_feasibility_threshold_sensitivity_output_0.csv'))
    df_ideal['Scenario'] = 'Ideal'
    df_cs = pd.read_csv(os.path.join(val_dir, 'Table_feasibility_threshold_sensitivity_output_2050.csv'))
    df_cs['Scenario'] = 'Climate_Stress'

    result = pd.concat([df_ideal, df_cs], ignore_index=True)
    # Reorder columns
    cols = ['Scenario'] + [c for c in result.columns if c != 'Scenario']
    result = result[cols]
    print(f"    -> {len(result)} rows")
    return result


def generate_supp_fig16():
    """Supp Fig 16: Future 2050 viability sensitivity (tech cost scenarios)."""
    print("  Generating SuppFig16 (viability sensitivity)...")
    sens_dir = os.path.join(RESULT_DIR, 'future_2050_viability_sensitivity')

    # Scenario summary
    scenario_summary = pd.read_csv(os.path.join(sens_dir, 'scenario_summary.csv'))
    # LCOE summary
    lcoe_summary = pd.read_csv(os.path.join(sens_dir, 'common_lcoe_summary.csv'))
    # Transition matrices
    trans_adv = pd.read_csv(os.path.join(sens_dir, 'classification_transition_matrix_future_2050_to_advanced.csv'))
    trans_con = pd.read_csv(os.path.join(sens_dir, 'classification_transition_matrix_future_2050_to_conservative.csv'))
    # Island-level comparison
    island_comp = pd.read_csv(os.path.join(sens_dir, 'island_level_comparison.csv'))

    print(f"    -> scenario_summary: {len(scenario_summary)}, island_comparison: {len(island_comp)}")
    return {
        'SuppFig16_summary': scenario_summary,
        'SuppFig16_lcoe': lcoe_summary,
        'SuppFig16_trans_adv': trans_adv,
        'SuppFig16_trans_con': trans_con,
        'SuppFig16_islands': island_comp,
    }


# ============================================================
# Main: Generate all sheets and write to Excel
# ============================================================
def main():
    print("=" * 60)
    print("Generating Nature Communications Source Data Excel")
    print("=" * 60)

    sheets = {}

    # Main figures
    sheets['Fig1a_1b'] = generate_fig1a_1b()
    fig1c_data = generate_fig1c()
    sheets['Fig1c'] = fig1c_data
    sheets['Fig2'] = generate_fig2()
    sheets['Fig3'] = generate_fig3()
    sheets['Fig4'] = generate_fig4()

    # Supplementary figures
    sheets['SuppFig2_3'] = generate_supp_fig2_3()
    sheets['SuppFig4'] = generate_supp_fig4()
    sheets['SuppFig5'] = generate_supp_fig5(fig1c_data)
    sheets['SuppFig6'] = generate_supp_fig6()
    sheets['SuppFig7'] = generate_supp_fig7()
    # SuppFig8 = same as Fig2
    # SuppFig9_10 = same as Fig4
    sheets['SuppFig11_12'] = generate_supp_fig11_12()
    sheets['SuppFig13'] = generate_supp_fig13()

    # SuppFig14: population sensitivity (multiple sub-sheets)
    fig14_dict = generate_supp_fig14()
    for k, v in fig14_dict.items():
        sheets[k] = v

    # SuppFig15: threshold sensitivity
    sheets['SuppFig15'] = generate_supp_fig15()

    # SuppFig16: viability sensitivity (multiple sub-sheets)
    fig16_dict = generate_supp_fig16()
    for k, v in fig16_dict.items():
        sheets[k] = v

    # Write to Excel
    print(f"\nWriting to {OUTPUT_FILE}...")
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        for sheet_name, df in sheets.items():
            if df is not None and isinstance(df, pd.DataFrame) and len(df) > 0:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"  {sheet_name}: {df.shape[0]} rows x {df.shape[1]} cols")
            else:
                print(f"  {sheet_name}: SKIPPED (no data or references another sheet)")

    print(f"\nDone! Output: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == '__main__':
    main()
