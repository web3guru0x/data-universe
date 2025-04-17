# Ghid de Optimizare pentru Mineri Data Universe

Acest ghid te va ajuta să optimizezi miner-ul tău de pe subnet-ul Data Universe pentru a maximiza scorul și recompensele.

## Factori care influențează scorul

Validatorii evaluează minerii pe baza a 2 dimensiuni principale:

1. **Valoarea datelor stocate**:
   - Prospețimea datelor (mai noi = mai valoroase)
   - Dezirabilitatea datelor (conform listei dinamice de dezirabilitate)
   - Factorul de duplicare (date unice = mai valoroase)

2. **Credibilitatea minerului**:
   - Bazată pe verificările aleatorii ale datelor
   - Are un impact exponențial asupra scorului: `score_final = score_brut * (credibilitate ^ 2.5)`

## Strategii de Optimizare

### 1. Optimizarea Configurației Scraper-ului

Fișierul `scraping/custom_config.json` inclus în acest repository este configurat pentru a colecta date cu valoare ridicată și nivel scăzut de duplicare. Strategiile utilizate includ:

- Concentrarea pe subiectele cu factor de scalare ridicat (#bittensor, r/Bittensor_)
- Scraping mai frecvent (la fiecare 2-3 minute) pentru date proaspete
- Limitarea cantității de date per tip pentru a asigura diversitatea
- Prioritizarea datelor noi (max_age_hint_minutes setat sub pragul de 30 zile)

Pentru a personaliza și mai mult:
```bash
# Verifică dashboard-ul pentru a identifica date cu valoare ridicată și nivel scăzut de duplicare
xdg-open https://sn13-dashboard.api.macrocosmos.ai/
```

### 2. Menținerea Prospețimii Datelor

Script-ul `clean_old_data.py` șterge automat datele mai vechi de pragul specificat (implicit 28 zile). Acesta:
- Previne umplerea bazei de date cu date vechi fără valoare
- Eliberează spațiu pentru date noi, mai valoroase
- Rulează automat la ora 00:00 în fiecare zi când folosești script-ul `run_optimized_miner.sh`

### 3. Monitorizarea Performanței

Script-ul `monitor_data_quality.py` îți oferă informații valoroase despre:
- Distribuția datelor tale după vârstă
- Cele mai mari "buckets" de date
- Recomandări pentru îmbunătățirea valorii datelor

### 4. Maximizarea Credibilității

Credibilitatea este factorul cu cel mai mare impact asupra scorului final. Pentru a o maximiza:
- Asigură-te că toate datele raportate sunt disponibile când sunt solicitate
- Menține miner-ul online și disponibil 24/7
- Utilizează hardware fiabil cu conexiune la internet stabilă
- Asigură-te că datele sunt scrape-uite corect și sunt valide

## Configurarea Hardware-ului

### Cerințe Minime:
- CPU: 4+ nuclee
- RAM: 8GB
- Stocare: Minim 500GB SSD
- Conexiune la internet: 100Mbps+, stabilă

### Cerințe Recomandate:
- CPU: 8+ nuclee
- RAM: 16GB
- Stocare: 1TB+ SSD NVMe
- Conexiune la internet: 500Mbps+, stabilă, cu IP static

## Rularea Optimizată

Pentru a rula miner-ul optimizat:

```bash
# Acordă permisiuni de execuție script-ului
chmod +x scripts/run_optimized_miner.sh

# Rulează miner-ul cu wallet-ul și hotkey-ul tău
./scripts/run_optimized_miner.sh your_wallet your_hotkey
```

## Verificarea Performanței

```bash
# Verifică logurile miner-ului
pm2 logs data-miner

# Verifică logurile monitorului
pm2 logs data-monitor

# Verifică scorul pe rețea
xdg-open https://taostats.io/subnets/netuid-13/
```

## Actualizări și Întreținere

Recomandăm actualizarea regulată a configurației scraper-ului bazată pe:
1. Feedback-ul din monitor-ul de date
2. Schimbări în lista de dezirabilitate
3. Tendințe ale datelor din dashboard-ul Data Universe

Bucură-te de mining profitabil în Data Universe! 