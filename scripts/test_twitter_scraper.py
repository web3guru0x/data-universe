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
    
    # Definește un interval de timp pentru test (ultimele 24 de ore)
    now = dt.datetime.now(dt.timezone.utc)
    yesterday = now - dt.timedelta(hours=24)
    
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
        
        # Creează configurația pentru scraping
        config = ScrapeConfig(
            entity_limit=10,  # Limităm la 10 rezultate pentru test
            date_range=DateRange(
                start=yesterday,
                end=now,
            ),
            labels=[DataLabel(value=hashtag)],
        )
        
        # Execută scraping-ul
        try:
            print(f"Interval de timp: {yesterday.strftime('%Y-%m-%d %H:%M')} până la {now.strftime('%Y-%m-%d %H:%M')}")
            entities = await scraper.scrape(config)
            
            if not entities:
                print(f"Nu s-au găsit entități pentru {hashtag}")
            else:
                print(f"S-au găsit {len(entities)} entități pentru {hashtag}")
                print("\nPrimele 3 entități:")
                for i, entity in enumerate(entities[:3]):
                    print(f"\nEntitatea {i+1}:")
                    print(f"URI: {entity.uri}")
                    print(f"Timestamp: {entity.datetime}")
                    print(f"Mărime: {entity.content_size_bytes} bytes")
                    
                    # Încearcă să decodifice și să afișeze conținutul JSON
                    try:
                        content = json.loads(entity.content)
                        print(f"Text: {content.get('text', 'N/A')[:100]}...")
                        print(f"Hashtag-uri: {content.get('tweet_hashtags', 'N/A')}")
                    except json.JSONDecodeError:
                        print(f"Conținut (primele 100 caractere): {entity.content[:100]}...")
                
                # Salvează un eșantion de entități pentru analiză ulterioară
                with open(f"twitter_{hashtag.replace('#', '')}_sample.json", "w") as f:
                    sample_data = [
                        {
                            "uri": e.uri,
                            "datetime": e.datetime.isoformat(),
                            "content": json.loads(e.content) if isinstance(e.content, str) else e.content,
                            "size_bytes": e.content_size_bytes
                        }
                        for e in entities[:5]  # Salvăm primele 5 entități
                    ]
                    json.dump(sample_data, f, indent=2, default=str)
                print(f"\nS-a salvat un eșantion în twitter_{hashtag.replace('#', '')}_sample.json")
        
        except Exception as e:
            print(f"Eroare la scraping pentru {hashtag}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_twitter_scraper()) 