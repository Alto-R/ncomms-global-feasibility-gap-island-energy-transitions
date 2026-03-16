from pathlib import Path

FIXED_MEDIAN_BREAKEVEN = 0.1973
DEFAULT_SOURCE_POP = 500
DEFAULT_POPULATION_LEVELS = (500, 2000, 10000, "actual")

SENSITIVITY_ROOT = Path("result") / "benchmark_population_sensitivity"
SAMPLE_TABLE_PATH = SENSITIVITY_ROOT / "benchmark_population_sensitivity_sample.csv"
RUN_MATRIX_PATH = SENSITIVITY_ROOT / "benchmark_population_sensitivity_run_matrix.csv"
RUNS_ROOT = SENSITIVITY_ROOT / "runs"
ANALYSIS_ROOT = SENSITIVITY_ROOT / "analysis"
FIGURES_ROOT = ANALYSIS_ROOT / "figures"
TABLES_ROOT = ANALYSIS_ROOT / "tables"

SIX_REGION_NAMES = [
    "Feasible Low Cost High Affordability",
    "Feasible High Cost High Affordability",
    "Feasible Low Cost Low Affordability",
    "Infeasible High Cost High Affordability",
    "Infeasible Low Cost Low Affordability",
    "Infeasible High Cost Low Affordability",
]

SIX_REGION_SHORT_NAMES = {
    SIX_REGION_NAMES[0]: "Q1",
    SIX_REGION_NAMES[1]: "Q2",
    SIX_REGION_NAMES[2]: "Q3",
    SIX_REGION_NAMES[3]: "Q4",
    SIX_REGION_NAMES[4]: "Q5",
    SIX_REGION_NAMES[5]: "Q6",
}

SCENARIO_SCRIPTS = {
    "output_0": "disaster_free_benchmark_sensitivity.py",
    "output_2050": "disaster_2050_benchmark_sensitivity.py",
}

SCENARIO_LABELS = {
    "output_0": "Baseline",
    "output_2050": "Climate Stress 2050",
}

ANNUALIZATION_RATE = 0.05
ANNUALIZATION_LIFETIME = 20
TROPICAL_LATITUDE_MAX = 23.5

INVESTMENT_COST = {
    "WT": 1392,
    "PV": 1377,
    "WEC": 6000,
    "AC": 150,
    "EB": 250,
    "CHP": 1300,
    "PEM": 1371,
    "FC": 3000,
    "LNG": 700,
    "LNGV": 500,
    "ESS": 1365,
    "TES": 250,
    "CES": 250,
    "H2S": 50,
}

FIXED_OM_COST = {
    "WT": 43,
    "PV": 23,
    "LNG": 14,
    "WEC": 300,
    "CHP": 26,
    "EB": 5,
    "AC": 3,
    "PEM": 41,
    "FC": 90,
    "LNGV": 25,
    "ESS": 34,
    "TES": 6,
    "CES": 6,
    "H2S": 1.2,
}

COST_BUCKET_COLORS = {
    "renewable": "#3C7D96",
    "storage": "#C9854D",
    "lng": "#66806A",
    "other": "#8B6F9B",
    "discard": "#D2B48C",
    "load_shedding": "#B85450",
}


def annualization_factor(rate=ANNUALIZATION_RATE, lifetime=ANNUALIZATION_LIFETIME):
    return (rate * (1 + rate) ** lifetime) / ((1 + rate) ** lifetime - 1)


def classify_six_region(
    tariff_breakeven,
    tariff_affordable,
    median_breakeven=FIXED_MEDIAN_BREAKEVEN,
):
    is_feasible = tariff_breakeven <= tariff_affordable
    is_low_cost = tariff_breakeven <= median_breakeven
    is_high_affordability = tariff_affordable > median_breakeven

    if is_feasible:
        if is_low_cost and is_high_affordability:
            return SIX_REGION_NAMES[0]
        if (not is_low_cost) and is_high_affordability:
            return SIX_REGION_NAMES[1]
        if is_low_cost and (not is_high_affordability):
            return SIX_REGION_NAMES[2]
        return SIX_REGION_NAMES[5]

    if (not is_low_cost) and is_high_affordability:
        return SIX_REGION_NAMES[3]
    if is_low_cost and (not is_high_affordability):
        return SIX_REGION_NAMES[4]
    if (not is_low_cost) and (not is_high_affordability):
        return SIX_REGION_NAMES[5]
    return SIX_REGION_NAMES[3]


def population_levels_for_actual(actual_population):
    levels = []
    for value in DEFAULT_POPULATION_LEVELS:
        resolved = actual_population if value == "actual" else int(value)
        if resolved not in levels:
            levels.append(resolved)
    return levels


def classify_climate_zone(latitude):
    return "Tropical" if abs(float(latitude)) <= TROPICAL_LATITUDE_MAX else "Non-tropical"


def classify_size_tier(actual_population):
    actual_population = int(actual_population)
    if actual_population < 2000:
        return "500-2000"
    if actual_population < 10000:
        return "2000-10000"
    return ">=10000"
