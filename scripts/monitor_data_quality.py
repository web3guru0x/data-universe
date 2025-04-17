#!/usr/bin/env python3

import argparse
import datetime as dt
import json
import requests
import sys
import time
import sqlite3
import os

# Dashboard URL to fetch current network statistics
DASHBOARD_URL = "https://sn13-dashboard.api.macrocosmos.ai/api/data_entity_buckets"

def parse_args():
    parser = argparse.ArgumentParser(description="Monitor data quality and optimize your miner")
    parser.add_argument("--db_path", type=str, required=True,
                        help="Path to the miner's database")
    parser.add_argument("--check_interval", type=int, default=3600, 
                        help="Interval between checks in seconds")
    return parser.parse_args()

def get_network_stats():
    """Fetch data entity bucket stats from the dashboard API"""
    try:
        response = requests.get(DASHBOARD_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching network stats: {e}")
        return None

def get_miner_stats(db_path):
    """Get statistics from local miner database"""
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get total data size
        cursor.execute("SELECT SUM(contentSizeBytes) FROM DataEntity")
        total_size = cursor.fetchone()[0] or 0
        
        # Get data bucket distribution
        cursor.execute("""
            SELECT source, label, timeBucketId, COUNT(*), SUM(contentSizeBytes) 
            FROM DataEntity 
            GROUP BY source, label, timeBucketId
            ORDER BY SUM(contentSizeBytes) DESC
        """)
        buckets = cursor.fetchall()
        
        # Get data age distribution
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN (julianday('now') - julianday(datetime)) < 1 THEN '< 1 day'
                    WHEN (julianday('now') - julianday(datetime)) < 7 THEN '1-7 days'
                    WHEN (julianday('now') - julianday(datetime)) < 14 THEN '7-14 days'
                    WHEN (julianday('now') - julianday(datetime)) < 30 THEN '14-30 days'
                    ELSE '> 30 days'
                END as age,
                COUNT(*), 
                SUM(contentSizeBytes)
            FROM DataEntity
            GROUP BY age
            ORDER BY age
        """)
        age_dist = cursor.fetchall()
        
        conn.close()
        
        return {
            "total_size_bytes": total_size,
            "buckets": buckets,
            "age_distribution": age_dist
        }
    except Exception as e:
        print(f"Error analyzing miner database: {e}")
        return None

def analyze_data(miner_stats, network_stats):
    """Compare miner data with network data and provide recommendations"""
    if not miner_stats or not network_stats:
        return []
    
    recommendations = []
    
    # Check age distribution
    old_data = next((age for age in miner_stats["age_distribution"] if age[0] == '> 30 days'), None)
    if old_data and old_data[2] > 0:
        recommendations.append(f"You have {old_data[1]} items ({old_data[2]} bytes) older than 30 days that aren't scored. Consider clearing them.")
    
    # Find underrepresented high-value buckets
    high_value_buckets = []
    for bucket in network_stats:
        # Look for buckets with high value (desirability > 0.7) but low duplication (miners < 5)
        if bucket.get("desirability", 0) > 0.7 and bucket.get("miner_count", 0) < 5:
            high_value_buckets.append(bucket)
    
    if high_value_buckets:
        recommendations.append("Consider adding these high-value, low-duplication buckets to your scraping config:")
        for bucket in high_value_buckets[:5]:  # Top 5 suggestions
            recommendations.append(f"  - {bucket.get('source', '')} {bucket.get('label', '')}: desirability={bucket.get('desirability', 0)}, miners={bucket.get('miner_count', 0)}")
    
    return recommendations

def main():
    args = parse_args()
    
    print("Data Universe Miner Monitor starting...")
    print(f"Monitoring database at: {args.db_path}")
    print(f"Check interval: {args.check_interval} seconds")
    
    while True:
        print("\n" + "="*50)
        print(f"Check time: {dt.datetime.now()}")
        
        # Get stats
        miner_stats = get_miner_stats(args.db_path)
        network_stats = get_network_stats()
        
        if miner_stats:
            print(f"\nTotal data size: {miner_stats['total_size_bytes'] / (1024*1024):.2f} MB")
            print("\nAge distribution:")
            for age in miner_stats["age_distribution"]:
                print(f"  {age[0]}: {age[1]} items, {age[2] / (1024*1024):.2f} MB")
            
            print("\nTop 5 buckets by size:")
            for i, bucket in enumerate(miner_stats["buckets"][:5]):
                source, label, time_bucket, count, size = bucket
                print(f"  {i+1}. Source: {source}, Label: {label}, Count: {count}, Size: {size / (1024*1024):.2f} MB")
        
        # Analyze and provide recommendations
        recommendations = analyze_data(miner_stats, network_stats)
        if recommendations:
            print("\nRecommendations:")
            for rec in recommendations:
                print(f"  - {rec}")
        
        print("="*50)
        
        # Wait for next check
        time.sleep(args.check_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        sys.exit(0) 