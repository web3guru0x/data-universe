#!/bin/bash

# Script pentru rularea optimizată a unui miner Data Universe

# Verificăm dacă pm2 este instalat
if ! command -v pm2 &> /dev/null; then
    echo "PM2 nu este instalat. Se instalează..."
    npm install -g pm2
fi

# Calea către directorul de bază (directorul curent)
BASE_DIR="$(pwd)"

# Verifică dacă există mediul virtual, dacă nu, îl creează
if [ ! -d "$BASE_DIR/bittensor_env" ]; then
    echo "Creez mediul virtual Python..."
    python3 -m venv bittensor_env
    echo "Instalez dependințele în mediul virtual..."
    source bittensor_env/bin/activate
    
    # Instalăm dependențele necesare
    pip install -e . --no-deps
    pip install torch pandas numpy bittensor wandb fastapi pydantic
    pip install sqlitedict requests pytest pytest-asyncio asyncio
    
    deactivate
fi

# Setăm calea Python către mediul virtual
PYTHON_CMD="$BASE_DIR/bittensor_env/bin/python"

echo "Se folosește Python din mediul virtual: $PYTHON_CMD"

# Setări configurabile
WALLET_NAME="${1:-cold_wallet}"  # Primul argument sau valoare implicită
WALLET_HOTKEY="${2:-hotkey_wallet}"  # Al doilea argument sau valoare implicită
DB_NAME="optimized_miner.sqlite"
MAX_DB_SIZE_GB=240
SCRAPING_CONFIG="scraping/custom_config.json"
MONITOR_INTERVAL=3600  # 1 oră în secunde

DB_PATH="$BASE_DIR/$DB_NAME"

# Verifică dacă fișierul de configurare există
if [ ! -f "$BASE_DIR/$SCRAPING_CONFIG" ]; then
    echo "Creez directorul și fișierul de configurare pentru scraping..."
    mkdir -p $(dirname "$BASE_DIR/$SCRAPING_CONFIG")
    cat > "$BASE_DIR/$SCRAPING_CONFIG" <<EOL
{
    "scraper_configs": [
        {
            "scraper_id": "X.apidojo",
            "cadence_seconds": 180,
            "labels_to_scrape": [
                {
                    "label_choices": [
                        "#bittensor",
                        "#tao",
                        "#decentralizedfinance",
                        "#bitcointechnology"
                    ],
                    "max_age_hint_minutes": 720,
                    "max_data_entities": 100
                },
                {
                    "label_choices": [
                        "#bitcoinmining",
                        "#bitcoinnews"
                    ],
                    "max_age_hint_minutes": 1080,
                    "max_data_entities": 50
                }
            ]
        },
        {
            "scraper_id": "Reddit.custom",
            "cadence_seconds": 120,
            "labels_to_scrape": [
                {
                    "label_choices": [
                        "r/Bittensor_",
                        "r/Polkadot"
                    ],
                    "max_age_hint_minutes": 720,
                    "max_data_entities": 80
                },
                {
                    "label_choices": [
                        "r/Cryptocurrency",
                        "r/Cryptomarkets",
                        "r/EthereumClassic"
                    ],
                    "max_age_hint_minutes": 720,
                    "max_data_entities": 70
                }
            ]
        }
    ]
}
EOL
    echo "Fișier de configurare creat: $SCRAPING_CONFIG"
fi

# Verifică dacă scripturile de monitorizare există
if [ ! -f "$BASE_DIR/scripts/clean_old_data.py" ] || [ ! -f "$BASE_DIR/scripts/monitor_data_quality.py" ]; then
    echo "Scripturile de monitorizare nu există. Le vom crea..."
    
    mkdir -p "$BASE_DIR/scripts"
    
    # Creăm scriptul clean_old_data.py
    cat > "$BASE_DIR/scripts/clean_old_data.py" <<EOL
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
EOL

    # Creăm scriptul monitor_data_quality.py
    cat > "$BASE_DIR/scripts/monitor_data_quality.py" <<EOL
#!/usr/bin/env python3

import argparse
import datetime as dt
import json
import sys
import time
import sqlite3
import os

def parse_args():
    parser = argparse.ArgumentParser(description="Monitor data quality and optimize your miner")
    parser.add_argument("--db_path", type=str, required=True,
                        help="Path to the miner's database")
    parser.add_argument("--check_interval", type=int, default=3600, 
                        help="Interval between checks in seconds")
    return parser.parse_args()

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
        
        if miner_stats:
            print(f"\nTotal data size: {miner_stats['total_size_bytes'] / (1024*1024):.2f} MB")
            print("\nAge distribution:")
            for age in miner_stats["age_distribution"]:
                print(f"  {age[0]}: {age[1]} items, {age[2] / (1024*1024):.2f} MB")
            
            print("\nTop 5 buckets by size:")
            for i, bucket in enumerate(miner_stats["buckets"][:5]):
                source, label, time_bucket, count, size = bucket
                print(f"  {i+1}. Source: {source}, Label: {label}, Count: {count}, Size: {size / (1024*1024):.2f} MB")
        
        print("="*50)
        
        # Wait for next check
        time.sleep(args.check_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        sys.exit(0)
EOL

    # Facem scripturile executabile
    chmod +x "$BASE_DIR/scripts/clean_old_data.py"
    chmod +x "$BASE_DIR/scripts/monitor_data_quality.py"
    
    echo "Scripturile de monitorizare au fost create."
fi

# Funcție pentru a porni monitorizarea
start_monitoring() {
    echo "Pornirea monitorizării minerului..."
    pm2 start $PYTHON_CMD --name data-monitor -- ./scripts/monitor_data_quality.py --db_path $DB_PATH --check_interval $MONITOR_INTERVAL
}

# Funcție pentru a porni minerul în mod online
start_miner() {
    echo "Pornire miner în modul online..."
    pm2 start $PYTHON_CMD --name data-miner -- ./neurons/miner.py \
            --wallet.name $WALLET_NAME \
            --wallet.hotkey $WALLET_HOTKEY \
            --neuron.database_name $DB_NAME \
            --neuron.max_database_size_gb_hint $MAX_DB_SIZE_GB \
            --neuron.scraping_config_file $SCRAPING_CONFIG \
            --logging.debug
}

# Oprim orice instanță anterioară a minerului și monitorului
pm2 stop data-miner 2>/dev/null
pm2 stop data-monitor 2>/dev/null
pm2 delete data-miner 2>/dev/null
pm2 delete data-monitor 2>/dev/null

# Pornim minerul și monitorizarea direct în modul online
echo "Pornire miner '$WALLET_HOTKEY' din wallet '$WALLET_NAME'..."
start_miner
start_monitoring

echo "Minerul Data Universe a fost pornit optimizat!"
echo "Pentru a vedea logurile minerului: pm2 logs data-miner"
echo "Pentru a vedea monitorizarea: pm2 logs data-monitor"

# Programăm curățarea automată a datelor vechi la fiecare 24h
(crontab -l 2>/dev/null; echo "0 0 * * * cd $BASE_DIR && $PYTHON_CMD ./scripts/clean_old_data.py --db_path $DB_PATH --days 28") | crontab -

echo "Curățarea automată a datelor vechi a fost configurată la 00:00 în fiecare zi" 