"""
Create Simplified Sample Data for Quick Testing
===============================================
This script generates minimal synthetic data to demonstrate the optimization model
without requiring large climate model datasets (CMIP6).

Generated files:
- sampledata/wave_2020.nc: Synthetic wave power density (WPD) data
- sampledata/waveheight_2020.nc: Synthetic wave height (Hs) data
- sampledata/wind_2020_uas.nc: Synthetic u-component wind speed data
- sampledata/wind_2020_vas.nc: Synthetic v-component wind speed data

Author: For Nature Communications Review
"""

import numpy as np
import pandas as pd
import xarray as xr
import os

print("="*70)
print("Creating Sample Data for Island Energy Optimization Model")
print("="*70)

# Test island coordinates (example: near Taiwan)
TEST_LAT = 24.455253
TEST_LON = 122.988732

# Ensure sampledata directory exists
os.makedirs('sampledata', exist_ok=True)

# ==================== 1. Wave Power Density Data ====================
print("\n[1/4] Generating wave power density data (wave_2020.nc)...")

# Create small spatial grid
lat_grid = np.array([TEST_LAT - 0.5, TEST_LAT, TEST_LAT + 0.5])
lon_grid = np.array([TEST_LON - 0.5, TEST_LON, TEST_LON + 0.5])

# Time array: 2020 with 3-hour resolution (2920 timesteps)
time_array = pd.date_range('2020-01-01', '2020-12-31 21:00:00', freq='3h')
n_timesteps = len(time_array)

# Generate realistic wave power density (kW/m)
# Pattern: seasonal variation (higher in winter) + daily fluctuations
np.random.seed(42)
day_of_year = np.arange(n_timesteps) / 8  # 8 timesteps per day
seasonal_component = 12 + 5 * np.sin(2 * np.pi * (day_of_year - 30) / 365)
random_component = np.random.uniform(-2, 2, n_timesteps)
wpd_timeseries = np.clip(seasonal_component + random_component, 3, 22)

# Expand to 4D: [time, npt, lat, lon]
wpd_4d = np.zeros((n_timesteps, 1, len(lat_grid), len(lon_grid)))
for i, lat in enumerate(lat_grid):
    for j, lon in enumerate(lon_grid):
        # Add spatial variation
        factor = 1.0 + 0.08 * (i - 1) + 0.04 * (j - 1)
        wpd_4d[:, 0, i, j] = wpd_timeseries * factor

# Create xarray Dataset
wave_dataset = xr.Dataset(
    data_vars={'WPD': (['time', 'npt', 'lat', 'lon'], wpd_4d)},
    coords={
        'time': time_array,
        'npt': [1],
        'lat': lat_grid,
        'lon': lon_grid
    },
    attrs={
        'title': 'Synthetic Wave Power Density Data',
        'description': 'Simplified data for testing island energy optimization',
        'institution': 'Generated for manuscript review',
        'created': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    }
)
wave_dataset['WPD'].attrs = {
    'long_name': 'Wave Power Density',
    'standard_name': 'sea_surface_wave_power_density',
    'units': 'kW/m',
    'valid_range': [0, 100]
}

# Save to netCDF
wave_file = 'sampledata/wave_2020.nc'
wave_dataset.to_netcdf(wave_file)
print(f"   ✓ Created: {wave_file}")
print(f"   ✓ Shape: {wpd_4d.shape}")
print(f"   ✓ Time: {time_array[0].strftime('%Y-%m-%d')} to {time_array[-1].strftime('%Y-%m-%d')}")
print(f"   ✓ WPD range: {wpd_timeseries.min():.1f} - {wpd_timeseries.max():.1f} kW/m")


# ==================== 2. Wave Height Data ====================
print("\n[2/4] Generating wave height data (waveheight_2020.nc)...")

# Generate realistic significant wave height (Hs, in meters)
# Wave height is related to wave power, but not exactly the same
# Using a different pattern with correlation to WPD
np.random.seed(45)
# Hs typically ranges from 1-4m for moderate seas
# WPD ∝ Hs^2 * T (where T is wave period), so roughly Hs ∝ sqrt(WPD)
# Adding some independent variation for realism
hs_base = np.sqrt(wpd_timeseries / 5)  # Rough conversion
hs_variation = np.random.uniform(-0.3, 0.3, n_timesteps)
hs_timeseries = np.clip(hs_base + hs_variation, 0.5, 5.5)

