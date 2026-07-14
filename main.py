import streamlit as st
import requests
import re

st.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")

def pulisci_bollino(testo):
    if not testo: return ""
    testo_str = str(testo).upper().strip()
    match = re.search(r'(IT\s*\d+[\s*\/]*\d*\s*CE|\d+[\s*\/]*\d*\s*CE)', testo_str)
    if match:
        return re.sub(r'\s+', '', match.group(1))
    return re.sub(r'[^A-Z0-9]', '', testo_str)[:10]

def prendi_prezzo_eurospin(barcode):
    """Tenta l'attacco diretto all'endpoint pubblico di Eurospin Spesa Online"""
    # Usiamo l'endpoint web del catalogo che è meno protetto di quello dell'app mobile
    url = f"https://www.eurospin.it/api/v1/catalog/products/{barcode}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=4)
        if response.status_code == 200:
            data = response.json()
            # Estraiamo il prezzo dal JSON reale di Eurospin
            prezzo = data.get("price", {}).get("regular", "N/D")
            return f"{prezzo} €" if prezzo != "N/D" else "Non disponibile"
        return "Controllare a scaffale"
    except:
        return "Server Eurospin protetto"

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

# --- INTERFACCIA ---
st.title("L'Inciarmo della Spesa 🛒")
st.subheader("Fase 2: Connessione Prezzi Live Eurospin")

barcode = st.text_input("Scannerizza o digita il codice a barre:", placeholder="Es. 8000380004141").strip()

if barcode:
    with st.spinner("Estrazione dati di fabbrica e tracciamento prezzi..."):
        info_prodotto = interroga_off_camuffato(barcode)
        prezzo_live_eurospin = prendi_prezzo_eurospin(barcode)
        
    if info_prodotto["success"]:
        st.success(f"🔥 **Dati intercettati con successo!**")
        
        bollino_pulito = pulisci_bollino(info_prodotto["stabilimento"])
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"💸 **Insegna Discount (Eurospin):**\n\n✨ Prezzo Live Rilevato: **{prezzo_live_eurospin}**")
        with col2:
            st.warning(f"👑 **Prodotto sul mercato:**\n\n✨ {info_prodotto['nome']} [{info_prodotto['marca']}]")
            
        if bollino_pulito:
            st.metric(label="🏭 Codice Stabilimento Unico (Bollino CE)", value=bollino_pulito)
        else:
            st.write("Stabilimento non dichiarato nei metadati.")
    else:
        st.error("Prodotto non identificato nei database di tracciamento rapidi.")
        
