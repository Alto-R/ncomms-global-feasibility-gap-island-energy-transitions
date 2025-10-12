#!/usr/bin/env python3
"""
Enhanced batch processing example with automatic token rotation
Usage: python batch_get.py
"""

from api import batch_get_data

def main():
    # Your API tokens
    tokens = [
        '05db78ba56223547458939d9aa05b698d5981736',
        '5277baa3ae3018a98c002de6b4058abedce313c0',
        '88520669eb6fc900d334b08b39af2a05fee56e2c',
        'b51c33d24ebcae239d3026937b83f02eff8e838f',
        'a90f2e44e1e8fe53064028c6062a7fbbd947a197',
        'ac3317d11a7e256e8831c63e536e0e53682925c6',
        'cdb9b198f70778d44c3816abab634eec26347811',
        'd4db0ae6c4cf4b6928b15d03338c509c3c75bc9f',
        'c2bd9d9c46da7dfe435a1efea84eec189b272539', 
        '0174a776a09af3f79601a9f6b2471cfe977703bc',
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

