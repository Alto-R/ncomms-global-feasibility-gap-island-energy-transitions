import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

from benchmark_population_sensitivity_config import RUN_MATRIX_PATH, SAMPLE_TABLE_PATH
from build_benchmark_population_sensitivity_sample import build_and_write


def _repo_root():
    return Path(__file__).resolve().parents[1]


def ensure_inputs(sample_path, run_matrix_path):
    sample_path = Path(sample_path)
    run_matrix_path = Path(run_matrix_path)
    if sample_path.exists() and run_matrix_path.exists():
        return
    build_and_write(sample_path=sample_path, run_matrix_path=run_matrix_path)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the all-island (>500 population) benchmark population sensitivity workflow."
    )
    parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python executable used to invoke the sensitivity scenario scripts.",
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run cases even when output files already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only build the run matrix and print the commands.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on the number of runs to execute.",
    )
    parser.add_argument(
        "--source-data-dir",
        default="demand/get1",
        help="Directory containing the benchmark 500-person demand/resource CSV files.",
    )
    return parser.parse_args()


def run_case(python_executable, script_path, row, repo_root, source_data_dir, dry_run):
    cmd = [
        python_executable,
        str(script_path),
        "--island_lat",
        str(row["latitude"]),
        "--island_lon",
        str(row["longitude"]),
        "--pop",
        str(int(row["target_population"])),
        "--source_pop",
        "500",
        "--output_dir",
        str(repo_root / Path(row["output_dir"])),
        "--source_data_dir",
        source_data_dir,
    ]
    if dry_run:
        return {
            "returncode": 0,
            "status": "dry_run",
            "command": " ".join(cmd),
        }

    completed = subprocess.run(cmd, cwd=repo_root, check=False)
    return {
        "returncode": completed.returncode,
        "status": "completed" if completed.returncode == 0 else "failed",
        "command": " ".join(cmd),
    }


def main():
    args = parse_args()
    repo_root = _repo_root()
    ensure_inputs(args.sample_file, args.run_matrix_file)
    run_matrix_df = pd.read_csv(args.run_matrix_file)

    records = []
    executed = 0
    for row in run_matrix_df.to_dict("records"):
        cost_file = repo_root / Path(row["cost_file"])
        capacity_file = repo_root / Path(row["capacity_file"])
        results_file = repo_root / Path(row["results_file"])

        if not args.force and cost_file.exists() and capacity_file.exists() and results_file.exists():
            status = "skipped_existing"
            command = ""
            returncode = 0
        else:
            if args.limit is not None and executed >= args.limit:
                break
            script_path = repo_root / "code" / row["script_name"]
            outcome = run_case(
                python_executable=args.python_executable,
                script_path=script_path,
                row=row,
                repo_root=repo_root,
                source_data_dir=args.source_data_dir,
                dry_run=args.dry_run,
            )
            status = outcome["status"]
            command = outcome["command"]
            returncode = outcome["returncode"]
            executed += 1

        records.append(
            {
                **row,
                "status": status,
                "returncode": returncode,
                "command": command,
            }
        )
        print(
            f"[{len(records):03d}] {row['scenario']} | pop={int(row['target_population'])} | "
            f"{row['display_name']} -> {status}"
        )

    manifest_df = pd.DataFrame(records)
    manifest_path = repo_root / "result" / "benchmark_population_sensitivity" / "run_execution_manifest.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_df.to_csv(manifest_path, index=False)
    print(f"Wrote execution manifest: {manifest_path}")


if __name__ == "__main__":
    main()
