import streamlit as st
import requests
import re
from urllib.parse import quote

st.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")

def pulisci_bollino(testo):
    if not testo: return ""
    testo_str = str(testo).upper().strip()
    match = re.search(r'(IT\s*\d+[\s*\/]*\d*\s*CE|\d+[\s*\/]*\d*\s*CE)', testo_str)
    if match:
        return re.sub(r'\s+', '', match.group(1))
    return re.sub(r'[^A-Z0-9]', '', testo_str)[:10]

def cerca_prezzo_everli(query, cap="20121"):
    """
    Interroga l'endpoint pubblico dell'aggregatore Everli.
    Invia il CAP per localizzare i supermercati disponibili nella zona.
    """
    query_pulita = quote(str(query).split(",")[0])
    # Endpoint pubblico di ricerca catalogo di Everli
    url = f"https://www.everli.com/api/v2/search?q={query_pulita}&zipcode={cap}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "it-IT,it;q=0.9",
        "Referer": "https://www.everli.com/"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Navighiamo l'albero del JSON di Everli per estrarre i prodotti
            products = data.get("products", [])
            if products:
                primo_prodotto = products[0]
                nome = primo_prodotto.get("name", "")
                prezzo = primo_prodotto.get("price", "N/D")
                store = primo_prodotto.get("store_name", "Supermercato Partner")
                
                if prezzo != "N/D":
                    return f"{prezzo} € ({store})"
            return "Prodotto non trovato su Everli per questo CAP"
        elif response.status_code == 403:
            return "Everli richiede verifica (Anti-Bot attivo)"
        return f"Everli Standard (Codice {response.status_code})"
    except:
        return "Connessione a Everli non riuscita"

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
st.subheader("Fase 2: Comparazione Aggregata Live")

# Configurazione della geolocalizzazione commerciale
cap_utente = st.text_input("Inserisci il tuo CAP per i prezzi della tua zona:", value="20121", max_chars=5)

barcode = st.text_input("Scannerizza o digita il codice a barre:", placeholder="Es. 8002270014901").strip()

if barcode:
    with st.spinner("Interrogando i database di spesa della tua zona..."):
        info_prodotto = interroga_off_camuffato(barcode)
        
    if info_prodotto["success"]:
        st.success(f"🔥 **Dati intercettati con successo!**")
        
        nome_completo = info_prodotto["nome"]
        # Interroghiamo Everli usando il nome reale del prodotto estratto dal barcode
        prezzo_live = cerca_prezzo_everli(nome_completo, cap_utente)
        bollino_pulito = pulisci_bollino(info_prodotto["stabilimento"])
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"💸 **Miglior Prezzo Rilevato (Everli):**\n\n✨ {prezzo_live}")
        with col2:
            st.warning(f"👑 **Prodotto sul mercato:**\n\n✨ {nome_completo} [{info_prodotto['marca']}]")
            
        if bollino_pulito:
            st.metric(label="🏭 Codice Stabilimento Unico (Bollino CE)", value=bollino_pulito)
        else:
            st.write("Stabilimento: **ITALIA** (Controlla il retro della confezione fisica)")
    else:
        st.error("Prodotto non identificato nei database di tracciamento rapidi.")
        
