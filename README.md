# Island Energy System Optimization with Climate Resilience

A comprehensive optimization framework for designing resilient island energy systems using Mixed Integer Linear Programming (MILP). This model integrates multi-energy systems with advanced reliability modeling and climate scenario analysis to support sustainable energy planning for remote islands.

*For Chinese documentation, see [README_cn.md](README_cn.md)*

---

**📋 NOTE**: Quick testing instructions with synthetic data (no multi-GB downloads required) are available in [`test/`](test/) directory. See [`test/test.md`](test/test.md) for running the model with sample data in ~5 minutes.

---

## 🌊 Overview

This project implements a sophisticated energy system optimization model specifically designed for island communities facing climate change challenges. The system optimizes the design and operation of integrated electricity-heat-cold energy networks while ensuring high reliability under extreme weather conditions.

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
| `disaster_2020.py` | 2020 baseline | 2020 current | Historical baseline performance | `output_2020/` |
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

## 🚀 Getting Started

### Prerequisites

**Required Python Packages:**
```bash
pip install pandas numpy xarray gurobipy scipy geopy pvlib timezonefinder scikit-learn
```

**System Requirements:**
- Gurobi Optimizer with valid license
- Minimum 16GB RAM (32GB+ recommended for batch processing)
- Python 3.8+

### Input Data Requirements

```
project_root/
├── demand/                         # Hourly demand profiles
│   ├── demand_{lat}_{lon}.csv      # Heating/cooling demands
│   ├── pv_{lat}_{lon}.csv          # Solar potential
│   └── wt_{lat}_{lon}.csv          # Wind potential
├── CMIP6/                          # Climate model data
│   ├── MRI_2020_uas/              # 2020 u-wind component
│   ├── MRI_2020_vas/              # 2020 v-wind component  
│   ├── MRI_2050_uas/              # 2050 u-wind projections
│   └── MRI_2050_vas/              # 2050 v-wind projections
├── wave/                           # Wave energy data
│   ├── wave_2020.nc               # 2020 wave power density
│   ├── waveheight_2020.nc         # 2020 significant wave heights
│   ├── wave_2050.nc               # 2050 wave projections
│   └── waveheight_2050.nc         # 2050 wave height projections
└── LNG/
    └── LNG_Terminals.xlsx         # Global LNG terminal locations
```

### Single Island Execution

```bash
# Run single island optimization (example coordinates)
python disaster_2020.py --island_lat 25.5 --island_lon 120.0 --pop 1000

# Run future scenario
python disaster_future_2050.py --island_lat 25.5 --island_lon 120.0 --pop 1000
```

### Batch Processing

```bash
# Process all islands in chosen_island.csv
chmod +x run_jobs_all.sh

nohup ./run_jobs_all.sh > logs/run_tasks.log 2>&1 &

```

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
- Natural Gas: LNGV gasification = CHP consumption + excess (penalty)

**Reliability Requirements:**
- Expected Energy Not Served (EENS) ≤ 0.1% of total demand for each energy carrier
- Evaluated across all clustered failure scenarios with equal probability weighting

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
- Minimize worst-case energy shortfalls through shortfall variables

## 📁 Output Structure

### Directory Organization
```
project_root/
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
