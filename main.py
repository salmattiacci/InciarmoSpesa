import streamlit as st
import requests
import re
import json
from urllib.parse import quote

st.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")

def pulisci_bollino(testo):
    if not testo: return ""
    testo_str = str(testo).upper().strip()
    match = re.search(r'(IT\s*\d+[\s*\/]*\d*\s*CE|\d+[\s*\/]*\d*\s*CE)', testo_str)
    if match:
        return re.sub(r'\s+', '', match.group(1))
    return re.sub(r'[^A-Z0-9]', '', testo_str)[:10]

def cerca_prezzo_unificato(nome_prodotto, barcode, cap="20121"):
    """
    Usa un proxy di sblocco per aggirare i firewall di Everli ed estrarre il prezzo reale.
    """
    query_pulita = quote(str(nome_prodotto).split(",")[0])
    target_url = f"https://www.everli.com/api/v2/search?q={query_pulita}&zipcode={cap}"
    proxy_url = f"https://api.allorigins.win/get?url={quote(target_url)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(proxy_url, headers=headers, timeout=6)
        if response.status_code == 200:
            proxy_data = response.json()
            contents = proxy_data.get("contents")
            
            if contents:
                data = json.loads(contents)
                products = data.get("products", [])
                if products:
                    primo_prodotto = products[0]
                    prezzo = primo_prodotto.get("price")
                    store = primo_prodotto.get("store_name", "Supermercato")
                    if prezzo:
                        return f"{prezzo} € ({store})"
                        
        # PIANO B: Se il proxy o Everli falliscono, proviamo il database aperto OFF
        url_off = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        res_off = requests.get(url_off, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
        if res_off.status_code == 200:
            product_data = res_off.json().get("product", {})
            prezzo_stimato = product_data.get("price")
            if prezzo_stimato:
                return f"{prezzo_stimato} € (Prezzo Medio Rilevato)"
    except Exception as e:
        pass
        
    return "Prezzo da verificare a scaffale 🏪"

def interroga_off_camuffato(barcode):
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "From": "inciarmospesa_app@gmail.com"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == 1:
                prodotto = data.get("product", {})
                return {
                    "success": True,
                    "nome": prodotto.get("product_name", "Prodotto sconosciuto"),
                    "marca": prodotto.get("brands", "Marca non indicata"),
                    "stabilimento": prodotto.get("manufacturing_places", "")
                }
        return {"success": False}
    except:
        return {"success": False}

# --- UI STREAMLIT ---
st.title("L'Inciarmo della Spesa 🛒")
st.subheader("Fase 2: Connessione Prezzi tramite Proxy")

# Configurazione della geolocalizzazione commerciale
cap_utente = st.text_input("Inserisci il tuo CAP per i prezzi della tua zona:", value="20121", max_chars=5)

barcode = st.text_input("Scannerizza o digita il codice a barre:", placeholder="Es. 8002270014901").strip()

if barcode:
    with st.spinner("Bypassando le protezioni server per estrarre il prezzo..."):
        info_prodotto = interroga_off_camuffato(barcode)
        
    if info_prodotto["success"]:
        st.success(f"🔥 **Dati intercettati con successo!**")
        
        nome_completo = info_prodotto["nome"]
        prezzo_live = cerca_prezzo_unificato(nome_completo, barcode, cap_utente)
        bollino_pulito = pulisci_bollino(info_prodotto["stabilimento"])
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"💸 **Prezzo Live Estratto:**\n\n✨ {prezzo_live}")
        with col2:
            st.warning(f"👑 **Prodotto sul mercato:**\n\n✨ {nome_completo} [{info_prodotto['marca']}]")
            
        if bollino_pulito:
            st.metric(label="🏭 Codice Stabilimento Unico (Bollino CE)", value=bollino_pulito)
        else:
            st.write("Stabilimento: **ITALIA** (Controlla il retro della confezione fisica)")
    else:
        st.error("Prodotto non identificato nei database di tracciamento rapidi.")
        
