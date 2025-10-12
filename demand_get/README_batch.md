# Enhanced Batch API Processing

## Overview
Enhanced batch processing system for renewables.ninja API with automatic token rotation and progress tracking.

## Features
- **Automatic token rotation**: Switches between tokens when rate limits are reached
- **Rate limit management**: Tracks 50 calls/hour limit per token
- **Progress saving**: Saves progress and can resume interrupted processing
- **Comprehensive logging**: Detailed logs saved to `api_batch_log.txt`
- **Error handling**: Retry mechanism for failed API calls

## Usage

### Quick Start
```python
from api import batch_get_data

tokens = [
    'your_token_1',
    'your_token_2', 
    'your_token_3',
    'your_token_4',
    'your_token_5'
]

# Process islands with automatic token rotation
successful, failed = batch_get_data(
    island_csv='island_test.csv',
    tokens=tokens,
    output_dir='data',
    progress_file='progress.txt'
)
```

### Command Line Usage
```bash
python batch_example.py
```

## Rate Limits & Performance

- **API Limit**: 50 calls per hour per token
- **Calls per island**: 3 (PV, Wind, Demand)
- **Islands per hour per token**: ~16 islands
- **With 5 tokens**: ~80 islands per hour

## File Structure
```
demand_get/
├── api.py                 # Enhanced API functions with TokenManager
├── batch_example.py       # Usage example
├── island_test.csv        # Island data
├── progress.txt          # Progress tracking (auto-generated)
├── api_batch_log.txt     # Detailed logs (auto-generated)
└── data/                 # Output data files
    ├── pv_lat_lon.csv
    ├── wt_lat_lon.csv
    └── demand_lat_lon.csv
```

## Configuration Options

### TokenManager Parameters
- `max_calls_per_hour`: Rate limit (default: 50)
- `tokens`: List of API tokens

### batch_get_data Parameters
- `island_csv`: CSV file with island data (requires: ID, Lat, Long, pop, Region)
- `tokens`: List of API tokens
- `output_dir`: Output directory for data files
- `progress_file`: File to track completed islands

## Progress Tracking
- Progress is automatically saved after each successful island
- If interrupted, restart the script to resume from where it left off
- Progress file format: One island ID per line

## Error Handling
- Failed API calls are automatically retried up to 5 times
- Failed islands are logged and reported at the end
- Script continues processing even if some islands fail

## Logging
All activities are logged to:
- Console output
- `api_batch_log.txt` file

Log includes:
- Token switching events
- API call status
- Processing progress
- Error messages
- Final statistics

## Example Output
```
2024-01-01 10:00:00 - INFO - Starting batch processing for 15 islands
2024-01-01 10:00:00 - INFO - Already completed: 0 islands
2024-01-01 10:00:00 - INFO - Token status: {'Token_1': '0/50', 'Token_2': '0/50', ...}
2024-01-01 10:00:01 - INFO - Processing island 8489: (-3.856477, -32.425866)
2024-01-01 10:00:01 - INFO - Using token 1, Status: {'Token_1': '3/50', ...}
2024-01-01 10:00:15 - INFO - Successfully processed island 8489 (1/15)
...
2024-01-01 10:15:30 - INFO - Switched to token 2 (calls in last hour: 0)
...
```