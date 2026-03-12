import argparse
from pathlib import Path

import pandas as pd

from benchmark_population_sensitivity_config import (
    RUN_MATRIX_PATH,
    RUNS_ROOT,
    SAMPLE_TABLE_PATH,
    SCENARIO_LABELS,
    SCENARIO_SCRIPTS,
    classify_climate_zone,
    classify_size_tier,
    population_levels_for_actual,
)


def _repo_root():
    return Path(__file__).resolve().parents[1]


def load_source_frames(repo_root):
    origin_path = repo_root / "result" / "island_data_origin.csv"
    viability_path = repo_root / "result" / "island_viability_summary_electric.csv"

    origin_df = pd.read_csv(origin_path)
    viability_df = pd.read_csv(viability_path)
    viability_df = viability_df[viability_df["scenario"] == "output_0"].copy()
    viability_df["island_id"] = viability_df["island_id"].astype(int)
    viability_df = viability_df[viability_df["population_raw"] > 500].copy()
    origin_df["ID"] = origin_df["ID"].astype(int)
    return origin_df, viability_df


def build_sample_table(origin_df, viability_df):
    origin_lookup = (
        origin_df[["ID", "Island"]]
        .drop_duplicates(subset=["ID"])
        .rename(columns={"ID": "island_id", "Island": "source_island_name"})
    )

    sample_df = viability_df[
        [
            "island_id",
            "Country",
            "lat",
            "lon",
            "population_raw",
            "income_per_capita_2020",
            "tariff_affordable",
            "tariff_breakeven",
            "viability_gap",
            "consumption_pc_kwh",
        ]
    ].copy()
    sample_df = sample_df.drop_duplicates(subset=["island_id"]).merge(origin_lookup, on="island_id", how="left")

    sample_df = sample_df.rename(
        columns={
            "Country": "country",
            "lat": "latitude",
            "lon": "longitude",
            "population_raw": "actual_population",
        }
    )
    sample_df["actual_population"] = sample_df["actual_population"].round().astype(int)
    sample_df["source_island_name"] = sample_df["source_island_name"].fillna(
        sample_df["island_id"].map(lambda value: f"Island {value}")
    )
    sample_df["display_name"] = sample_df["source_island_name"]
    sample_df["climate_zone"] = sample_df["latitude"].map(classify_climate_zone)
    sample_df["size_tier"] = sample_df["actual_population"].map(classify_size_tier)
    sample_df["benchmark_population"] = 500
    sample_df["benchmark_affected"] = True
    sample_df["scenario_scope"] = "output_0;output_2050"

    sample_df = sample_df.sort_values(
        ["climate_zone", "size_tier", "country", "actual_population", "island_id"],
        ascending=[True, True, True, True, True],
    ).reset_index(drop=True)
    sample_df["sample_order"] = range(1, len(sample_df) + 1)

    keep_columns = [
        "sample_order",
        "climate_zone",
        "size_tier",
        "island_id",
        "display_name",
        "source_island_name",
        "country",
        "latitude",
        "longitude",
        "actual_population",
        "income_per_capita_2020",
        "consumption_pc_kwh",
        "tariff_affordable",
        "tariff_breakeven",
        "viability_gap",
        "benchmark_population",
        "benchmark_affected",
        "scenario_scope",
    ]
    return sample_df[keep_columns]


def build_run_matrix(sample_df):
    population_order = {"500": 1, "2000": 2, "10000": 3, "actual": 4}
    rows = []
    for sample in sample_df.to_dict("records"):
        for scenario_name, script_name in SCENARIO_SCRIPTS.items():
            for target_population in population_levels_for_actual(sample["actual_population"]):
                population_label = "actual" if target_population == sample["actual_population"] else str(target_population)
                output_dir = RUNS_ROOT / scenario_name / f"pop_{int(target_population)}"
                rows.append(
                    {
                        "sample_order": sample["sample_order"],
                        "climate_zone": sample["climate_zone"],
                        "size_tier": sample["size_tier"],
                        "display_name": sample["display_name"],
                        "island_id": sample["island_id"],
                        "country": sample["country"],
                        "latitude": sample["latitude"],
                        "longitude": sample["longitude"],
                        "actual_population": sample["actual_population"],
                        "target_population": int(target_population),
                        "population_label": population_label,
                        "population_order": population_order[population_label],
                        "scenario": scenario_name,
                        "scenario_label": SCENARIO_LABELS[scenario_name],
                        "script_name": script_name,
                        "output_dir": output_dir.as_posix(),
                        "cost_file": (output_dir / f"{sample['latitude']}_{sample['longitude']}_best_cost.csv").as_posix(),
                        "capacity_file": (output_dir / f"{sample['latitude']}_{sample['longitude']}_capacity.csv").as_posix(),
                        "results_file": (output_dir / f"{sample['latitude']}_{sample['longitude']}_results.csv").as_posix(),
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["sample_order", "scenario", "population_order"]
    ).reset_index(drop=True)


def build_and_write(sample_path=SAMPLE_TABLE_PATH, run_matrix_path=RUN_MATRIX_PATH):
    repo_root = _repo_root()
    origin_df, viability_df = load_source_frames(repo_root)
    sample_df = build_sample_table(origin_df, viability_df)
    run_matrix_df = build_run_matrix(sample_df)

    sample_path = Path(sample_path)
    run_matrix_path = Path(run_matrix_path)
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    run_matrix_path.parent.mkdir(parents=True, exist_ok=True)
    sample_df.to_csv(sample_path, index=False)
    run_matrix_df.to_csv(run_matrix_path, index=False)
    return sample_df, run_matrix_df


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build the all-island (>500 population) benchmark sensitivity sample table and run matrix."
    )
    parser.add_argument(
        "--sample-output",
        default=str(SAMPLE_TABLE_PATH),
        help="Path to write the sample table CSV.",
    )
    parser.add_argument(
        "--run-matrix-output",
        default=str(RUN_MATRIX_PATH),
        help="Path to write the run matrix CSV.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    sample_df, run_matrix_df = build_and_write(
        sample_path=args.sample_output,
        run_matrix_path=args.run_matrix_output,
    )
    print(f"Wrote sample table: {args.sample_output}")
    print(f"Wrote run matrix: {args.run_matrix_output}")
    print(f"Affected islands (>500 population): {len(sample_df)}")
    print(f"Run matrix rows: {len(run_matrix_df)}")


if __name__ == "__main__":
    main()
