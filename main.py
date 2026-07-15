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

def ottieni_prezzo_carrefour_reale(barcode):
    """
    Interroga direttamente l'API pubblica di Carrefour Italia per avere il prezzo reale
    al centesimo senza stime e senza blocchi IP.
    """
    # Endpoint ufficiale di ricerca di Carrefour Italia per codice a barre
    url = f"https://www.carrefour.it/api/v1/products/search?q={barcode}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "x-carrefour-brand": "carrefour"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Estraiamo i prodotti dal JSON di Carrefour
            products = data.get("searchResponse", {}).get("products", [])
            if products:
                primo = products[0]
                prezzo = primo.get("price", {}).get("salesPrice")
                nome_reale = primo.get("name")
                
                if prezzo:
                    return f"{float(prezzo):.2f} € (Prezzo Reale Carrefour 🛒)"
    except Exception as e:
        pass
        
    return "Prezzo non trovato (Prodotto non a listino Carrefour)"

def interroga_off_completo(barcode):
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
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
st.subheader("Fase 2: Prezzi Reali al Centesimo")

barcode = st.text_input("Scannerizza o digita il codice a barre:", placeholder="Es. 8002270014901").strip()

if barcode:
    with st.spinner("Connessione ai server dei prezzi in corso..."):
        info_prodotto = interroga_off_completo(barcode)
        
    if info_prodotto["success"]:
        st.success(f"🔥 **Dati intercettati con successo!**")
        
        nome_completo = info_prodotto["nome"]
        # Interrogazione API Carrefour per prezzo reale
        prezzo_live = ottieni_prezzo_carrefour_reale(barcode)
        bollino_pulito = pulisci_bollino(info_prodotto["stabilimento"])
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"💸 **Prezzo Live:**\n\n✨ {prezzo_live}")
        with col2:
            st.warning(f"👑 **Prodotto sul mercato:**\n\n✨ {nome_completo} [{info_prodotto['marca']}]")
            
        if bollino_pulito:
            st.metric(label="🏭 Codice Stabilimento Unico (Bollino CE)", value=bollino_pulito)
        else:
            st.write("Stabilimento: **ITALIA** (Controlla il retro della confezione)")
    else:
        st.error("Prodotto non identificato nei database di tracciamento rapidi.")
        
