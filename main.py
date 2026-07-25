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


URL_CATALOGO_DECO = "https://supermercatideco.it/manager/includer.php"
SHOP_ID_DECO = "38774"  # verifica se corrisponde al tuo punto vendita


def cerca_prodotto_deco(nome_prodotto):
    """Cerca live nel catalogo Decò (no cache, dati sempre freschi)."""
    if not nome_prodotto:
        return None

    payload = {
        "version": "225-960",
        "mobile": 1,
        "action": "read_all_by_shop_id_filtered_frontend",
        "filter[fTag]": "",
        "filter[fCode]": "",
        "filter[sort]": 1,
        "filter[fCatalog]": 0,
        "filter[min_price]": "",
        "filter[max_price]": "",
        "filter[min_amount]": "",
        "filter[max_amount]": "",
        "filter[search]": nome_prodotto,
        "filter[fCat]": "",
        "filter[fBrands]": "",
        "filter[fSeasons]": "",
        "filter[ops_id]": 0,
        "start": 0,
        "length": 5,
        "addVat": 1,
        "_cache": 0,
        "f": "EcommerceManagerExt/services/reader_product",
        "language_code": "it",
        "fallback_lang": "it",
        "shop_id": SHOP_ID_DECO,
    }
    headers = {**HEADERS, "X-Requested-With": "XMLHttpRequest"}
    try:
        resp = requests.post(URL_CATALOGO_DECO, data=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            dati = resp.json().get("data", {})
            prodotti = dati.get("products") if isinstance(dati, dict) else None
            if prodotti:
                return prodotti[0]  # primo risultato più rilevante
    except (requests.RequestException, ValueError):
        pass
    return None


def ottieni_prezzo_reale_definitivo(barcode, nome_prodotto):
    """
    1. Cerca live nel catalogo Decò (dati sempre freschi, no cache).
    2. Se non trova nulla, prova Open Prices (database collaborativo).
    3. Come ultima spiaggia, cerca nel volantino Decò corrente.
    Restituisce solo ed esclusivamente prezzi reali, senza stime.
    """
    barcode_pulito = str(barcode).strip()

    # 1. TENTATIVO: catalogo Decò live
    prodotto_deco = cerca_prodotto_deco(nome_prodotto)
    if prodotto_deco:
        # NOTA: adatta questi nomi di campo quando conosci la struttura
        # esatta della risposta (guarda deco_catalogo_raw.json)
        prezzo = prodotto_deco.get("price") or prodotto_deco.get("prezzo")
        nome_deco = prodotto_deco.get("name") or prodotto_deco.get("title") or nome_prodotto
        if prezzo:
            return f"{prezzo} € (Catalogo Decò live: {nome_deco})"

    # 2. TENTATIVO: API Open Prices
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


def e_barcode(testo):
    return testo.strip().isdigit() and 8 <= len(testo.strip()) <= 14


def cerca_barcode_per_nome(nome):
    """Trova il barcode di un prodotto a partire dal nome (ricerca OFF)."""
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {"search_terms": nome, "search_simple": 1, "action": "process", "json": 1, "page_size": 1}
    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if res.status_code == 200:
            prodotti = res.json().get("products", [])
            if prodotti:
                return prodotti[0].get("code")
    except requests.RequestException:
        pass
    return None


def controlla_corrispondenza_in_sessione(nuovo_prodotto):
    """Confronta il bollino CE del prodotto appena cercato con quelli già
    cercati in questa sessione (salvati in memoria, nessun file)."""
    if not nuovo_prodotto["bollino"]:
        return []
    return [
        p for p in st.session_state.collezione
        if p["bollino"] == nuovo_prodotto["bollino"] and p["marca"] != nuovo_prodotto["marca"]
    ]



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

# --- UI STREAMLIT ---
st.title("L'Inciarmo della Spesa 🛒")
st.subheader("Cerca per nome o barcode, confronto marca vs private label")

if "collezione" not in st.session_state:
    st.session_state.collezione = []  # lista in memoria, vive solo per questa sessione

testo_ricerca = st.text_input(
    "Barcode o nome prodotto:", placeholder="Es. 8002270014901 oppure 'pasta barilla napoletana'"
).strip()

if testo_ricerca:
    with st.spinner("Ricerca in corso..."):
        if e_barcode(testo_ricerca):
            barcode = testo_ricerca
        else:
            barcode = cerca_barcode_per_nome(testo_ricerca)

        info_prodotto = interroga_off_completo(barcode) if barcode else {"success": False}

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

        prodotto_corrente = {
            "barcode": barcode,
            "nome": nome_completo,
            "marca": info_prodotto["marca"],
            "bollino": bollino_pulito,
        }

        corrispondenze = controlla_corrispondenza_in_sessione(prodotto_corrente)
        if corrispondenze:
            st.balloons()
            st.success("🎯 **MATCH! Stesso stabilimento di:**")
            for p in corrispondenze:
                st.write(f"- {p['marca']} — {p['nome']}")
        elif bollino_pulito:
            st.caption("Nessuna corrispondenza (per ora) con altri prodotti cercati in questa sessione.")

        st.session_state.collezione.append(prodotto_corrente)

        with st.expander(f"📋 Prodotti cercati in questa sessione ({len(st.session_state.collezione)})"):
            for p in st.session_state.collezione:
                st.write(f"- {p['marca']} — {p['nome']} (bollino: {p['bollino'] or 'n/d'})")
    else:
        st.error("Prodotto non identificato nei database di tracciamento rapidi.")

