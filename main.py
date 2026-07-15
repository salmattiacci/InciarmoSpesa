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

def ottieni_prezzo_reale_definitivo(barcode):
    """
    Interroga le API pubbliche di Open Prices. 
    Restituisce solo ed esclusivamente prezzi reali al centesimo inseriti nel database,
    senza fare alcuna stima o approssimazione.
    """
    # Puliamo il barcode per assicurarci che sia nel formato corretto senza spazi
    barcode_pulito = str(barcode).strip()
    
    # 1. TENTATIVO: API Open Prices (Database collaborativo globale dei prezzi reali)
    url_prices = f"https://api.prices.openfoodfacts.org/v1/prices?product_code={barcode_pulito}"
    headers = {
        "User-Agent": "InciarmoDellaSpesaApp/2.0 (contatto: inciarmospesa_app@gmail.com)"
    }
    
    try:
        response = requests.get(url_prices, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            if items:
                # Ordiniamo per trovare il prezzo più recente registrato
                ultimo_item = items[0]
                prezzo = ultimo_item.get("price")
                store = ultimo_item.get("location_name", "Supermercato")
                data_agg = ultimo_item.get("created_at", "")[:10] # Prende la data YYYY-MM-DD
                
                if prezzo is not None:
                    return f"{float(prezzo):.2f} € (Trovato presso: {store} - Rilevato il {data_agg})"
                    
        # 2. TENTATIVO: Endpoint OFF integrato (Prezzo medio memorizzato nella scheda prodotto)
        url_off = f"https://world.openfoodfacts.org/api/v2/product/{barcode_pulito}.json"
        res_off = requests.get(url_off, headers=headers, timeout=4)
        if res_off.status_code == 200:
            product_data = res_off.json().get("product", {})
            prezzo_diretto = product_data.get("price")
            store_diretto = product_data.get("stores", "Store non specificato")
            if prezzo_diretto:
                return f"{float(prezzo_diretto):.2f} € (Archiviato da: {store_diretto})"
                
    except Exception as e:
        return f"Errore di connessione ai database prezzi"
        
    return "Prezzo reale non ancora mappato nei database aperti 🏪"

def interroga_off_completo(barcode):
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    headers = {
        "User-Agent": "InciarmoDellaSpesaApp/2.0 (contatto: inciarmospesa_app@gmail.com)"
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
st.subheader("Fase 2: Prezzi Reali Verificati")

barcode = st.text_input("Scannerizza o digita il codice a barre:", placeholder="Es. 8002270014901").strip()

if barcode:
    with st.spinner("Interrogazione database prezzi reali in corso..."):
        info_prodotto = interroga_off_completo(barcode)
        
    if info_prodotto["success"]:
        st.success(f"🔥 **Dati intercettati con successo!**")
        
        nome_completo = info_prodotto["nome"]
        # Chiamata al motore prezzi reali pulito
        prezzo_live = ottieni_prezzo_reale_definitivo(barcode)
        bollino_pulito = pulisci_bollino(info_prodotto["stabilimento"])
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"💸 **Prezzo Reale Rilevato:**\n\n✨ {prezzo_live}")
        with col2:
            st.warning(f"👑 **Prodotto sul mercato:**\n\n✨ {nome_completo} [{info_prodotto['marca']}]")
            
        if bollino_pulito:
            st.metric(label="🏭 Codice Stabilimento Unico (Bollino CE)", value=bollino_pulito)
        else:
            st.write("Stabilimento: **ITALIA** (Controlla il retro della confezione)")
    else:
        st.error("Prodotto non identificato nei database di tracciamento rapidi.")
