#!/usr/bin/env python3

import asyncio
import os
import sys
import json
import datetime as dt
from dotenv import load_dotenv

# Adaugă calea root a proiectului la PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scraping.apify import ActorRunner, RunConfig
from scraping.x.apidojo_scraper import ApiDojoTwitterScraper
from common.date_range import DateRange
from common.data import DataLabel
from scraping.scraper import ScrapeConfig

async def test_twitter_scraper():
    # Încarcă variabilele de mediu din .env
    load_dotenv()
    
    # Verifică dacă cheia Apify există
    apify_token = os.getenv("APIFY_API_TOKEN")
    if not apify_token:
        print("Eroare: Nu s-a găsit APIFY_API_TOKEN în variabilele de mediu sau fișierul .env")
        return

    print(f"Folosesc cheia Apify: {apify_token[:5]}...{apify_token[-5:]}")

    # Creează un scraper Twitter
    scraper = ApiDojoTwitterScraper()
    
    # Nu mai folosim interval de timp, căutăm direct hashtag-urile
    
    # Lista de hashtag-uri de testat - inclusiv cele populare din trending
    hashtags = [
        "#SOONISTHEREDPILL", 
        "#BoogaHeights", 
        "#Esaret",
        "#Balochistan",
        "#crypto", 
        "#bitcoin", 
        "#Gold",
        "#Arsenal",
        "#Russia",
        "#NATO",
        "#Trump"
    ]
    
    for hashtag in hashtags:
        print(f"\n--- Testez scraping pentru {hashtag} ---")
        
        # Modificăm configurația pentru a căuta direct hash-tag-uri fără filtrare după dată
        run_input = {
            "searchTerms": [hashtag],
            "maxTweets": 10,
            "maxRequestRetries": 5
        }
        
        # Configurați scraperul manual
        run_config = RunConfig(
            actor_id="61RPP7dywgiy0JPD0", # ApiDojo Twitter Scraper actor ID
            debug_info=f"Test direct {hashtag}",
            max_data_entities=10,
            timeout_secs=120,
        )
        
        # Inițializați runner-ul
        runner = ActorRunner()
        
        try:
            print(f"Căutare directă pentru: {hashtag}")
            # Rulează actorul direct pentru a obține rezultate
            dataset = await runner.run(run_config, run_input)
            
            if not dataset:
                print(f"Nu s-au găsit rezultate pentru {hashtag}")
            else:
                print(f"S-au găsit {len(dataset)} rezultate pentru {hashtag}")
                print("\nPrimele 3 rezultate:")
                
                for i, item in enumerate(dataset[:3]):
                    print(f"\nRezultatul {i+1}:")
                    if "url" in item:
                        print(f"URL: {item['url']}")
                    if "createdAt" in item:
                        print(f"Data creării: {item['createdAt']}")
                    if "text" in item:
                        print(f"Text: {item['text'][:100]}...")
                    
                    if "entities" in item and "hashtags" in item["entities"]:
                        hashtags_list = [f"#{tag['text']}" for tag in item["entities"]["hashtags"]]
                        print(f"Hashtag-uri: {hashtags_list}")
                
                # Salvează rezultatele brute pentru analiză
                with open(f"twitter_{hashtag.replace('#', '')}_raw.json", "w") as f:
                    json.dump(dataset[:5], f, indent=2)
                print(f"\nS-au salvat rezultatele brute în twitter_{hashtag.replace('#', '')}_raw.json")
        
        except Exception as e:
            print(f"Eroare la scraping direct pentru {hashtag}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_twitter_scraper()) 