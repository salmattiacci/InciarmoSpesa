import streamlit as st
import requests
import re

from matching.match_prodotti import Prodotto, valuta_coppia, prodotto_da_off_json, calcola_similarita_ingredienti

st.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")

HEADERS = {
    "User-Agent": "InciarmoDellaSpesaApp/2.0 (contatto: inciarmospesa_app@gmail.com)"
}


def pulisci_bollino(testo):
    if not testo:
        return ""
    testo_str = str(testo).upper().strip()
    match = re.search(r'(IT\s*\d+[\s*\/]*\d*\s*CE|\d+[\s*\/]*\d*\s*CE)', testo_str)
    if match:
        return re.sub(r'\s+', '', match.group(1))
    return re.sub(r'[^A-Z0-9]', '', testo_str)[:10]


URL_CATALOGO_DECO = "https://supermercatideco.it/manager/includer.php"
SHOP_ID_DECO = "38774"  # verifica se corrisponde al tuo punto vendita


def cerca_prodotto_deco(nome_prodotto):
    """Cerca live nel catalogo Decò (usato solo per identificare il prodotto
    quando OFF non lo trova, non per il prezzo)."""
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


def e_barcode(testo):
    return testo.strip().isdigit() and 8 <= len(testo.strip()) <= 14


def cerca_barcode_per_nome(nome):
    """Trova il barcode di un prodotto a partire dal nome (ricerca OFF).
    Privilegia risultati venduti/prodotti in Italia, per evitare di pescare
    varianti estere (es. senza glutine francese) che hanno ricette diverse."""
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": nome,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 10,
        "fields": "code,countries_tags",
    }
    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if res.status_code != 200:
            return None
        prodotti = res.json().get("products", [])
        if not prodotti:
            return None

        # 1° tentativo: primo prodotto venduto/prodotto in Italia
        for p in prodotti:
            if "en:italy" in (p.get("countries_tags") or []):
                return p.get("code")

        # fallback: se nessuno risulta italiano, prendi comunque il primo risultato
        return prodotti[0].get("code")
    except requests.RequestException:
        return None


def interroga_off_completo(barcode):
    """Recupera nome, marca, stabilimento, ingredienti e categorie da Open Food Facts."""
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
                    "stabilimento": prodotto.get("manufacturing_places", ""),
                    "ingredienti": prodotto.get("ingredients_text_it") or prodotto.get("ingredients_text", ""),
                    "categorie": prodotto.get("categories_tags", []),
                }
        return {"success": False}
    except requests.RequestException:
        return {"success": False}


def normalizza_marca(marca):
    """Prende solo il primo brand (se separati da virgola) e normalizza
    maiuscole/spazi, per confrontare in modo affidabile."""
    primo = (marca or "").split(",")[0].strip().lower()
    return primo


def stessa_marca(marca_a, marca_b):
    """True se le due marche sono uguali o una è contenuta nell'altra
    (es. 'De Cecco' vs 'F.lli De Cecco di Filippo' sono la stessa azienda)."""
    a, b = normalizza_marca(marca_a), normalizza_marca(marca_b)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _query_off_search(params, max_risultati):
    url = "https://world.openfoodfacts.org/api/v2/search"
    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if res.status_code != 200:
            return [], f"HTTP {res.status_code}"
        return res.json().get("products", []), None
    except requests.RequestException as e:
        return [], str(e)


