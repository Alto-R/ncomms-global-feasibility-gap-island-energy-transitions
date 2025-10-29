# Test Documentation for Island Energy Optimization Model

This document provides instructions for running the test suite for the island energy transition optimization model, prepared for Nature Communications reviewers.

---

## 1. Overview

This test suite validates a multi-energy island optimization model that:
- **Optimizes energy system design** for islands using renewable resources (wind, solar, wave) and storage technologies
- **Models climate disaster impacts** on equipment reliability and operation
- **Integrates 14 energy technologies**: Wind turbines (WT), photovoltaics (PV), wave energy converters (WEC), combined heat and power (CHP), electric boilers (EB), air conditioning (AC), proton exchange membrane electrolyzers (PEM), fuel cells (FC), LNG storage and vaporizers (LNG, LNGV), and four storage types (ESS, TES, CES, H2S)
- **Ensures reliability** through Monte Carlo simulation and scenario clustering
- **Meets energy demands** for electricity, heating, cooling, gas, and hydrogen

The test suite includes three Python scripts that validate different aspects of the model under synthetic data conditions.

**Note on Data**: This test suite uses **synthetic climate data** to enable rapid reproduction of results. The full research uses CMIP6 climate model outputs (multiple terabytes), which are impractical for code review distribution. The synthetic data preserves the same statistical characteristics and temporal patterns as real CMIP6 data, allowing reviewers to validate the computational methodology without requiring terabyte-scale downloads.

---

## 2. System Requirements

**Python**: ≥ 3.8

**Required Packages**:
```
pandas >= 1.3.0, numpy >= 1.21.0, xarray >= 0.19.0, netCDF4 >= 1.5.7
gurobipy >= 9.5.0, scipy >= 1.7.0, geopy >= 2.2.0, pvlib >= 0.9.0
timezonefinder >= 5.2.0, scikit-learn >= 0.24.0, openpyxl >= 3.0.9
```

**Critical Dependency**: **Gurobi Optimizer** (version 9.5+) with valid license

- Download: <https://www.gurobi.com/downloads/>
- Academic licenses: <https://www.gurobi.com/academia/academic-program-and-licenses/>

**Hardware**: Minimum 16 GB RAM, recommended 32 GB RAM

---

## 3. Installation Guide

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
or
pip install pandas numpy xarray netCDF4 scipy geopy pvlib timezonefinder scikit-learn openpyxl gurobipy
```

**Note**: You do **NOT** need to download large CMIP6 climate datasets. The test suite generates small synthetic data files (< 10 MB).

### Step 2: Install and Activate Gurobi License

```bash
# After installing gurobipy
grbgetkey YOUR-LICENSE-KEY

# Verify installation
python -c "import gurobipy as gp; print(gp.gurobi.version())"
```

**Estimated installation time**: 5-10 minutes (excluding license acquisition)

---

## 4. Test Files Description

### **4.1 create_sample_data.py**

**Purpose**: Generates synthetic climate data **without requiring full CMIP6 datasets**.

**Why synthetic data?**
- Original CMIP6 outputs are **multiple terabytes** (global coverage, 1980-2100)
- Synthetic data enables rapid reproducibility (< 1 minute generation)
- Preserves realistic temporal patterns and climate correlations
- **Full research uses actual CMIP6 data** from ESGF portals; optimization methodology is identical

**Generates**:

- `wave_2020.nc`: Wave power density (3-22 kW/m)
- `waveheight_2020.nc`: Significant wave height (0.5-5.5 m)
- `wind_2020_uas.nc`: Eastward wind (-8 to 12 m/s)
- `wind_2020_vas.nc`: Northward wind (-6 to 10 m/s)

**Runtime**: ~5 seconds

### **4.2 disaster_free_test.py**

**Purpose**: Tests optimization under ideal conditions (no equipment failures)

**Validates**: Basic optimization, multi-energy integration (5 carriers), 14 technology coordination, storage cycling, economic optimization

**Runtime**: <1 minute

### **4.3 disaster_2020_test.py**

**Purpose**: Tests optimization with climate disaster scenarios and equipment failures

**Validates**: Equipment failure modeling (wind, PV, wave), weather-dependent repairs, Monte Carlo simulation (10 scenarios), K-means clustering (2-4 clusters), reliability constraints (EENS ≤ 0.1%), LNG procurement restrictions during disasters

**Runtime**: 1-5 minutes

**Key Point**: The **computational methodology is identical** for both data types. Synthetic data allows reviewers to validate the optimization algorithm, energy balance constraints, and output formats without multi-TB downloads.

---

## 5. Running the Tests

### **Step 1: Generate Sample Data**

```bash
cd test
python create_sample_data.py
```

Verify 4 `.nc` files created in `sampledata/` directory.

### **Step 2: Run Disaster-Free Test**

```bash
python disaster_free_test.py --island_lat 24.455253 --island_lon 122.988732 --pop 500
```

**Output files** (in `output_sample/`):
- `24.455253_122.988732_best_cost_free.csv`
- `24.455253_122.988732_capacity_free.csv`
- `24.455253_122.988732_results_free.csv`

### **Step 3: Run Disaster Scenario Test**

```bash
python disaster_2020_test.py --island_lat 24.455253 --island_lon 122.988732 --pop 500
```

**Output files** (in `output_sample/`):
- `24.455253_122.988732_best_cost_2020.csv`
- `24.455253_122.988732_capacity_2020.csv`
- `24.455253_122.988732_results_2020.csv`

**Total test execution time**: ~5 minutes

---

## 6. Expected Outputs

Each test generates 3 CSV files:

1. **Cost file** (`*_best_cost_*.csv`): 8 rows, 2 columns
   - Annualized investment cost, LNG purchase cost, O&M cost, energy discard, curtailment, load shedding, total operating cost, total annual cost
   - Expected range: $100k-$500k for 500 population

2. **Capacity file** (`*_capacity_*.csv`): 14 rows, 2 columns
   - Optimal capacity for each device (WT, PV, WEC, CHP, EB, AC, PEM, FC, LNG, LNGV, ESS, TES, CES, H2S)

3. **Results file** (`*_results_*.csv`): 2,920 rows, 40+ columns
   - Hourly operational data: technology outputs, storage states, energy balances, load shedding

**Key validation**: Disaster scenario cost should be 5-15% higher than disaster-free due to reliability requirements.

---

## Summary

These tests demonstrate that the computational methodology is scientifically sound and reproducible. The synthetic data approach allows code validation without requiring terabyte-scale climate datasets, while using identical optimization formulations as the full research.
