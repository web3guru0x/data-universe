#!/usr/bin/env python3

import os
import json
import sys
import asyncio
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Adaugă directorului rădăcină în PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from apify_client import ApifyClientAsync

async def check_apify_actors():
    load_dotenv()
    
    # Verifică dacă există token Apify
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        print("ERROR: Nu s-a găsit APIFY_API_TOKEN în variabilele de mediu sau fișierul .env")
        return

    print(f"Folosesc Apify token: {token[:5]}...{token[-5:]}")
    
    # Inițializează clientul Apify
    client = ApifyClientAsync(token=token)
    
    # Lista actorilor de verificat
    actor_ids = [
        "61RPP7dywgiy0JPD0",  # ApiDojo Twitter Scraper
        "heLL6fUofdPgRXZie"   # Microworlds Twitter Scraper
    ]
    
    print("\n=== VERIFICARE ACTORI APIFY ===\n")
    
    for actor_id in actor_ids:
        try:
            # Obține informații despre actor
            actor_info = await client.actor(actor_id).get()
            print(f"Actor: {actor_info.get('name', 'Fără nume')}")
            print(f"  ID: {actor_id}")
            print(f"  Versiune: {actor_info.get('version', {}).get('versionNumber', 'Necunoscută')}")
            print(f"  Status: {actor_info.get('isPublic', False) and 'Public' or 'Privat'}")
            print(f"  Disponibil: {not actor_info.get('isDeprecated', False) and 'Da' or 'Nu (Deprecated)'}")
            
            # Obține executări recente
            runs = await client.actor(actor_id).runs().list(desc=True, limit=3)
            if runs.get('items', []):
                print("  Rulări recente:")
                for run in runs['items']:
                    status = run.get('status')
                    date = datetime.fromisoformat(run.get('startedAt').replace('Z', '+00:00')) if 'startedAt' in run else None
                    date_str = date.strftime("%Y-%m-%d %H:%M:%S") if date else "Necunoscută"
                    print(f"    - {date_str}: {status}")
            else:
                print("  Nu există rulări recente")
            
            # Testează actorul cu o interogare simplă
            print("\n  Testăm actorul cu o interogare de test...")
            
            if "Twitter" in actor_info.get('name', ''):
                test_input = {
                    "searchTerms": ["#news"],
                    "maxTweets": 5,
                    "maxRequestRetries": 2
                }
            else:
                test_input = {}  # Input gol pentru alți actori
            
            # Rulează actorul cu o interogare de test
            run = await client.actor(actor_id).call(run_input=test_input, timeout_secs=60)
            
            # Obținem rezultatele
            items = [i async for i in client.dataset(run["defaultDatasetId"]).iterate_items()] 
            
            if items:
                print(f"  ✅ Actorul a returnat {len(items)} rezultate în modul de test")
                print(f"  Primul rezultat: {json.dumps(items[0], indent=2)[:200]}...")
            else:
                print("  ⚠️ Actorul nu a returnat rezultate în modul de test")
        
        except Exception as e:
            print(f"  ❌ Eroare la verificarea actorului {actor_id}: {str(e)}")
        
        print("\n" + "-" * 50 + "\n")
    
    # Verifică limitele de credit
    try:
        user = await client.user().get()
        if 'proxy' in user and 'usage' in user['proxy']:
            proxy_usage = user['proxy']['usage']
            proxy_limit = user['proxy'].get('monthlyUsageLimit', 0)
            print(f"Utilizare proxy pentru luna curentă: {proxy_usage}/{proxy_limit}")
        
        subscription = user.get('subscription', {})
        print(f"Plan Apify: {subscription.get('plan', 'Necunoscut')}")
        
        if 'nextBillingAt' in subscription:
            next_billing = datetime.fromisoformat(subscription['nextBillingAt'].replace('Z', '+00:00'))
            print(f"Următoarea facturare: {next_billing.strftime('%Y-%m-%d')}")
    except Exception as e:
        print(f"Eroare la obținerea informațiilor despre utilizator: {str(e)}")

if __name__ == "__main__":
    asyncio.run(check_apify_actors()) 