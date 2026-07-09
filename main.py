import streamlit as st
import requests
import pandas as pd
import os
import re

FILE_CACHE = "prodotti.csv"

# Configurazione pagina Streamlit
st.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")

def pulisci_bollino(testo):
    if not testo or pd.isna(testo): return ""
    return re.sub(r'[^A-Z0-9]', '', str(testo).upper()).replace("EMB", "")

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
            return {"errore": f"Trovato: **{nome_utente} [{brand_utente}]**. Purtroppo non ha il codice stabilimento inserito nel database, impossibile trovare cloni."}, "ERRORE"

        # 3. CHIAMATA LIVE: CERCA CLONI CON LO STESSO STABILIMENTO
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
                
                # Abbiamo lo sgamo!
                nuovo_match = {
                    "stabilimento": emb_codice,
                    "categoria": categoria,
                    "discount": f"{nome_clone} [{brand_clone}]",
                    "marca": f"{nome_utente} [{brand_utente}]",
                    "barcode_discount": str(code_clone),
                    "barcode_marca": str(barcode_utente),
                    "prezzo_discount": "N/A",  
                    "prezzo_marca": "N/A",     
                    "nota": "Verificato live tramite codice stabilimento unico ministeriale.",
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
                return nuovo_match, "LIVE"
                
        return {"errore": f"Trovato '{nome_utente} [{brand_utente}]' (Fabbrica: {emb_codice}), ma non ci sono marchi alternativi censiti per questo stabilimento."}, "ERRORE"
        
    except Exception as e:
        return {"errore": f"Errore di rete: {str(e)}"}, "ERRORE"


# --- INTERFACCIA GRAFICA STREAMLIT ---

st.title("L'Inciarmo della Spesa 🛒")
st.subheader("Veri Inciarmi Industriali + Risparmio On-Demand")

# Input utente
barcode = st.text_input("Scannerizza o digita il codice a barre del prodotto:", placeholder="Es. 8017596064011")

if st.button("Trova Inciarmo 🎯", type="primary"):
    if barcode.strip():
        with st.spinner("Ricerca e analisi dello stabilimento ministeriale in corso..."):
            risultato, stato = cerca_e_archivia_clone_live(barcode)
            
        if stato == "ERRORE":
            st.error(risultato["errore"])
        else:
            if stato == "CACHE":
                st.caption("⚡ *Risultato caricato istantaneamente dalla cache locale*")
            else:
                st.caption("🌐 *Nuovo inciarmo scovato in tempo reale e salvato nel database!*")
                
            # Mostra i dati formattati come volevi tu
            st.markdown(f"### {risultato['bollino']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"💸 **Alternativa Discount/Insegna:**\n\n✨ {risultato['discount']}\n\n💰 Prezzo: **{risultato['prezzo_discount']}**")
            with col2:
                st.warning(f"👑 **Prodotto Comparato:**\n\n✨ {risultato['marca']}\n\n💰 Prezzo: **{risultato['prezzo_marca']}**")
                
            st.success(f"🏭 **Codice Stabilimento Unico:** {risultato['stabilimento']}")
            st.blockquote(f"📋 **Nota d'ispezione:** {risultato['nota']}")
            
            # Spazio Crowdsourcing Prezzi
            st.write("---")
            st.write("ℹ️ *I prezzi indicano 'N/A'? Aiuta la community! Se sei al supermercato, inserisci quanto li hai pagati per aggiornare il database.*")
    else:
        st.warning("Inserisci un codice a barre valido prima di cliccare.")
        
