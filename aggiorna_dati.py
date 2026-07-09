def scrape_prezzo_reale_web(barcode):
    """
    Usa DuckDuckGo HTML (Lite) che non ha blocchi CAPTCHA per i server,
    estrarre i prezzi reali dai siti di spesa italiani.
    """
    if not barcode or len(str(barcode)) < 8:
        return None
        
    # DuckDuckGo in versione light senza JS e senza blocchi aggressivi
    url = f"https://lite.duckduckgo.com/lite/"
    data = {"q": f"prezzo {barcode} esselunga conad coop"}
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        time.sleep(random.uniform(1.5, 3.0))
        res = requests.post(url, data=data, headers=headers, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            testo_completo = soup.get_text()
            
            # Cerca i pattern dei prezzi in euro (es. 1,49 o 8,90)
            prezzi_trovati = re.findall(r'(\d+,\d{2})\s*€|€\s*(\d+,\d{2})', testo_completo)
            validi = []
            for p in prezzi_trovati:
                pulito = p[0] if p[0] else p[1]
                val_float = float(pulito.replace(',', '.'))
                if 0.30 < val_float < 40.0: # Escludiamo micro-prezzi o errori di lettura
                    validi.append(val_float)
            
            if validi:
                # Prendiamo il prezzo mediano o il primo trovato per stabilità
                return round(validi[0], 2)
    except Exception as e:
        print(f"Errore ricerca DuckDuckGo per {barcode}: {e}")
    return None
    
