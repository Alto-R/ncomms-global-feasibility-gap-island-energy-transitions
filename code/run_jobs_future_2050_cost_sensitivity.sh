#!/bin/bash

set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
RUN_MATRIX_FILE="${RUN_MATRIX_FILE:-$REPO_ROOT/result/future_2050_cost_sensitivity/future_2050_cost_sensitivity_run_matrix.csv}"
LOG_DIR="$REPO_ROOT/logs/future_2050_cost_sensitivity"

PYTHON_BIN="${PYTHON_BIN:-python3}"
MAX_CONCURRENT_RUNS="${MAX_CONCURRENT_RUNS:-20}"

SCENARIO_TARGET="all"
FORCE=0
LIMIT=""

mkdir -p "$LOG_DIR"

usage() {
    cat <<'EOF'
Usage:
  bash code/run_jobs_future_2050_cost_sensitivity.sh [all|output_future_2050_advanced|output_future_2050_conservative] [options]

Options:
  --force                    Re-run cases even if output files already exist.
  --limit N                  Limit the number of executable cases per scenario.
  --max-concurrent N         Maximum concurrent sensitivity cases. Default: 20
  --python-bin PATH          Python executable. Default: python3
  --run-matrix PATH          Run matrix CSV. Default: result/future_2050_cost_sensitivity/future_2050_cost_sensitivity_run_matrix.csv
  -h, --help                 Show this help message.

Examples:
  bash code/run_jobs_future_2050_cost_sensitivity.sh
  bash code/run_jobs_future_2050_cost_sensitivity.sh output_future_2050_advanced --force --max-concurrent 24
  bash code/run_jobs_future_2050_cost_sensitivity.sh output_future_2050_conservative --limit 20
  bash code/run_jobs_future_2050_cost_sensitivity.sh all --python-bin /path/to/python3
EOF
}

check_mip_gap() {
    local log_file=$1
    local task_name=$2
    local island_id=$3
    local target_gap_percent=1.00

    if [ ! -f "$log_file" ]; then
        return
    fi

    local gap_line
    gap_line=$(grep "Time limit reached. Using best solution found with gap" "$log_file" 2>/dev/null || true)

    if [ -n "$gap_line" ]; then
        local final_gap
        final_gap=$(echo "$gap_line" | awk '{print $NF}' | tr -d '%')

        if (( $(echo "$final_gap > $target_gap_percent" | bc -l) )); then
            echo "GAP CHECK FAILED: Island $island_id, Task $task_name. Final Gap: ${final_gap}% > ${target_gap_percent}%" >> "$MAIN_LOG"
        fi
    fi
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            all|output_future_2050_advanced|output_future_2050_conservative)
                SCENARIO_TARGET="$1"
                shift
                ;;
            --force)
                FORCE=1
                shift
                ;;
            --limit)
                LIMIT="$2"
                shift 2
                ;;
            --max-concurrent)
                MAX_CONCURRENT_RUNS="$2"
                shift 2
                ;;
            --python-bin)
                PYTHON_BIN="$2"
                shift 2
                ;;
            --run-matrix)
                RUN_MATRIX_FILE="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "Unknown argument: $1" >&2
                usage >&2
                exit 1
                ;;
        esac
    done
}

run_sensitivity_case() {
    local scenario_key=$1
    local script_name=$2
    local island_id=$3
    local island_lat=$4
    local island_lon=$5
    local target_population=$6
    local population_label=$7
    local output_dir=$8

    local log_file="$LOG_DIR/${scenario_key}_island_${island_id}_pop_${target_population}.log"
    local task_name="${scenario_key}|island=${island_id}|pop=${population_label}"

    echo "Case started: $task_name at $(date +'%Y-%m-%d %H:%M:%S')" >> "$MAIN_LOG"

    if ! (
        cd "$REPO_ROOT"
        "$PYTHON_BIN" "code/$script_name" \
            --island_lat "$island_lat" \
            --island_lon "$island_lon" \
            --pop "$target_population"
    ) >> "$log_file" 2>&1; then
        sleep 10
        if ! (
            cd "$REPO_ROOT"
            "$PYTHON_BIN" "code/$script_name" \
                --island_lat "$island_lat" \
                --island_lon "$island_lon" \
                --pop "$target_population"
        ) >> "$log_file" 2>&1; then
            echo "Case FAILED: $task_name at $(date +'%Y-%m-%d %H:%M:%S')" >> "$MAIN_LOG"
            exit 1
        fi
    fi

    check_mip_gap "$log_file" "$task_name" "$island_id"
    echo "Case completed: $task_name at $(date +'%Y-%m-%d %H:%M:%S')" >> "$MAIN_LOG"
    exit 0
}

