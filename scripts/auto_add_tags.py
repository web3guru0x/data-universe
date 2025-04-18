#!/usr/bin/env python3

import os
import sys
import json
import time
import re
import asyncio
import subprocess
import datetime as dt
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Adaugă directorul principal la calea Python
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(script_dir, '..')))

# Calea către fișierul de log al minerului
LOG_FILE = os.path.expanduser('~/.bittensor/miners/default/miner1/netuid13/None/events.log')
LOG_FILE_ALT = os.path.expanduser('~/.pm2/logs/data-miner-out.log')

# Calea către fișierul de configurare
CONFIG_FILE = os.path.join(script_dir, '..', 'scraping', 'custom_config.json')

# Expresii regulate pentru a captura cererile de date
BUCKET_REQUEST_PATTERN = r"Got to a GetDataEntityBucket request .* label=DataLabel\(value='([^']+)'\)"
SOURCE_PATTERN = r"source=(\d+)"

# Mapare surse numerice la ID-uri scraper
SOURCE_TO_SCRAPER = {
    1: "Reddit.custom",  # Reddit
    2: "X.apidojo",      # Twitter/X
    7: "X.apidojo"       # Twitter/X (uneori apare și ca 7)
}

def load_config():
    """Încarcă fișierul de configurare curent."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Eroare la încărcarea configurației: {e}")
        return None

def save_config(config):
    """Salvează configurația actualizată."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Configurație salvată cu succes la {dt.datetime.now()}")
        return True
    except Exception as e:
        print(f"Eroare la salvarea configurației: {e}")
        return False

def get_scraper_config(config, source_id):
    """Obține configurația pentru un anumit scraper din ID-ul sursei."""
    scraper_id = SOURCE_TO_SCRAPER.get(source_id)
    if not scraper_id:
        return None
    
    for scraper_config in config.get("scraper_configs", []):
        if scraper_config.get("scraper_id") == scraper_id:
            return scraper_config
    
    return None

def add_tag_to_config(config, tag, source_id):
    """Adaugă un tag nou în configurație pentru sursa specificată."""
    scraper_config = get_scraper_config(config, source_id)
    if not scraper_config:
        print(f"Nu s-a găsit configurație pentru sursa {source_id}")
        return False
    
    # Verifică dacă tag-ul este deja în configurație
    for label_group in scraper_config.get("labels_to_scrape", []):
        label_choices = label_group.get("label_choices", [])
        if tag in label_choices:
            print(f"Tag-ul '{tag}' există deja în configurație")
            return False
    
    # Determinăm în care grup să adăugăm tag-ul
    # Preferăm primul grup dacă are mai puține tag-uri
    if len(scraper_config.get("labels_to_scrape", [])) > 0:
        target_group = scraper_config["labels_to_scrape"][0]
        
        # Dacă avem un al doilea grup și are mai puține tag-uri, folosim al doilea grup
        if len(scraper_config["labels_to_scrape"]) > 1:
            if len(scraper_config["labels_to_scrape"][0]["label_choices"]) > len(scraper_config["labels_to_scrape"][1]["label_choices"]):
                target_group = scraper_config["labels_to_scrape"][1]
        
        # Adaugă tag-ul în grupul țintă
        target_group["label_choices"].append(tag)
        print(f"Tag-ul '{tag}' a fost adăugat în configurație pentru {SOURCE_TO_SCRAPER.get(source_id)}")
        return True
    
    return False

def restart_miner():
    """Repornește miner-ul pentru a aplica noua configurație."""
    try:
        print("Se repornește miner-ul...")
        subprocess.run(["pm2", "restart", "data-miner"], check=True)
        print("Miner-ul a fost repornit cu succes!")
        return True
    except Exception as e:
        print(f"Eroare la repornirea miner-ului: {e}")
        return False

class LogHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_position = 0
        self.config = load_config()
        self.last_config_update = 0
        self.pending_tags = {}  # {source_id: [tag1, tag2, ...]}
        
        # Inițializează poziția inițială a fișierului de log
        try:
            if os.path.exists(LOG_FILE):
                self.log_file = LOG_FILE
                self.last_position = os.path.getsize(LOG_FILE)
            elif os.path.exists(LOG_FILE_ALT):
                self.log_file = LOG_FILE_ALT
                self.last_position = os.path.getsize(LOG_FILE_ALT)
            else:
                print(f"Nu s-a găsit niciun fișier de log. Se așteaptă crearea.")
                self.log_file = LOG_FILE
        except Exception as e:
            print(f"Eroare la inițializarea poziției fișierului de log: {e}")
            self.log_file = LOG_FILE
    
    def on_modified(self, event):
        if not os.path.exists(self.log_file):
            # Verifică fișierul alternativ dacă cel principal nu există
            if os.path.exists(LOG_FILE_ALT) and self.log_file != LOG_FILE_ALT:
                self.log_file = LOG_FILE_ALT
                self.last_position = 0
            else:
                return
        
        if event.src_path == self.log_file:
            self.process_log()
    
    def process_log(self):
        try:
            with open(self.log_file, 'r') as f:
                f.seek(self.last_position)
                new_content = f.read()
                self.last_position = f.tell()
            
            self.process_log_content(new_content)
            
        except Exception as e:
            print(f"Eroare la procesarea log-ului: {e}")
    
    def process_log_content(self, content):
        # Caută cereri de bucket în conținut
        bucket_matches = re.finditer(BUCKET_REQUEST_PATTERN, content)
        
        for match in bucket_matches:
            tag = match.group(1)
            
            # Identifică sursa (1=Reddit, 2/7=Twitter)
            source_match = re.search(SOURCE_PATTERN, content[max(0, match.start()-100):match.end()+100])
            if source_match:
                source_id = int(source_match.group(1))
                
                # Adaugă tag-ul la lista de tag-uri în așteptare pentru această sursă
                if source_id not in self.pending_tags:
                    self.pending_tags[source_id] = []
                
                if tag not in self.pending_tags[source_id]:
                    self.pending_tags[source_id].append(tag)
                    print(f"Tag nou detectat: '{tag}' pentru sursa {source_id}")
        
        # Verifică dacă avem tag-uri în așteptare și dacă a trecut suficient timp de la ultima actualizare
        current_time = time.time()
        if self.pending_tags and (current_time - self.last_config_update > 60):  # 60 secunde între actualizări
            self.update_config()
    
    def update_config(self):
        # Reîncarcă configurația pentru a avea cea mai recentă versiune
        self.config = load_config()
        if not self.config:
            return
        
        config_changed = False
        
        # Procesează tag-urile în așteptare
        for source_id, tags in self.pending_tags.items():
            for tag in tags:
                # Adaugă tag-ul în configurație dacă nu există deja
                if add_tag_to_config(self.config, tag, source_id):
                    config_changed = True
        
        # Salvează configurația dacă s-a modificat
        if config_changed:
            if save_config(self.config):
                self.last_config_update = time.time()
                print("Configurația a fost actualizată cu tag-uri noi. Se repornește miner-ul.")
                restart_miner()
        
        # Resetează tag-urile în așteptare
        self.pending_tags = {}

def main():
    print(f"Monitorizare automată de tag-uri pornită la {dt.datetime.now()}")
    print(f"Se monitorizează fișierul de log: {LOG_FILE}")
    print(f"Se va actualiza configurația: {CONFIG_FILE}")
    
    event_handler = LogHandler()
    observer = Observer()
    
    # Verifică log-urile existente la pornire
    if os.path.exists(LOG_FILE):
        observer.schedule(event_handler, path=os.path.dirname(LOG_FILE), recursive=False)
        event_handler.log_file = LOG_FILE
        # Procesează log-ul existent pentru a găsi tag-uri recente
        event_handler.process_log()
    elif os.path.exists(LOG_FILE_ALT):
        observer.schedule(event_handler, path=os.path.dirname(LOG_FILE_ALT), recursive=False)
        event_handler.log_file = LOG_FILE_ALT
        # Procesează log-ul existent pentru a găsi tag-uri recente
        event_handler.process_log()
    else:
        print("Nu s-a găsit niciun fișier de log. Se așteaptă crearea.")
        # Încearcă să observi directorul pentru ambele fișiere log
        if os.path.exists(os.path.dirname(LOG_FILE)):
            observer.schedule(event_handler, path=os.path.dirname(LOG_FILE), recursive=False)
        if os.path.exists(os.path.dirname(LOG_FILE_ALT)):
            observer.schedule(event_handler, path=os.path.dirname(LOG_FILE_ALT), recursive=False)
    
    observer.start()
    
    try:
        while True:
            time.sleep(5)
            # Actualizează imediat tag-urile așteptate dacă există
            if event_handler.pending_tags and (time.time() - event_handler.last_config_update > 60):
                event_handler.update_config()
    except KeyboardInterrupt:
        print("Oprire monitorizare...")
        observer.stop()
    
    observer.join()

if __name__ == "__main__":
    main() 