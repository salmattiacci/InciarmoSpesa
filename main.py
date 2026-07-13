import streamlit as st
import requests
import pandas as pd
import os
import re
import time
import random
from bs4 import BeautifulSoup

FILE_CACHE = "prodotti.csv"

# Insegne per il controllo dell'inversione dei ruoli (Marca vs Discount)
INSEGNE_SUPERMERCATI = ["eurospin", "conad", "coop", "esselunga", "lidl", "carrefour", "md", "todis", "selex", "pam", "penny", "aldi"]

# Configurazione della pagina Streamlit
st.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")

def pulisci_bollino(testo):
    if not testo or pd.isna(testo): return ""
    testo_str = str(testo).upper().strip()
    match = re.search(r'(IT\s*\d+[\s*\/]*\d*\s*CE|\d+[\s*\/]*\d*\s*CE)', testo_str)
    if match:
        return re.sub(r'\s+', '', match.group(1))
    match_elastico = re.search(r'(IT\d+CE|\d+CE)', re.sub(r'\s+', '', testo_str))
    if match_elastico:
        return match_elastico.group(1)
    pulito = re.sub(r'[^A-Z0-9]', '', testo_str).replace("EMB", "")
    return pulito[:12] if len(pulito) > 12 else pulito

def estrai_prezzo_web_gratis(nome_prodotto, brand):
    """
    Scraper Fai-Da-Te 100% Gratis. Usa DuckDuckGo Lite (senza JS e senza blocchi)
    per trovare il prezzo del prodotto sui volantini o siti di spesa italiani.
    """
    if not nome_prodotto or nome_prodotto == "Prodotto sconosciuto":
        return "N/A"
        
    query = f"prezzo {nome_prodotto} {brand} supermercato euro"
    url = "https://lite.duckduckgo.com/lite/"
    data = {"q": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # Piccolo delay casuale per simulare l'umano ed essere super sicuri
        time.sleep(random.uniform(0.5, 1.5))
        res = requests.post(url, data=data, headers=headers, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            testo_pagina = soup.get_text()
            
            # Cerca pattern di prezzi in Euro (es: 1,49€, € 2.50, 0.99 €)
            prezzi_trovati = re.findall(r'(\d+,\d{2})\s*€|€\s*(\d+,\d{2})|(\d+\.\d{2})\s*€', testo_pagina)
            validi = []
            for p in prezzi_trovati:
                # Prende il gruppo regex che ha catturato il testo
                pulito = p[0] if p[0] else (p[1] if p[1] else p[2])
                if pulito:
                    val_float = float(pulito.replace(',', '.'))
                    # Esclude micro-prezzi sballati o errori di lettura (es. pesi in kg o percentuali)
                    if 0.40 < val_float < 35.0:
                        validi.append(val_float)
            
            if validi:
                # Restituisce il prezzo più basso o frequente trovato nei risultati
                return f"{round(min(validi), 2)} €"
    except Exception as e:
        pass
    return "N/A"

def cerca_e_archivia_clone_live(barcode_utente):
    barcode_utente = str(barcode_utente).strip()
    
    # 1. CONTROLLO CACHE LOCALE
    if os.path.exists(FILE_CACHE):
        try:
            df_cache = pd.read_csv(FILE_CACHE)
            df_cache['barcode_marca'] = df_cache['barcode_marca'].astype(str)
            df_cache['barcode_discount'] = df_cache['barcode_discount'].astype(str)
            
            match_esistente = df_cache[(df_cache['barcode_marca'] == barcode_utente) | 
                                       (df_cache['barcode_discount'] == barcode_utente)]
            if not match_esistente.empty:
                return match_esistente.to_dict(orient="records")[0], "CACHE"
        except:
            pass

    # 2. CHIAMATA LIVE SUL PRODOTTO SCANSIONATO
    url_prod = f"https://it.openfoodfacts.org/api/v2/product/{barcode_utente}.json"
    headers = {"User-Agent": "InciarmoSpesaStreamlit/6.0 (Live Engine)"}
    
    try:
        res = requests.get(url_prod, headers=headers, timeout=10)
        if res.status_code != 200: 
            return {"errore": "Errore di connessione con il database internazionale."}, "ERRORE"
        
        dati = res.json()
        if dati.get("status") == 0: 
            return {"errore": "Codice a barre sconosciuto o non censito in Italia."}, "ERRORE"
        
        prodotto = dati.get("product", {})
        emb_codice = pulisci_bollino(prodotto.get("emb_codes", ""))
        
        categorie = prodotto.get("categories_tags", [])
        categoria = categorie[0].replace("en:", "").replace("it:", "") if categorie else "Alimentari"
        brand_utente = prodotto.get("brands", "Generico").split(",")[0].strip()
        nome_utente = prodotto.get("product_name", "Prodotto sconosciuto")
        
        if not emb_codice or emb_codice == "NAN":
            return {"errore": f"Trovato: **{nome_utente} [{brand_utente}]**. Purtroppo questo prodotto non ha un codice stabilimento valido inserito su Open Food Facts, impossibile trovare i cloni."}, "ERRORE"

        # 3. CHIAMATA LIVE: CERCA CLONI CON LO STESSO STABILIMENTO ISOLATO
        url_fabbrica = "https://it.openfoodfacts.org/api/v2/search"
        params = {
            "action": "process",
            "emb_codes_tags": emb_codice,
            "fields": "product_name,brands,code",
            "page_size": 50
        }
        
        res_fabbrica = requests.get(url_fabbrica, params=params, headers=headers, timeout=10)
        cloni_trovati = res_fabbrica.json().get("products", [])
        
        for clone in cloni_trovati:
            brand_clone = clone.get("brands", "Generico").split(",")[0].strip()
            code_clone = str(clone.get("code", "")).strip()
            nome_clone = clone.get("product_name", "Senza nome")
            
            if brand_clone != "Generico" and brand_clone.lower() != brand_utente.lower() and code_clone != barcode_utente:
                
                # Assegnazione iniziale dei ruoli
                m_marca, n_marca, m_barcode = brand_utente, nome_utente, barcode_utente
                m_discount, n_discount, e_barcode = brand_clone, nome_clone, code_clone
                
                # Controllo e correzione inversione ruoli
                if any(s in m_marca.lower() for s in INSEGNE_SUPERMERCATI) and not any(s in m_discount.lower() for s in INSEGNE_SUPERMERCATI):
                    m_marca, m_discount = m_discount, m_marca
                    n_marca, n_discount = n_discount, n_marca
                    m_barcode, e_barcode = e_barcode, m_barcode

                # SCRAPING LIVE E GRATUITO DEI PREZZI PRIMA DI SALVARE IL RECORD
                with st.spinner("Estrazione prezzi reali dal web in corso..."):
                    prezzo_m = estrai_prezzo_web_gratis(n_marca, m_marca)
                    prezzo_d = estrai_prezzo_web_gratis(n_discount, m_discount)

                nuovo_match = {
                    "stabilimento": emb_codice,
                    "categoria": categoria,
                    "discount": f"{n_discount} [{m_discount}]",
                    "marca": f"{n_marca} [{m_marca}]",
                    "barcode_discount": str(e_barcode),
                    "barcode_marca": str(m_barcode),
                    "prezzo_discount": prezzo_d,  
                    "prezzo_marca": prezzo_m,     
                    "nota": "Verificato live tramite codice stabilimento unico ministeriale con stima prezzi web.",
                    "bollino": "🟢 Identico (Stessa Fabbrica)"
                }
                
                # 4. SALVATAGGIO IN CACHE
                df_nuovo = pd.DataFrame([nuovo_match])
                if os.path.exists(FILE_CACHE):
                    df_vecchio = pd.read_csv(FILE_CACHE)
                    df_aggiornato = pd.concat([df_vecchio, df_nuovo]).drop_duplicates(subset=["barcode_discount", "barcode_marca"])
                else:
                    df_aggiornato = df_nuovo
                
                df_aggiornato.to_csv(FILE_CACHE, index=False)
                return नया_match, "LIVE"
                
        return {"errore": f"Trovato '{nome_utente} [{brand_utente}]' (Fabbrica: {emb_codice}), ma al momento non ci sono marchi alternativi censiti per questo stabilimento."}, "ERRORE"
        
    except Exception as e:
        return {"errore": f"Errore di rete: {str(e)}"}, "ERRORE"


# --- INTERFACCIA GRAFICA STREAMLIT ---

st.title("L'Inciarmo della Spesa 🛒")
st.subheader("Veri Inciarmi Industriali + Risparmio On-Demand (100% Free)")

barcode = st.text_input("Scannerizza o digita il codice a barre del prodotto:", placeholder="Es. 8017596064011")

if st.button("Trova Inciarmo 🎯", type="primary"):
    if barcode.strip():
        with st.spinner("Analisi dello stabilimento ministeriale in corso..."):
            risultato, stato = cerca_e_archivia_clone_live(barcode)
            
        if stato == "ERRORE":
            st.error(risultato["errore"])
        else:
            if stato == "CACHE":
                st.caption("⚡ *Risultato caricato istantaneamente dalla cache locale (Prezzi bloccati)*")
            else:
                st.caption("🌐 *Nuovo inciarmo scovato live con estrazione prezzi automatica a costo zero!*")
                
            st.markdown(f"### {risultato['bollino']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"💸 **Alternativa Discount/Insegna:**\n\n✨ {risultato['discount']}\n\n💰 Prezzo stimato: **{risultato['prezzo_discount']}**")
            with col2:
                st.warning(f"👑 **Prodotto Comparato:**\n\n✨ {risultato['marca']}\n\n💰 Prezzo stimato: **{risultato['prezzo_marca']}**")
                
            st.success(f"🏭 **Codice Stabilimento Unico:** {risultato['stabilimento']}")
            st.markdown(f"> 📋 **Nota d'ispezione:** {risultato['nota']}")
            
            st.write("---")
            st.write("ℹ️ *Se i prezzi estratti dal web sono imprecisi, puoi correggerli manualmente aggiornando il file prodotti.csv o usando il crowdsourcing.*")
    else:
        st.warning("Inserisci un codice a barre valido prima di cliccare.")
        