collect_tasks() {
    local scenario_key=$1
    local task_file=$2

    "$PYTHON_BIN" - "$RUN_MATRIX_FILE" "$scenario_key" "$FORCE" "$LIMIT" "$REPO_ROOT" > "$task_file" <<'PY'
import csv
import os
import sys

run_matrix_file, scenario_key, force_flag, limit_arg, repo_root = sys.argv[1:6]
force = force_flag == "1"
limit = None if limit_arg == "" else int(limit_arg)
selected = 0

with open(run_matrix_file, newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    for row in reader:
        if row["scenario"] != scenario_key:
            continue

        existing = all(
            os.path.exists(os.path.join(repo_root, row[key]))
            for key in ("cost_file", "capacity_file", "results_file")
        )
        status = "skip_existing" if (existing and not force) else "run"

        writer.writerow(
            [
                status,
                row["island_id"],
                row["latitude"],
                row["longitude"],
                row["target_population"],
                row.get("population_label", row["target_population"]),
                row["script_name"],
                row["output_dir"],
                row.get("display_name", row["scenario"]),
            ]
        )

        if status == "run":
            selected += 1
            if limit is not None and selected >= limit:
                break
PY
}

run_scenario_batches() {
    local scenario_key=$1
    local scenario_label=$2

    MAIN_LOG="$LOG_DIR/main_${scenario_key}.log"
    : > "$MAIN_LOG"

    echo "Scenario: $scenario_label ($scenario_key)" >> "$MAIN_LOG"
    echo "Python: $PYTHON_BIN" >> "$MAIN_LOG"
    echo "Run matrix: $RUN_MATRIX_FILE" >> "$MAIN_LOG"
    echo "Max concurrent runs: $MAX_CONCURRENT_RUNS" >> "$MAIN_LOG"
    echo "Force rerun: $FORCE" >> "$MAIN_LOG"
    echo "Limit: ${LIMIT:-none}" >> "$MAIN_LOG"
    echo "============================================================" >> "$MAIN_LOG"

    if [ ! -f "$RUN_MATRIX_FILE" ]; then
        echo "Run matrix missing: $RUN_MATRIX_FILE" | tee -a "$MAIN_LOG"
        return 1
    fi

    local task_file
    task_file=$(mktemp)
    collect_tasks "$scenario_key" "$task_file"

    declare -a TASKS
    local skipped_existing=0
    while IFS=$'\t' read -r status island_id island_lat island_lon target_population population_label script_name output_dir display_name; do
        [ -z "${status:-}" ] && continue
        if [ "$status" = "skip_existing" ]; then
            skipped_existing=$((skipped_existing + 1))
            echo "Skip existing: island=$island_id pop=$population_label scenario=$scenario_key" >> "$MAIN_LOG"
            continue
        fi
        TASKS+=("${island_id}"$'\t'"${island_lat}"$'\t'"${island_lon}"$'\t'"${target_population}"$'\t'"${population_label}"$'\t'"${script_name}"$'\t'"${output_dir}"$'\t'"${display_name}")
    done < "$task_file"
    rm -f "$task_file"

    local total_cases=${#TASKS[@]}
    echo "Runnable cases: $total_cases" >> "$MAIN_LOG"
    echo "Skipped existing: $skipped_existing" >> "$MAIN_LOG"

    if [ $total_cases -eq 0 ]; then
        echo "No cases to run for $scenario_key." >> "$MAIN_LOG"
        echo "No cases to run for $scenario_key."
        return 0
    fi

    local batch_start=0
    local batch_num=1

    while [ $batch_start -lt $total_cases ]; do
        local batch_end=$((batch_start + MAX_CONCURRENT_RUNS - 1))
        if [ $batch_end -ge $total_cases ]; then
            batch_end=$((total_cases - 1))
        fi

        local batch_size=$((batch_end - batch_start + 1))
        local batch_start_time
        batch_start_time=$(date +'%Y-%m-%d %H:%M:%S')

        echo "------------------------------------------------------------" >> "$MAIN_LOG"
        echo "BATCH $batch_num: Cases $((batch_start + 1))-$((batch_end + 1)) (${batch_size} cases) started at $batch_start_time" >> "$MAIN_LOG"

        declare -A BATCH_PIDS
        declare -A BATCH_RESULTS

        for i in $(seq $batch_start $batch_end); do
            local task_info=${TASKS[$i]}
            local island_id island_lat island_lon target_population population_label script_name output_dir display_name
            IFS=$'\t' read -r island_id island_lat island_lon target_population population_label script_name output_dir display_name <<< "$task_info"

            run_sensitivity_case \
                "$scenario_key" \
                "$script_name" \
                "$island_id" \
                "$island_lat" \
                "$island_lon" \
                "$target_population" \
                "$population_label" \
                "$output_dir" &
            BATCH_PIDS["${island_id}_${target_population}"]=$!

            echo "  island=$island_id pop=$population_label started in background (PID: $!)" >> "$MAIN_LOG"
        done

        local batch_success_count=0
        local batch_fail_count=0

        for case_key in "${!BATCH_PIDS[@]}"; do
            local pid=${BATCH_PIDS[$case_key]}
            wait "$pid"
            local exit_code=$?
            BATCH_RESULTS[$case_key]=$exit_code

            if [ $exit_code -eq 0 ]; then
                batch_success_count=$((batch_success_count + 1))
            else
                batch_fail_count=$((batch_fail_count + 1))
            fi
        done

        local batch_end_time
        batch_end_time=$(date +'%Y-%m-%d %H:%M:%S')
        local batch_start_timestamp
        batch_start_timestamp=$(date -d "$batch_start_time" +%s)
        local batch_end_timestamp
        batch_end_timestamp=$(date -d "$batch_end_time" +%s)
        local batch_duration=$((batch_end_timestamp - batch_start_timestamp))
        local hours=$((batch_duration / 3600))
        local minutes=$(((batch_duration % 3600) / 60))
        local seconds=$((batch_duration % 60))
        local duration_format
        duration_format=$(printf "%02d:%02d:%02d" $hours $minutes $seconds)

        echo "BATCH $batch_num COMPLETED at $batch_end_time (Duration: $duration_format)" >> "$MAIN_LOG"
        echo "  Success: $batch_success_count, Failed: $batch_fail_count" >> "$MAIN_LOG"

        if [ $batch_fail_count -gt 0 ]; then
            echo "  Failed cases:" >> "$MAIN_LOG"
            for case_key in "${!BATCH_RESULTS[@]}"; do
                if [ ${BATCH_RESULTS[$case_key]} -ne 0 ]; then
                    echo "    $case_key (exit code: ${BATCH_RESULTS[$case_key]})" >> "$MAIN_LOG"
                fi
            done
        fi

        echo "" >> "$MAIN_LOG"

        unset BATCH_PIDS
        unset BATCH_RESULTS

        batch_start=$((batch_end + 1))
        batch_num=$((batch_num + 1))
    done

    echo "============================================================" >> "$MAIN_LOG"
    echo "All batches completed for $scenario_key." >> "$MAIN_LOG"
    echo "Finished $scenario_label ($scenario_key). Main log: $MAIN_LOG"
}

parse_args "$@"

case "$SCENARIO_TARGET" in
    all)
        run_scenario_batches "output_future_2050_advanced" "disaster_future_2050_advanced" || exit 1
        run_scenario_batches "output_future_2050_conservative" "disaster_future_2050_conservative" || exit 1
        ;;
    output_future_2050_advanced)
        run_scenario_batches "output_future_2050_advanced" "disaster_future_2050_advanced" || exit 1
        ;;
    output_future_2050_conservative)
        run_scenario_batches "output_future_2050_conservative" "disaster_future_2050_conservative" || exit 1
        ;;
    *)
        echo "Unknown scenario target: $SCENARIO_TARGET" >&2
        usage >&2
        exit 1
        ;;
esac