# Expand to 4D: [time, npt, lat, lon]
hs_4d = np.zeros((n_timesteps, 1, len(lat_grid), len(lon_grid)))
for i, lat in enumerate(lat_grid):
    for j, lon in enumerate(lon_grid):
        # Add spatial variation consistent with WPD
        factor = 1.0 + 0.08 * (i - 1) + 0.04 * (j - 1)
        hs_4d[:, 0, i, j] = hs_timeseries * factor

# Create xarray Dataset for wave height
waveheight_dataset = xr.Dataset(
    data_vars={'Hs': (['time', 'npt', 'lat', 'lon'], hs_4d)},
    coords={
        'time': time_array,
        'npt': [1],
        'lat': lat_grid,
        'lon': lon_grid
    },
    attrs={
        'title': 'Synthetic Significant Wave Height Data',
        'description': 'Simplified data for testing island energy optimization',
        'institution': 'Generated for manuscript review',
        'created': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    }
)
waveheight_dataset['Hs'].attrs = {
    'long_name': 'Significant Wave Height',
    'standard_name': 'sea_surface_wave_significant_height',
    'units': 'm',
    'valid_range': [0, 20]
}

# Save to netCDF
waveheight_file = 'sampledata/waveheight_2020.nc'
waveheight_dataset.to_netcdf(waveheight_file)
print(f"   ✓ Created: {waveheight_file}")
print(f"   ✓ Shape: {hs_4d.shape}")
print(f"   ✓ Time: {time_array[0].strftime('%Y-%m-%d')} to {time_array[-1].strftime('%Y-%m-%d')}")
print(f"   ✓ Hs range: {hs_timeseries.min():.1f} - {hs_timeseries.max():.1f} m")


# ==================== 3. Wind Speed Data (u-component) ====================
print("\n[3/4] Generating u-component wind speed data (wind_2020_uas.nc)...")

# Generate realistic u-component wind speed (eastward, m/s)
# Pattern: seasonal variation + diurnal cycle + random fluctuations
np.random.seed(43)

# Seasonal component (higher wind in winter/spring)
seasonal_wind_u = 5.0 + 2.0 * np.sin(2 * np.pi * (day_of_year - 80) / 365)

# Diurnal cycle (higher wind during day, lower at night)
hour_of_day = (np.arange(n_timesteps) % 8) * 3  # 0-21 hours
diurnal_component = 1.0 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)

# Random component for realistic variability
random_wind = np.random.uniform(-1.5, 1.5, n_timesteps)

# Combine components (typical offshore wind u-component: -10 to 10 m/s)
uas_timeseries = np.clip(seasonal_wind_u + diurnal_component + random_wind, -8, 12)

# Expand to 3D: [time, lat, lon]
uas_3d = np.zeros((n_timesteps, len(lat_grid), len(lon_grid)))
for i, lat in enumerate(lat_grid):
    for j, lon in enumerate(lon_grid):
        # Add spatial variation
        factor = 1.0 + 0.05 * (i - 1) + 0.03 * (j - 1)
        uas_3d[:, i, j] = uas_timeseries * factor

# Create xarray Dataset for uas
uas_dataset = xr.Dataset(
    data_vars={'uas': (['time', 'lat', 'lon'], uas_3d)},
    coords={
        'time': time_array,
        'lat': lat_grid,
        'lon': lon_grid
    },
    attrs={
        'title': 'Synthetic U-Component Wind Speed Data',
        'description': 'Simplified data for testing island energy optimization',
        'institution': 'Generated for manuscript review',
        'created': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    }
)
uas_dataset['uas'].attrs = {
    'long_name': 'Eastward Near-Surface Wind',
    'standard_name': 'eastward_wind',
    'units': 'm s-1',
    'valid_range': [-50, 50]
}

