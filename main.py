import streamlit as st
import requests
import re
from bs4 import BeautifulSoup

st.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")

HEADERS = {
    "User-Agent": "InciarmoDellaSpesaApp/2.0 (contatto: inciarmospesa_app@gmail.com)"
}

# Aggiorna questo link ogni settimana con il volantino corrente
URL_VOLANTINO = "https://deco.volantinopiu.com/volantino2793400pv615.html"


def pulisci_bollino(testo):
    if not testo:
        return ""
    testo_str = str(testo).upper().strip()
    match = re.search(r'(IT\s*\d+[\s*\/]*\d*\s*CE|\d+[\s*\/]*\d*\s*CE)', testo_str)
    if match:
        return re.sub(r'\s+', '', match.group(1))
    return re.sub(r'[^A-Z0-9]', '', testo_str)[:10]


@st.cache_data(ttl=3600)  # ricarica il volantino al massimo una volta all'ora
def scrape_volantino_deco(url):
    """Scarica il volantino e restituisce lista di {prezzo, descrizione}."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    risultati = []
    for prezzo_tag in soup.find_all(string=re.compile(r"€\s*\d+[.,]\d{2}")):
        contenitore = prezzo_tag.find_parent("div") or prezzo_tag.find_parent()
        testo = contenitore.get_text(" ", strip=True) if contenitore else ""
        risultati.append({"prezzo": prezzo_tag.strip(), "descrizione": testo[:150]})
    return risultati


def trova_prezzo_volantino(nome_prodotto, prodotti_volantino):
    if not nome_prodotto:
        return None, None
    nome_lower = nome_prodotto.lower()
    for p in prodotti_volantino:
        if nome_lower in p["descrizione"].lower():
            return p["prezzo"], p["descrizione"]
    return None, None


def ottieni_prezzo_reale_definitivo(barcode, nome_prodotto):
    """
    1. Prova Open Prices (database collaborativo di prezzi reali).
    2. Se non trova nulla, cerca il prodotto nel volantino Decò corrente.
    Restituisce solo ed esclusivamente prezzi reali, senza stime.
    """
    barcode_pulito = str(barcode).strip()

    # 1. TENTATIVO: API Open Prices
    url_prices = f"https://prices.openfoodfacts.org/api/v1/prices?product_code={barcode_pulito}"
    try:
        response = requests.get(url_prices, headers=HEADERS, timeout=8)
        if response.status_code == 200:
            items = response.json().get("items", [])
            if items:
                ultimo_item = items[0]
                prezzo = ultimo_item.get("price")
                store = ultimo_item.get("location_name", "Supermercato")
                data_agg = (ultimo_item.get("created_at") or "")[:10]
                if prezzo is not None:
                    return f"{float(prezzo):.2f} € (Trovato presso: {store} - Rilevato il {data_agg})"
    except requests.RequestException:
        pass

    # 2. TENTATIVO: volantino Decò corrente
    prodotti_volantino = scrape_volantino_deco(URL_VOLANTINO)
    prezzo_volantino, descrizione = trova_prezzo_volantino(nome_prodotto, prodotti_volantino)
    if prezzo_volantino:
        return f"{prezzo_volantino} (Volantino Decò: {descrizione})"

    return "Prezzo reale non ancora mappato nei database aperti 🏪"


def interroga_off_completo(barcode):
    url = f"https://world.openfoodfacts.net/api/v2/product/{barcode}.json"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
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
    except requests.RequestException:
        return {"success": False}


# --- UI STREAMLIT ---
st.title("L'Inciarmo della Spesa 🛒")
st.subheader("Fase 2: Prezzi Reali Verificati")

barcode = st.text_input("Scannerizza o digita il codice a barre:", placeholder="Es. 8002270014901").strip()

if barcode:
    with st.spinner("Interrogazione database prezzi reali in corso..."):
        info_prodotto = interroga_off_completo(barcode)

    if info_prodotto["success"]:
        st.success("🔥 **Dati intercettati con successo!**")

        nome_completo = info_prodotto["nome"]
        prezzo_live = ottieni_prezzo_reale_definitivo(barcode, nome_completo)
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
    
