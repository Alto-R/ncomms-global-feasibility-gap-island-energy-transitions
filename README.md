# Island Energy System Optimization with Climate Resilience

A comprehensive optimization framework for designing resilient island energy systems using Mixed Integer Linear Programming (MILP). This model integrates multi-energy systems with advanced reliability modeling and climate scenario analysis to support sustainable energy planning for remote islands.

*For Chinese documentation, see [README_cn.md](README_cn.md)*

---

## 🌊 Overview

This project implements a sophisticated energy system optimization model (MILP) specifically designed for island communities facing climate change challenges. The system optimizes the design and operation of integrated electricity-heat-cold energy networks while ensuring high reliability under extreme weather conditions.

### Key Features
- **Multi-Energy Integration**: Simultaneous optimization of electricity, heating, and cooling systems
- **Climate Resilience**: Advanced disaster modeling based on wind speed and wave height thresholds
- **Technology Learning**: Incorporates projected cost reductions for emerging technologies
- **Reliability Analysis**: Monte Carlo simulation with intelligent scenario clustering
- **Economic Optimization**: Total cost minimization including CAPEX, OPEX, and operational penalties

## 🏗️ System Architecture

### Energy Technologies (14 Types)

**Renewable Generation:**
- **WT (Wind Turbines)**: Onshore wind power generation
- **PV (Photovoltaic)**: Solar electricity generation  
- **WEC (Wave Energy Converters)**: Ocean wave power conversion

**Conventional Systems:**
- **LNG (Liquefied Natural Gas)**: Fuel storage with periodic procurement cycles
- **CHP (Combined Heat & Power)**: Natural gas-fired cogeneration units

**Energy Conversion:**
- **EB (Electric Boiler)**: Electricity-to-heat conversion
- **AC (Air Conditioning)**: Electricity-to-cooling conversion
- **PEM (Proton Exchange Membrane)**: Water electrolysis for hydrogen production 
- **FC (Fuel Cell)**: Hydrogen-to-electricity conversion with waste heat
- **LNGV (LNG Vaporizer)**: LNG gasification with cold energy recovery

**Energy Storage:**
- **ESS (Electrical Storage System)**: Battery storage
- **TES (Thermal Energy Storage)**: Hot water/steam storage systems
- **CES (Cold Energy Storage)**: Chilled water storage systems  
- **H2S (Hydrogen Storage)**: Compressed hydrogen storage

### Reliability Modeling

The system employs sophisticated failure modeling based on environmental conditions:

**Equipment Failure Probabilities:**
- **Based on vulnerability curve**

**Repair Constraints:**
- Wind/PV systems: Repair only possible when wind ≤20 m/s
- Wave systems: Repair requires both wind ≤20 m/s AND wave height ≤2m
- Repair times: WT/WEC (14 days), PV (4 days)

## 📊 Scenario Analysis

The model includes five distinct scenarios representing different climate conditions and technology maturity levels:

| Scenario File | Climate Data | Technology Costs | Purpose | Output Directory |
|---------------|--------------|------------------|---------|------------------|
| `disaster_free.py` | Ideal (No disaster) | 2020 current | Current ideal performance | `output_0/` |
| `disaster_2020.py` | 2020 baseline | 2020 current | Current baseline performance | `output_2020/` |
| `disaster_2050.py` | 2050 projections | 2020 current | Climate impact with current technology | `output_2050/` |
| `disaster_future_2030.py` | 2050 projections | 2030 projected | Early technology adoption benefits | `output_future_2030/` |
| `disaster_future_2040.py` | 2050 projections | 2040 projected | Mid-term technology maturation | `output_future_2040/` |
| `disaster_future_2050.py` | 2050 projections | 2050 projected | Full technology learning effects | `output_future_2050/` |

### Technology Cost Learning Curves

The model incorporates realistic cost projections for key technologies:

**Hydrogen Technologies:**
- PEM Electrolyzer: $1,120/kW → $915/kW → $748/kW (2020→2030→2050)
- Fuel Cell: $2,000/kW → $1,800/kW → $1,600/kW (2020→2030→2050)

**Energy Storage:**
- Battery ESS: $784/kWh → $686/kWh → $588/kWh (2020→2030→2050)

**Fixed Costs:** Wind, solar, LNG, and other mature technologies maintain constant costs across scenarios.

