#!/usr/bin/env python3

import argparse
import sqlite3
import datetime as dt
import json
import os
import sys

def parse_args():
    parser = argparse.ArgumentParser(description="Afișează datele colectate de minerul Data Universe")
    parser.add_argument("--db_path", type=str, required=True,
                        help="Calea către baza de date a minerului")
    parser.add_argument("--limit", type=int, default=10,
                        help="Numărul maxim de entități de afișat")
    parser.add_argument("--source", type=str, choices=['all', 'reddit', 'twitter'],
                        default='all', help="Sursa pentru care să afișezi datele")
    parser.add_argument("--show_content", action="store_true",
                        help="Afișează conținutul datelor (poate fi foarte mare)")
    return parser.parse_args()

def get_source_number(source_name):
    if source_name == 'reddit':
        return 1  # Reddit
    elif source_name == 'twitter':
        return 7  # Twitter/X
    return None

def show_database_stats(db_path):
    """Afișează statistici generale despre baza de date"""
    if not os.path.exists(db_path):
        print(f"Eroare: Baza de date nu a fost găsită la {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Total entități
        cursor.execute("SELECT COUNT(*) FROM DataEntity")
        total_entities = cursor.fetchone()[0]
        
        # Mărime totală
        cursor.execute("SELECT SUM(contentSizeBytes) FROM DataEntity")
        total_size = cursor.fetchone()[0] or 0
        
        # Distribuție pe surse
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN source = 1 THEN 'Reddit'
                    WHEN source = 7 THEN 'Twitter/X'
                    ELSE 'Altă sursă'
                END as source_name,
                COUNT(*), 
                SUM(contentSizeBytes)
            FROM DataEntity 
            GROUP BY source
        """)
        sources = cursor.fetchall()
        
        # Vârsta datelor
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN (julianday('now') - julianday(datetime)) < 1 THEN '< 1 zi'
                    WHEN (julianday('now') - julianday(datetime)) < 7 THEN '1-7 zile'
                    WHEN (julianday('now') - julianday(datetime)) < 14 THEN '7-14 zile'
                    WHEN (julianday('now') - julianday(datetime)) < 30 THEN '14-30 zile'
                    ELSE '> 30 zile'
                END as age,
                COUNT(*), 
                SUM(contentSizeBytes)
            FROM DataEntity
            GROUP BY age
        """)
        age_dist = cursor.fetchall()
        
        print("\n" + "=" * 50)
        print(f"STATISTICI BAZĂ DE DATE: {db_path}")
        print("=" * 50)
        print(f"Total entități: {total_entities}")
        print(f"Mărime totală: {total_size / (1024*1024):.2f} MB")
        
        print("\nDistribuție pe surse:")
        for source in sources:
            print(f"  {source[0]}: {source[1]} entități, {source[2] / (1024*1024):.2f} MB")
        
        print("\nDistribuție pe vârstă:")
        for age in age_dist:
            print(f"  {age[0]}: {age[1]} entități, {age[2] / (1024*1024):.2f} MB")
        
        conn.close()
        return True
    except Exception as e:
        print(f"Eroare la citirea bazei de date: {e}")
        return False

def show_entities(db_path, limit=10, source='all', show_content=False):
    """Afișează entitățile din baza de date"""
    if not os.path.exists(db_path):
        print(f"Eroare: Baza de date nu a fost găsită la {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Construiește interogarea în funcție de sursă
        query = "SELECT uri, datetime, source, label, content, contentSizeBytes FROM DataEntity"
        params = []
        
        if source != 'all':
            source_num = get_source_number(source)
            if source_num is not None:
                query += " WHERE source = ?"
                params.append(source_num)
        
        query += " ORDER BY datetime DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        entities = cursor.fetchall()
        
        print("\n" + "=" * 50)
        print(f"ULTIMELE {limit} ENTITĂȚI{' DIN ' + source.upper() if source != 'all' else ''}")
        print("=" * 50)
        
        for entity in entities:
            uri, dt_str, source_num, label, content, size = entity
            source_name = "Reddit" if source_num == 1 else "Twitter/X" if source_num == 7 else f"Altă sursă ({source_num})"
            
            print(f"\nURI: {uri}")
            print(f"Data: {dt_str}")
            print(f"Sursă: {source_name}")
            print(f"Etichetă: {label}")
            print(f"Mărime: {size / 1024:.2f} KB")
            
            if show_content:
                try:
                    # Încercăm să parsăm conținutul ca JSON (majoritatea datelor sunt stocate ca JSON)
                    content_json = json.loads(content)
                    print(f"Conținut: {json.dumps(content_json, indent=2, ensure_ascii=False)[:500]}...")
                except:
                    # Dacă nu e JSON, afișăm ca text
                    print(f"Conținut: {str(content)[:500]}...")
            
            print("-" * 30)
        
        conn.close()
        return True
    except Exception as e:
        print(f"Eroare la citirea bazei de date: {e}")
        return False

def main():
    args = parse_args()
    
    # Afișează statistici generale
    if not show_database_stats(args.db_path):
        sys.exit(1)
    
    # Afișează cele mai recente entități
    if not show_entities(args.db_path, args.limit, args.source, args.show_content):
        sys.exit(1)

if __name__ == "__main__":
    main() 