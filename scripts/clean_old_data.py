#!/usr/bin/env python3

import argparse
import sqlite3
import datetime as dt
import sys
import os

def parse_args():
    parser = argparse.ArgumentParser(description="Clean old data from miner database")
    parser.add_argument("--db_path", type=str, required=True,
                        help="Path to the miner's database")
    parser.add_argument("--days", type=int, default=28,
                        help="Delete data older than this many days (default: 28)")
    parser.add_argument("--dry_run", action="store_true",
                        help="Show what would be deleted without actually deleting")
    return parser.parse_args()

def clean_old_data(db_path, days_threshold, dry_run=False):
    """Clean data older than the specified threshold from the database"""
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Calculate the cutoff date
        cutoff_date = dt.datetime.now() - dt.timedelta(days=days_threshold)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
        
        # Check how much data would be deleted
        cursor.execute(
            "SELECT COUNT(*), SUM(contentSizeBytes) FROM DataEntity WHERE datetime < ?", 
            (cutoff_str,)
        )
        count, size = cursor.fetchone()
        
        if count is None or count == 0:
            print(f"No data older than {days_threshold} days found.")
            conn.close()
            return True
        
        size = size or 0
        print(f"Found {count} items ({size / (1024*1024):.2f} MB) older than {days_threshold} days.")
        
        if dry_run:
            print("Dry run: No data deleted.")
        else:
            # Delete old data
            cursor.execute("DELETE FROM DataEntity WHERE datetime < ?", (cutoff_str,))
            conn.commit()
            print(f"Deleted {count} items ({size / (1024*1024):.2f} MB) older than {days_threshold} days.")
        
        # Check database size after deletion
        cursor.execute("SELECT COUNT(*), SUM(contentSizeBytes) FROM DataEntity")
        remaining_count, remaining_size = cursor.fetchone()
        remaining_size = remaining_size or 0
        print(f"Database now contains {remaining_count} items ({remaining_size / (1024*1024):.2f} MB)")
        
        conn.close()
        return True
    except Exception as e:
        print(f"Error cleaning database: {e}")
        return False

def main():
    args = parse_args()
    
    print(f"Database cleaning tool for Data Universe Miner")
    print(f"Database path: {args.db_path}")
    print(f"Threshold: {args.days} days")
    
    if args.dry_run:
        print("Mode: Dry run (no data will be deleted)")
    else:
        print("Mode: Live run (data will be deleted)")
    
    if not clean_old_data(args.db_path, args.days, args.dry_run):
        sys.exit(1)

if __name__ == "__main__":
    main() 