def cerca_candidati_stessa_categoria(categoria_tag, marca_esclusa, barcode_escluso, max_risultati=30):
    """Cerca su OFF altri prodotti nella stessa categoria specifica (es.
    'en:durum-wheat-spaghetti'), escludendo la marca e il barcode di
    partenza. Usato per trovare da soli i possibili equivalenti, senza che
    l'utente debba cercarli a mano uno per uno."""
    diagnostica = {"categoria_en": None, "grezzi_con_italia": 0, "grezzi_senza_italia": 0, "errore": None}

    if not categoria_tag:
        return [], diagnostica

    # 'en:durum-wheat-spaghetti' -> 'Durum Wheat Spaghetti' (formato atteso da categories_tags_en)
    nome_categoria_en = categoria_tag.split(":", 1)[-1].replace("-", " ").title()
    diagnostica["categoria_en"] = nome_categoria_en

    fields = "code,product_name,brands,manufacturing_places,ingredients_text_it,ingredients_text,categories_tags"

    prodotti, errore = _query_off_search(
        {
            "categories_tags_en": nome_categoria_en,
            "countries_tags_en": "Italy",
            "page_size": max_risultati,
            "sort_by": "unique_scans_n",
            "fields": fields,
        },
        max_risultati,
    )
    diagnostica["grezzi_con_italia"] = len(prodotti)
    diagnostica["errore"] = errore

    # Fallback: se col filtro Italia non troviamo nulla, riproviamo senza
    # (meglio un candidato non-italiano che nessun candidato)
    if not prodotti:
        prodotti, errore = _query_off_search(
            {
                "categories_tags_en": nome_categoria_en,
                "page_size": max_risultati,
                "sort_by": "unique_scans_n",
                "fields": fields,
            },
            max_risultati,
        )
        diagnostica["grezzi_senza_italia"] = len(prodotti)
        diagnostica["errore"] = diagnostica["errore"] or errore

    candidati = []
    for p in prodotti:
        if p.get("code") == barcode_escluso:
            continue
        if stessa_marca(p.get("brands"), marca_esclusa):
            continue
        prodotto = prodotto_da_off_json(p)
        if prodotto:
            candidati.append(prodotto)
    return candidati, diagnostica


def costruisci_prodotto(barcode, nome, marca, bollino, info_off):
    """Crea l'oggetto Prodotto usato dal modulo di matching."""
    return Prodotto(
        barcode=barcode or "",
        nome=nome,
        marca=marca,
        categorie=info_off.get("categorie", []),
        ingredienti=info_off.get("ingredienti", ""),
        stabilimento=bollino or None,
    )


# --- UI STREAMLIT ---
st.title("L'Inciarmo della Spesa 🛒")
st.subheader("Cerca per nome o barcode, confronto marca vs private label")

if "collezione" not in st.session_state:
    st.session_state.collezione = []  # lista di Prodotto, vive solo per questa sessione

soglia_ingredienti = st.slider(
    "Soglia similarità ingredienti per considerare un match", 50, 100, 75
)

testo_ricerca = st.text_input(
    "Barcode o nome prodotto:", placeholder="Es. 8002270014901 oppure 'pasta barilla napoletana'"
).strip()

