#!/bin/bash

# Script pentru rularea optimizată a unui miner Data Universe

# Verificăm dacă pm2 este instalat
if ! command -v pm2 &> /dev/null; then
    echo "PM2 nu este instalat. Se instalează..."
    npm install -g pm2
fi

# Găsim comanda Python corectă
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "EROARE: Nu s-a găsit Python. Te rugăm să instalezi Python 3.10 sau mai recent."
    exit 1
fi

echo "Se folosește comanda Python: $PYTHON_CMD"

# Setări configurabile
WALLET_NAME="${1:-cold_wallet}"  # Primul argument sau valoare implicită
WALLET_HOTKEY="${2:-hotkey_wallet}"  # Al doilea argument sau valoare implicită
DB_NAME="optimized_miner.sqlite"
MAX_DB_SIZE_GB=240
SCRAPING_CONFIG="scraping/custom_config.json"
MONITOR_INTERVAL=3600  # 1 oră în secunde

# Calea către directorul de bază (directorul curent)
BASE_DIR="$(pwd)"
DB_PATH="$BASE_DIR/$DB_NAME"

# Funcție pentru a rula un miner în modul offline pentru a construi o bază de date inițială
init_db() {
    echo "Inițializăm baza de date în modul offline..."
    $PYTHON_CMD ./neurons/miner.py --offline \
           --neuron.database_name $DB_NAME \
           --neuron.max_database_size_gb_hint $MAX_DB_SIZE_GB \
           --neuron.scraping_config_file $SCRAPING_CONFIG \
           --logging.debug
}

# Funcție pentru a curăța datele vechi
clean_old_data() {
    echo "Curățăm datele mai vechi de 28 de zile..."
    $PYTHON_CMD ./scripts/clean_old_data.py --db_path $DB_PATH --days 28
}

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

# Verifică dacă baza de date există deja
if [ ! -f "$DB_PATH" ]; then
    # Dacă baza de date nu există, inițializăm în mod offline
    echo "Baza de date nu există. Creăm o bază de date inițială..."
    init_db
    
    # Așteptăm să obținem niște date înainte de a porni în mod online
    echo "Așteptăm 15 minute pentru a obține date inițiale..."
    sleep 900  # 15 minute în secunde
else
    # Dacă baza de date există, curățăm datele vechi
    clean_old_data
fi

# Oprim orice instanță anterioară a minerului și monitorului
pm2 stop data-miner 2>/dev/null
pm2 stop data-monitor 2>/dev/null
pm2 delete data-miner 2>/dev/null
pm2 delete data-monitor 2>/dev/null

# Pornim minerul și monitorizarea
start_miner
start_monitoring

echo "Minerul Data Universe a fost pornit optimizat!"
echo "Pentru a vedea logurile minerului: pm2 logs data-miner"
echo "Pentru a vedea monitorizarea: pm2 logs data-monitor"

# Programăm curățarea automată a datelor vechi la fiecare 24h
(crontab -l 2>/dev/null; echo "0 0 * * * cd $BASE_DIR && $PYTHON_CMD ./scripts/clean_old_data.py --db_path $DB_PATH --days 28") | crontab -

echo "Curățarea automată a datelor vechi a fost configurată la 00:00 în fiecare zi" 