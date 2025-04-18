#!/usr/bin/env python3

import os
import sys
import json
import time
import re
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
LOG_DIR_PM2 = os.path.expanduser('~/.pm2/logs')

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

def get_pm2_logs():
    """Obține ultimele log-uri direct din PM2 pentru data-miner."""
    try:
        # Folosim comandă simplă pentru a vedea log-urile recente
        result = subprocess.run(["pm2", "logs", "--lines", "200", "--nostream"], 
                               capture_output=True, text=True, check=True)
        return result.stdout
    except Exception as e:
        print(f"Eroare la obținerea log-urilor PM2: {e}")
        return ""

def scan_log_files():
    """Scanează toate fișierele de log posibile și returnează conținutul lor."""
    log_content = ""
    
    # Verifică toate log-urile din directorul PM2
    if os.path.exists(LOG_DIR_PM2):
        for file in os.listdir(LOG_DIR_PM2):
            if "data-miner" in file and file.endswith(".log"):
                try:
                    with open(os.path.join(LOG_DIR_PM2, file), 'r') as f:
                        log_content += f.read()
                        print(f"Scanat fișier log PM2: {file}")
                except Exception as e:
                    print(f"Eroare la citirea {file}: {e}")
    
    # Verifică și log-ul principal al minerului
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                log_content += f.read()
                print(f"Scanat fișier log principal: {LOG_FILE}")
        except Exception as e:
            print(f"Eroare la citirea log-ului principal: {e}")
            
    # Verifică și log-ul alternativ
    if os.path.exists(LOG_FILE_ALT):
        try:
            with open(LOG_FILE_ALT, 'r') as f:
                log_content += f.read()
                print(f"Scanat fișier log alternativ: {LOG_FILE_ALT}")
        except Exception as e:
            print(f"Eroare la citirea log-ului alternativ: {e}")
            
    return log_content

def extract_pm2_log_commands():
    """Extrage toate comenzile 'pm2 logs' care ar putea arăta log-urile minerului."""
    commands = [
        ["pm2", "logs"],
        ["pm2", "logs", "data-miner", "--lines", "100"],
        ["pm2", "logs", "all", "--lines", "100"],
        ["pm2", "logs", "--raw"]
    ]
    
    log_content = ""
    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout:
                log_content += result.stdout
                print(f"Extras log-uri cu comanda: {' '.join(cmd)}")
        except Exception as e:
            print(f"Eroare la rularea comenzii {' '.join(cmd)}: {e}")
            
    return log_content

def process_log_content(content):
    """Procesează conținutul log-ului și returnează tag-urile găsite."""
    pending_tags = {}
    
    # Caută cereri de bucket în conținut
    bucket_matches = re.finditer(BUCKET_REQUEST_PATTERN, content)
    
    for match in bucket_matches:
        tag = match.group(1)
        
        # Identifică sursa (1=Reddit, 2/7=Twitter)
        source_match = re.search(SOURCE_PATTERN, content[max(0, match.start()-100):match.end()+100])
        if source_match:
            source_id = int(source_match.group(1))
            
            # Adaugă tag-ul la lista de tag-uri în așteptare pentru această sursă
            if source_id not in pending_tags:
                pending_tags[source_id] = []
            
            if tag not in pending_tags[source_id]:
                pending_tags[source_id].append(tag)
                print(f"Tag nou detectat: '{tag}' pentru sursa {source_id}")
    
    return pending_tags

def update_config_with_tags(pending_tags):
    """Actualizează configurația cu tag-urile noi găsite."""
    if not pending_tags:
        return False
        
    # Încarcă configurația curentă
    config = load_config()
    if not config:
        return False
    
    config_changed = False
    
    # Procesează tag-urile în așteptare
    for source_id, tags in pending_tags.items():
        for tag in tags:
            # Adaugă tag-ul în configurație dacă nu există deja
            if add_tag_to_config(config, tag, source_id):
                config_changed = True
    
    # Salvează configurația dacă s-a modificat
    if config_changed:
        if save_config(config):
            print("Configurația a fost actualizată cu tag-uri noi. Se repornește miner-ul.")
            restart_miner()
            return True
    
    return False

def main():
    print(f"Monitorizare automată de tag-uri pornită la {dt.datetime.now()}")
    print(f"Se va actualiza configurația: {CONFIG_FILE}")
    
    # Scanează imediat log-urile existente la pornire
    print("Scanare inițială a tuturor log-urilor disponibile...")
    
    # Combină toate sursele de log-uri posibile
    all_logs = scan_log_files()
    all_logs += get_pm2_logs()
    all_logs += extract_pm2_log_commands()
    
    # Procesează tot conținutul găsit inițial
    if all_logs:
        pending_tags = process_log_content(all_logs)
        if pending_tags:
            print(f"S-au găsit {sum(len(tags) for tags in pending_tags.values())} tag-uri noi în scanarea inițială.")
            update_config_with_tags(pending_tags)
    
    # Monitorizare continuă
    try:
        last_check = time.time()
        
        while True:
            time.sleep(30)  # Verifică la fiecare 30 de secunde
            
            current_time = time.time()
            # Verifică doar la fiecare 2 minute pentru a nu consuma prea multe resurse
            if current_time - last_check > 120:
                print(f"Verificare periodică a log-urilor la {dt.datetime.now()}")
                
                # Scanează din nou toate log-urile
                logs = scan_log_files() + get_pm2_logs()
                
                # Procesează conținutul
                pending_tags = process_log_content(logs)
                if pending_tags:
                    update_config_with_tags(pending_tags)
                
                last_check = current_time
                
    except KeyboardInterrupt:
        print("Oprire monitorizare...")
    
    print("Monitorizare încheiată.")

if __name__ == "__main__":
    main() 