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

def cerca_prezzo_google(barcode, nome_prodotto):
    """
    Estrae il prezzo di mercato reale scansionando i risultati di Google Shopping Italia.
    Bypassa totalmente i blocchi dei singoli supermercati.
    """
    # Cerchiamo usando il codice a barre per massima precisione, altrimenti il nome prodotto
    query = barcode if barcode else nome_prodotto
    url = f"https://www.google.it/search?q={quote(query)}+prezzo+supermercato"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            html = response.text
            
            # Cerchiamo pattern di prezzi tipici italiani (es. 1,49 € o 0,99 € o € 2,50)
            # Questo regex intercetta i numeri con la virgola seguiti o preceduti dal simbolo dell'Euro
            prezzi_trovati = re.findall(r'(\d+,\d{2})\s*€|€\s*(\d+,\d{2})', html)
            
            valori = []
            for p in prezzi_trovati:
                valore = p[0] if p[0] else p[1]
                valori.append(float(valore.replace(",", ".")))
                
            if valori:
                # Prendiamo il prezzo minimo rilevato sul web (escludendo eventuali errori irrealistici sotto 0.10€)
                valori_validi = [v for v in valori if v > 0.15]
                if valori_validi:
                    prezzo_minimo = min(valori_validi)
                    return f"Da {prezzo_minimo:.2f} € (Rilevato sul Web 🌐)"
                    
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
st.subheader("Fase 2: Connessione Prezzi Globale")

barcode = st.text_input("Scannerizza o digita il codice a barre:", placeholder="Es. 8002270014901").strip()

if barcode:
    with st.spinner("Intercettando i prezzi reali sul mercato..."):
        info_prodotto = interroga_off_camuffato(barcode)
        
    if info_prodotto["success"]:
        st.success(f"🔥 **Dati intercettati con successo!**")
        
        nome_completo = info_prodotto["nome"]
        # Chiamata al nuovo motore Google-based
        prezzo_live = cerca_prezzo_google(barcode, nome_completo)
        bollino_pulito = pulisci_bollino(info_prodotto["stabilimento"])
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"💸 **Prezzo Rilevato:**\n\n✨ {prezzo_live}")
        with col2:
            st.warning(f"👑 **Prodotto sul mercato:**\n\n✨ {nome_completo} [{info_prodotto['marca']}]")
            
        if bollino_pulito:
            st.metric(label="🏭 Codice Stabilimento Unico (Bollino CE)", value=bollino_pulito)
        else:
            st.write("Stabilimento: **ITALIA** (Controlla il retro della confezione fisica)")
    else:
        st.error("Prodotto non identificato nei database di tracciamento rapidi.")
        
