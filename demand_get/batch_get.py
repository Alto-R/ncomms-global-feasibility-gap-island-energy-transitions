#!/usr/bin/env python3
"""
Enhanced batch processing example with automatic token rotation
Usage: python batch_get.py
"""

from api import batch_get_data

def main():
    # Your API tokens
    tokens = [
    ]
    
    # Configuration
    island_csv = 'cluster_island_2015_withregion.csv'  # Change to your island CSV file
    output_dir = 'data/get1'             # Output directory for data files
    progress_file = 'progress.txt'  # Progress tracking file
    
    print("Starting enhanced batch processing with automatic token rotation...")
    print(f"Number of tokens: {len(tokens)}")
    print(f"Rate limit: 50 calls per hour per token")
    print(f"Maximum islands per hour: {16 * len(tokens)} islands")
    
    # Run batch processing
    try:
        successful, failed = batch_get_data(
            island_csv=island_csv,
            tokens=tokens,
            output_dir=output_dir,
            progress_file=progress_file
        )
        
        print(f"\n=== FINAL RESULTS ===")
        print(f"Successfully processed: {successful} islands")
        print(f"Failed: {len(failed)} islands")
        
        if failed:
            print(f"Failed islands: {failed}")
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Progress has been saved.")
        print("You can resume by running this script again.")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()