# Save to netCDF
uas_file = 'sampledata/wind_2020_uas.nc'
uas_dataset.to_netcdf(uas_file)
print(f"   ✓ Created: {uas_file}")
print(f"   ✓ Shape: {uas_3d.shape}")
print(f"   ✓ Time: {time_array[0].strftime('%Y-%m-%d')} to {time_array[-1].strftime('%Y-%m-%d')}")
print(f"   ✓ uas range: {uas_timeseries.min():.1f} - {uas_timeseries.max():.1f} m/s")


# ==================== 4. Wind Speed Data (v-component) ====================
print("\n[4/4] Generating v-component wind speed data (wind_2020_vas.nc)...")

# Generate realistic v-component wind speed (northward, m/s)
np.random.seed(44)

# Seasonal component (slightly different pattern from u-component)
seasonal_wind_v = 3.5 + 1.5 * np.cos(2 * np.pi * (day_of_year - 60) / 365)

# Diurnal cycle with phase shift
diurnal_component_v = 0.8 * np.sin(2 * np.pi * (hour_of_day - 9) / 24)

# Random component
random_wind_v = np.random.uniform(-1.2, 1.2, n_timesteps)

# Combine components (typical offshore wind v-component: -8 to 10 m/s)
vas_timeseries = np.clip(seasonal_wind_v + diurnal_component_v + random_wind_v, -6, 10)

# Expand to 3D: [time, lat, lon]
vas_3d = np.zeros((n_timesteps, len(lat_grid), len(lon_grid)))
for i, lat in enumerate(lat_grid):
    for j, lon in enumerate(lon_grid):
        # Add spatial variation
        factor = 1.0 + 0.06 * (i - 1) + 0.02 * (j - 1)
        vas_3d[:, i, j] = vas_timeseries * factor

# Create xarray Dataset for vas
vas_dataset = xr.Dataset(
    data_vars={'vas': (['time', 'lat', 'lon'], vas_3d)},
    coords={
        'time': time_array,
        'lat': lat_grid,
        'lon': lon_grid
    },
    attrs={
        'title': 'Synthetic V-Component Wind Speed Data',
        'description': 'Simplified data for testing island energy optimization',
        'institution': 'Generated for manuscript review',
        'created': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    }
)
vas_dataset['vas'].attrs = {
    'long_name': 'Northward Near-Surface Wind',
    'standard_name': 'northward_wind',
    'units': 'm s-1',
    'valid_range': [-50, 50]
}

# Save to netCDF
vas_file = 'sampledata/wind_2020_vas.nc'
vas_dataset.to_netcdf(vas_file)
print(f"   ✓ Created: {vas_file}")
print(f"   ✓ Shape: {vas_3d.shape}")
print(f"   ✓ Time: {time_array[0].strftime('%Y-%m-%d')} to {time_array[-1].strftime('%Y-%m-%d')}")
print(f"   ✓ vas range: {vas_timeseries.min():.1f} - {vas_timeseries.max():.1f} m/s")

# Calculate and display total wind speed for reference
total_wind = np.sqrt(uas_timeseries**2 + vas_timeseries**2)
print(f"   ✓ Total wind speed range: {total_wind.min():.1f} - {total_wind.max():.1f} m/s")


# ==================== Summary ====================
print("\n" + "="*70)
print("Sample Data Generation Complete!")
print("="*70)
print(f"\nGenerated files in 'sampledata/' directory:")
print(f"  1. wave_2020.nc         - Wave power density WPD (3x3 grid, 2920 timesteps)")
print(f"  2. waveheight_2020.nc   - Wave height Hs (3x3 grid, 2920 timesteps)")
print(f"  3. wind_2020_uas.nc     - U-component wind (3x3 grid, 2920 timesteps)")
print(f"  4. wind_2020_vas.nc     - V-component wind (3x3 grid, 2920 timesteps)")
print(f"\nTest coordinates: ({TEST_LAT:.4f}, {TEST_LON:.4f})")
print(f"Time resolution: 3-hour")
print(f"Coverage: 2020-01-01 to 2020-12-31")
print("\nData format compatible with your processing code:")
print("  - Wave WPD: WPD variable with [time, npt, lat, lon] dimensions")
print("  - Wave Hs: Hs variable with [time, npt, lat, lon] dimensions")
print("  - Wind: uas/vas variables with [time, lat, lon] dimensions")
print("\nYou can now run the optimization model with these synthetic datasets.")
print("="*70)