if testo_ricerca:
    with st.spinner("Ricerca in corso..."):
        barcode = None if e_barcode(testo_ricerca) else cerca_barcode_per_nome(testo_ricerca)
        if e_barcode(testo_ricerca):
            barcode = testo_ricerca

        info_prodotto = interroga_off_completo(barcode) if barcode else {"success": False}

        # Fallback: se OFF non ha il prodotto (tipico dei marchi privati come Decò),
        # prova a cercarlo direttamente nel catalogo Decò
        if not info_prodotto["success"] and not e_barcode(testo_ricerca):
            prodotto_deco_diretto = cerca_prodotto_deco(testo_ricerca)
            if prodotto_deco_diretto:
                nome_trovato = prodotto_deco_diretto.get("name") or testo_ricerca
                codice_deco = prodotto_deco_diretto.get("code")

                # Con il barcode vero del prodotto Decò, proviamo OFF per stabilimento/ingredienti
                info_off_deco = interroga_off_completo(codice_deco) if codice_deco else {"success": False}

                info_prodotto = {
                    "success": True,
                    "nome": nome_trovato,
                    "marca": "Decò",
                    "stabilimento": info_off_deco.get("stabilimento", "") if info_off_deco["success"] else "",
                    "ingredienti": info_off_deco.get("ingredienti", "") if info_off_deco["success"] else "",
                    "categorie": info_off_deco.get("categorie", []) if info_off_deco["success"] else [],
                }
                if codice_deco:
                    barcode = codice_deco

    if info_prodotto["success"]:
        st.success("🔥 **Dati intercettati con successo!**")

        nome_completo = info_prodotto["nome"]
        bollino_pulito = pulisci_bollino(info_prodotto["stabilimento"])

        st.warning(f"👑 **Prodotto sul mercato:**\n\n✨ {nome_completo} [{info_prodotto['marca']}]")

        if bollino_pulito:
            st.metric(label="🏭 Codice Stabilimento Unico (Bollino CE)", value=bollino_pulito)
        else:
            st.write("Stabilimento: **ITALIA** (Controlla il retro della confezione)")

        prodotto_corrente = costruisci_prodotto(
            barcode, nome_completo, info_prodotto["marca"], bollino_pulito, info_prodotto
        )

        categorie = info_prodotto.get("categorie", [])
        categoria_specifica = categorie[-1] if categorie else None

        with st.spinner("Cerco possibili equivalenti..."):
            candidati, diagnostica = cerca_candidati_stessa_categoria(
                categoria_specifica, info_prodotto["marca"], barcode
            )
            # calcolo lo score di ogni candidato, anche sotto soglia, per il debug
            tutti_gli_score = []
            for cand in candidati:
                score_ing = calcola_similarita_ingredienti(prodotto_corrente, cand)
                tutti_gli_score.append((cand, score_ing))
            tutti_gli_score.sort(key=lambda t: t[1], reverse=True)

            corrispondenze = [
                c for cand in candidati
                if (c := valuta_coppia(prodotto_corrente, cand, soglia_ingredienti))
            ]
            corrispondenze.sort(key=lambda c: c.score_finale, reverse=True)

        if corrispondenze:
            st.balloons()
            st.success("🎯 **Guarda anche:**")
            for c in corrispondenze[:5]:
                st.write(
                    f"- **{c.prodotto_b.marca}** — {c.prodotto_b.nome} "
                    f"(ingredienti: {c.score_ingredienti}% · "
                    f"stesso stabilimento: {'sì' if c.stesso_stabilimento else 'no'} · "
                    f"score: {c.score_finale}%)"
                )
        else:
            st.caption("Nessun equivalente trovato con questa soglia.")

        st.session_state.collezione.append(prodotto_corrente)

        with st.expander(f"📋 Prodotti cercati in questa sessione ({len(st.session_state.collezione)})"):
            for p in st.session_state.collezione:
                st.write(f"- {p.marca} — {p.nome} (bollino: {p.stabilimento or 'n/d'})")

        with st.expander("🔍 Debug dati grezzi (ingredienti/categorie)"):
            for p in st.session_state.collezione:
                st.markdown(f"**{p.marca} — {p.nome}**")
                st.write(f"Categorie: {p.categorie or 'nessuna'}")
                st.write(f"Ingredienti: {p.ingredienti or 'nessuno'}")
                st.write("---")

        with st.expander(f"🧪 Debug candidati confrontati ({len(candidati)} trovati nella stessa categoria)"):
            st.write(f"Categoria OFF usata per la ricerca: `{diagnostica['categoria_en']}`")
            st.write(f"Risultati grezzi con filtro Italia: {diagnostica['grezzi_con_italia']}")
            if diagnostica["grezzi_senza_italia"]:
                st.write(f"Risultati grezzi senza filtro Italia (fallback usato): {diagnostica['grezzi_senza_italia']}")
            if diagnostica["errore"]:
                st.error(f"Errore chiamata OFF: {diagnostica['errore']}")
            if not tutti_gli_score:
                st.write("Nessun candidato trovato su OFF per questa categoria/paese.")
            for cand, score_ing in tutti_gli_score[:15]:
                st.write(
                    f"- **{cand.marca}** — {cand.nome} → similarità ingredienti: {round(score_ing, 1)}% "
                    f"(ingredienti: {cand.ingredienti[:80] or 'vuoto'}...)"
                )
    else:
        st.error("Prodotto non identificato nei database di tracciamento rapidi.")
    