## 📋 System Requirements

**Operating Systems:**

- Windows 10/11
- Linux (Ubuntu 20.04+, CentOS 8+)
- macOS 11+ (Big Sur or later)

**Python:** >= 3.9 (tested on 3.9, 3.10, 3.11)

**Required Python Packages:**

*see requirements.txt for details*
- pandas >= 1.3.0
- numpy >= 1.21.0
- xarray >= 0.19.0
- netCDF4 >= 1.5.7
- gurobipy >= 9.5.0
- scipy >= 1.7.0
- geopy >= 2.2.0
- pvlib >= 0.9.0
- timezonefinder >= 5.2.0
- scikit-learn >= 0.24.0
- openpyxl >= 3.0.9

**Critical Dependency:**

- Gurobi Optimizer 11.0+ with valid license
- Download: <https://www.gurobi.com/downloads/>
- Academic licenses: <https://www.gurobi.com/academia/academic-program-and-licenses/>

**Hardware Requirements:**

- **Recommended**: 32 GB RAM, 16+ core CPU
- **Storage**: 70+ GB for full CMIP6 data

**Tested Platforms:**

- Windows 11 with Python 3.9, 3.10, 3.11
- Ubuntu 22.04 with Python 3.9, 3.10, 3.11
- macOS 14 with Python 3.9, 3.10, 3.11

## 🔧 Installation

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
or
pip install pandas numpy xarray netCDF4 scipy geopy pvlib timezonefinder scikit-learn openpyxl gurobipy
```

### Step 2: Configure Gurobi License

```bash
# Obtain license key from https://www.gurobi.com
grbgetkey YOUR-LICENSE-KEY

# Verify installation
python -c "import gurobipy as gp; print(gp.gurobi.version())"
```

**Estimated installation time**: 5-10 minutes on a standard desktop computer

**Optional: Virtual Environment** (recommended)

```bash
# Using conda
conda create -n island_env python=3.11
conda activate island_env

# Or using venv
python -m venv island_env
source island_env/bin/activate  # Windows: island_env\Scripts\activate
```

## 🎯 Quick Start Demo

### Demo with Synthetic Data

For quick testing without downloading large CMIP6 datasets, we provide synthetic climate data generation.

**Location**: All demo files are in the [`test/`](test/) directory. See [`test/test.md`](test/test.md) for detailed instructions.

### Running the Demo

**Step 1: Generate Sample Climate Data** (~30 seconds)

```bash
cd test
python create_sample_data.py
```

This creates 4 NetCDF files (~2 MB total).

**Step 2: Run Ideal Scenario Test** (~1 minutes)

```bash
python disaster_free_test.py --island_lat 24.455253 --island_lon 122.988732 --pop 500
```

**Step 3: Run Baseline Scenario Test** (~2 minutes)

```bash
python disaster_2020_test.py --island_lat 24.455253 --island_lon 122.988732 --pop 500
```

### Expected Demo Output

Output files are generated in `test/output_sample/`:

1. **`*_best_cost_*.csv`** (8 rows): System cost breakdown
   - Annualized investment, LNG costs, O&M, operational penalties
   - Expected total: $100k-$500k for 500 population

2. **`*_capacity_*.csv`** (14 rows): Optimal technology capacities
   - Renewable generation (WT, PV, WEC)
   - Energy conversion systems (CHP, EB, AC, PEM, FC, LNGV)
   - Storage systems (ESS, TES, CES, H2S)

3. **`*_results_*.csv`** (2,920 rows): Detailed operational data
   - Hourly power generation, storage states, energy flows
   - Supply-demand balances, load shedding events

### Demo Run Time

- **Total**: ~3 minutes (depending on CPU cores)
- **Tested on**: Intel i9-14900HX (24 cores), 16 GB RAM, Windows 11

See [`test/test.md`](test/test.md) for details.

**Note on Full-Scale Research**: The complete research results published in the manuscript were computed on a Linux-based high-performance computing (HPC) cluster with significantly more computational resources, enabling efficient computation of thousands of islands across multiple climate scenarios.



## 📖 Usage Instructions

### Data Directory Structure

```
project_root/
├── demand/                         # Energy demand profiles
│   ├── demand_{lat}_{lon}.csv      # Hourly heating/cooling
│   ├── pv_{lat}_{lon}.csv          # Solar potential 
│   └── wt_{lat}_{lon}.csv          # Wind potential
├── CMIP6/                          # Climate model projections
│   ├── MRI_2020_uas/              # U-wind component (NetCDF)
│   ├── MRI_2020_vas/              # V-wind component (NetCDF)
│   ├── MRI_2050_uas/              # Future projections
│   └── MRI_2050_vas/              # Future projections
├── wave/                           # Wave energy data
│   ├── wave_2020.nc               # Wave power density (kW/m)
│   ├── waveheight_2020.nc         # Significant wave height (m)
│   ├── wave_2050.nc               # Future wave projections
│   └── waveheight_2050.nc         # Future wave height
└── LNG/
    └── LNG_Terminals.xlsx         # Global LNG terminal database
