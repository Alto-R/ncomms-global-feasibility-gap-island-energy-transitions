from pathlib import Path


def _replace_once(text, old, new, label):
    occurrences = text.count(old)
    if occurrences != 1:
        raise RuntimeError(f"Expected exactly one match for {label}, found {occurrences}.")
    return text.replace(old, new, 1)


def _transform_source(source_text, scenario_name):
    source_text = _replace_once(
        source_text,
        'parser.add_argument("--pop", type=int, required=True, help="Population of the island")',
        (
            'parser.add_argument("--pop", type=int, required=True, help="Population of the island")\n'
            'parser.add_argument("--source_pop", type=int, default=500, help="Benchmark population used to generate the source time series")\n'
            'parser.add_argument("--output_dir", type=str, default=None, help="Directory for sensitivity outputs")\n'
            'parser.add_argument("--source_data_dir", type=str, default="demand/get1", help="Directory containing benchmark demand/resource CSV files")'
        ),
        "parser arguments",
    )

    source_text = _replace_once(
        source_text,
        """pop = args.pop
if pop < 500:
    pop = pop
else:
    pop = 500
island_coords = (island_lat, island_lon)
""",
        f"""pop = args.pop
source_pop = args.source_pop
if pop <= 0:
    raise ValueError("Population must be positive.")
if source_pop <= 0:
    raise ValueError("Source population must be positive.")
scale_factor = pop / source_pop
output_dir = args.output_dir or os.path.join(
    "result", "benchmark_population_sensitivity", "runs", "{scenario_name}", f"pop_{{int(pop)}}"
)
source_data_dir = args.source_data_dir
island_coords = (island_lat, island_lon)
""",
        "population cap block",
    )

    source_text = _replace_once(
        source_text,
        """demand_data = pd.read_csv(f'demand/get1/demand_{island_lat}_{island_lon}.csv', index_col=0, parse_dates=True)
pv_data = pd.read_csv(f'demand/get1/pv_{island_lat}_{island_lon}.csv', index_col=0, parse_dates=True)
wt_data = pd.read_csv(f'demand/get1/wt_{island_lat}_{island_lon}.csv', index_col=0, parse_dates=True)
""",
        """demand_data = pd.read_csv(os.path.join(source_data_dir, f'demand_{island_lat}_{island_lon}.csv'), index_col=0, parse_dates=True)
pv_data = pd.read_csv(os.path.join(source_data_dir, f'pv_{island_lat}_{island_lon}.csv'), index_col=0, parse_dates=True)
wt_data = pd.read_csv(os.path.join(source_data_dir, f'wt_{island_lat}_{island_lon}.csv'), index_col=0, parse_dates=True)
""",
        "source data directory block",
    )

    source_text = _replace_once(
        source_text,
        """# 提取功率数组
pv_power = pv_data_3h['electricity'].values
wind_power = wt_data_3h['electricity'].values
""",
        """# 提取功率数组
demand_data_3h[['heating_demand', 'cooling_demand']] = demand_data_3h[['heating_demand', 'cooling_demand']].mul(scale_factor)
pv_power = pv_data_3h['electricity'].values * scale_factor
wind_power = wt_data_3h['electricity'].values * scale_factor
""",
        "time-series scaling block",
    )

    source_text = _replace_once(
        source_text,
        (
            "capacity_df, results, all_cost, cost_df = integrated_optimization_model()\n"
            f"cost_df.to_csv(f'output_{scenario_name.split('_')[-1]}/{{island_lat}}_{{island_lon}}_best_cost.csv', index=False)\n"
            f"capacity_df.to_csv(f'output_{scenario_name.split('_')[-1]}/{{island_lat}}_{{island_lon}}_capacity.csv', index=False)\n"
            f"results.to_csv(f'output_{scenario_name.split('_')[-1]}/{{island_lat}}_{{island_lon}}_results.csv', index=False)"
        ),
        """capacity_df, results, all_cost, cost_df = integrated_optimization_model()
if capacity_df is None or results is None or cost_df is None:
    raise RuntimeError("Sensitivity optimization did not produce output files.")

os.makedirs(output_dir, exist_ok=True)
cost_df.to_csv(os.path.join(output_dir, f"{island_lat}_{island_lon}_best_cost.csv"), index=False)
capacity_df.to_csv(os.path.join(output_dir, f"{island_lat}_{island_lon}_capacity.csv"), index=False)
results.to_csv(os.path.join(output_dir, f"{island_lat}_{island_lon}_results.csv"), index=False)
run_metadata = pd.DataFrame(
    [
        {
            "scenario": output_dir.replace("\\\\", "/").split("/")[-2],
            "target_population": pop,
            "source_population": source_pop,
            "scale_factor": scale_factor,
            "source_data_dir": source_data_dir,
            "island_lat": island_lat,
            "island_lon": island_lon,
        }
    ]
)
run_metadata.to_csv(os.path.join(output_dir, f"{island_lat}_{island_lon}_run_metadata.csv"), index=False)
""",
        "output write block",
    )
    return source_text


def run_transformed_source(source_filename, scenario_name):
    source_path = Path(__file__).with_name(source_filename)
    source_text = source_path.read_text(encoding="utf-8")
    transformed = _transform_source(source_text, scenario_name)
    exec_globals = {
        "__name__": "__main__",
        "__file__": str(source_path),
    }
    exec(compile(transformed, f"{source_filename}::<benchmark_population_sensitivity>", "exec"), exec_globals)