```

**Data Format Requirements:**

- **Demand files**: CSV with timestamp index, columns: heating_demand, cooling_demand
- **Renewable potential**: CSV with timestamp index, column: electricity
- **Climate data**: NetCDF4 format, 3-hour temporal resolution, WGS84 coordinates
- **CMIP6 data access**: Download from ESGF portals

### Single Island Optimization

```bash
# Run Ideal scenario
python disaster_free.py --island_lat 25.5 --island_lon 120.0 --pop 1000
# Run Baseline scenario
python disaster_2020.py --island_lat 25.5 --island_lon 120.0 --pop 1000
# Run Climate stress scenario with current technology
python disaster_2050.py --island_lat 25.5 --island_lon 120.0 --pop 1000
# Run future scenarios with technology learning
python disaster_future_2030.py --island_lat 25.5 --island_lon 120.0 --pop 1000
python disaster_future_2040.py --island_lat 25.5 --island_lon 120.0 --pop 1000
python disaster_future_2050.py --island_lat 25.5 --island_lon 120.0 --pop 1000
```

**Command-line arguments:**

- `--island_lat`: Latitude in decimal degrees (WGS84)
- `--island_lon`: Longitude in decimal degrees (WGS84)
- `--pop`: Island population (scales energy demand)

### Batch Processing Multiple Islands

Create a CSV file `chosen_island.csv`:

```csv
island_name,latitude,longitude,population
Island_A,25.5,120.0,1000
Island_B,24.2,122.5,500
```

Run batch processing:

```bash
chmod +x run_jobs_all.sh
nohup ./run_jobs_all.sh > logs/run_tasks.log 2>&1 &
```

### Modifying Model Parameters

Key parameters can be adjusted in the Python scenario files:

| Parameter | Location | Description |
|-----------|----------|-------------|
| Investment costs | Lines 295-301 | Technology CAPEX ($/kW or $/kWh) |
| Efficiencies | Lines 303-306 | Conversion/storage efficiencies |
| LNG pricing | Lines 310-313 | Fuel cost, transport, fixed charter |
| Penalty coefficients | Lines 316-320 | Curtailment, load shedding penalties |
| Repair times | Lines 333-335 | Equipment restoration durations |
| Monte Carlo scenarios | Line 513 | Number of failure scenarios (default: 10,000) |
| Reliability target | Line 869 | EENS limit (default: 0.1% of demand) |

### Reproduction Instructions

To reproduce manuscript results:

1. **Prepare renewable potential and energy demand data** in `demand_get/` folder, and download climate model data from external sources
   - Follow manuscript "Method: Renewable Potential and Demand Assessment and Supplementary information: Supplementary Method 3"
   - Download CMIP6 climate data from ESGF portals
     - Model: MRI-AGCM3-2-S_highresSST
     - Variables: uas, vas (wind components)
     - Scenarios: SSP5-8.5

2. **Run optimization code** in `code/` folder
   - Execute scenario scripts for all islands in your database
   - Generate optimization results for all climate and technology scenarios

3. **Process results** in `result/` folder
   - Compile optimization outputs across scenarios
   - Calculate summary statistics and performance metrics

4. **Visualize results** in `visualization/` folder
   - Run visualization scripts to reproduce manuscript figures
   - Scripts correspond to figures: `fig1_*.ipynb` → Figure 1, `fig2_*.ipynb` → Figure 2, etc.

## ⚙️ Model Formulation

### Objective Function
Minimize total annualized system cost:

```
min: CAPEX_annualized + OPEX_fixed + LNG_costs + Curtailment_penalties + Load_shedding_penalties
```

**Cost Components:**
- **Investment Costs**: Annualized over 20-year lifetime at 5% discount rate
- **Fixed O&M**: Annual maintenance costs proportional to capacity
- **LNG Costs**: Procurement + transportation (distance-based) + fixed charter costs
- **Operational Penalties**: Renewable curtailment, load shedding, energy spillage

### Key Constraints

**Energy Balance (Multi-Energy):**
- Electricity: Generation + storage discharge = demand + conversion loads + storage charge
- Heat: EB + CHP heat + FC heat + TES discharge = heating demand + TES charge  
- Cold: AC + LNGV cold + CES discharge = cooling demand + CES charge
- Hydrogen: PEM production + H2S discharge = FC consumption + H2S charge
- Natural Gas: LNGV gasification = CHP consumption

**Reliability Requirements:**
- Expected Energy Not Served (EENS) ≤ 0.1% of total demand for each energy carrier

**Storage Operations:**
- Cyclic boundary conditions (end state = initial state)
- Self-discharge losses: ESS/H2S (0.01%/hour), TES/CES (5%/hour)
- Power limits: Charge/discharge ≤ 25% of storage capacity

**LNG Procurement:**
- Periodic purchasing every 14 days (112 time steps at 3-hour resolution)
- Disaster-sensitive: No procurement during extreme weather periods
- Storage balance with consumption for CHP and gasification

### Reliability Analysis Methodology

**1. Monte Carlo Simulation:**
- Generate 10000 independent equipment failure scenarios
- Weather-dependent failure probabilities for renewable technologies
- Repair time modeling with weather constraints

**2. Scenario Reduction:**
- Extract statistical features: total downtime, max consecutive failures, event frequency
- K-means clustering with automatic cluster selection using silhouette coefficient
- Select representative scenarios closest to cluster centroids

**3. Robust Optimization:**
- Ensure system reliability across all representative failure scenarios

## 📁 Output Structure

### Directory Organization
```
project_root/
├── output_0/              # Ideal scenario results
├── output_2020/           # Baseline scenario results
├── output_2050/           # Climate change impact
├── output_future_2030/    # Early tech adoption (2030)
├── output_future_2040/    # Mid-term tech development (2040)  
├── output_future_2050/    # Mature technology scenario (2050)
└── logs/                  # Execution logs and error tracking
```

### Result Files (per island)
**Cost Analysis:**
- `{lat}_{lon}_best_cost.csv`: Complete cost breakdown (CAPEX, OPEX, fuel, penalties)

**System Design:**
- `{lat}_{lon}_capacity.csv`: Optimal capacity for all 14 technology types

**Operational Results:**
- `{lat}_{lon}_results.csv`: 2,920 time steps of detailed operational data including:
  - Power generation by technology
  - Storage charge/discharge cycles  
  - Energy conversion flows
  - Supply-demand balances
  - Load shedding and curtailment

### Performance Monitoring
- `logs/main_log.log`: Detailed execution log for climate scenarios
- `logs/main_future_log.log`: Technology scenario execution log  
- `logs/gap_failure_islands.csv`: Islands exceeding 1% MIP optimality gap

## 🔬 Research Applications

### Climate Resilience Studies
- **Impact Assessment**: Quantify climate change effects on energy system performance
- **Adaptation Planning**: Identify optimal technology portfolios for future conditions
- **Risk Analysis**: Evaluate system vulnerability to extreme weather events

### Technology Economics  
- **Learning Curve Analysis**: Model benefits of cost reductions in emerging technologies
- **Investment Timing**: Optimize technology deployment schedules
- **Economic Viability**: Compare renewable vs. conventional system economics

### Energy Security
- **Reliability Enhancement**: Design systems meeting strict availability requirements
- **Fuel Security**: Minimize dependence on imported fuels through local renewables
- **Grid Resilience**: Ensure stable operation during equipment failures

### Policy Support
- **Infrastructure Planning**: Support long-term energy infrastructure investments
- **Technology Incentives**: Evaluate policies promoting renewable energy adoption  
- **Climate Adaptation**: Guide resilient infrastructure development strategies

---

## 📄 License & Citation

This project is developed for academic research purposes. When using this model, please cite relevant publications and acknowledge the comprehensive climate and reliability modeling approach.

**Technical Contact**: For model implementation questions or collaboration opportunities.
