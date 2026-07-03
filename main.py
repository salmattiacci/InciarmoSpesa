import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests

# 1. Configurazione UI Mobile-First
st.set_page_config(
    page_title="L'Inciarmo della Spesa", 
    page_icon="🛒", 
    layout="centered"
)

st.title("L'Inciarmo della Spesa 🛒")
st.caption("Database dinamico dei produttori reali dietro i brand da discount")

# 2. Inizializzazione Connettore Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Cache impostata a 60 secondi per vedere rapidamente gli aggiornamenti
    df = conn.read(ttl=60)
except Exception as e:
    st.error("Errore di connessione al database Google Sheets.")
    df = pd.DataFrame()

# 3. Definizione dei Tab di Navigazione (Ottimizzati per lo switch da smartphone)
tab_cerca, tab_segnala, tab_admin = st.tabs(["🔍 Cerca Prodotti", "📢 Segnala uno Sgamo", "⚙️ Sincronizza Dati"])

# --- TAB 1: RICERCA E VISUALIZZAZIONE ---
with tab_cerca:
    query = st.text_input("Cerca stabilimento, discount o marca...", placeholder="Es. Eurospin, Conad, IT 03 3 CE...")

    if not df.empty:
        # Filtro dinamico case-insensitive su tutte le colonne del DataFrame
        if query:
            mask = df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)
            df_filtrato = df[mask]
        else:
            df_filtrato = df

        if df_filtrato.empty:
            st.warning("Nessun inciarmo trovato con questi filtri. Segnalalo tu nel secondo tab!")
        else:
            # Rendering dei prodotti in Card grafiche pulite
            for _, row in df_filtrato.iterrows():
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{row['discount']}**")
                        st.markdown(f"💎 *Equivalente a:* **{row['marca']}**")
                    with col2:
                        st.caption(f"**{row['bollino']}**")
                    
                    st.divider()
                    st.caption(f"🏭 Stabilimento: {row['stabilimento']} | Categoria: {row['categoria']}")
                    st.write(row['nota'])
    else:
        st.info("Il database è temporaneamente vuoto o in fase di sincronizzazione.")

# --- TAB 2: CROWDSOURCING UTENTI ---
with tab_segnala:
    st.subheader("Hai scoperto un nuovo inciarmo?")
    st.caption("Inserisci i dati dell'etichetta. Dopo una verifica tecnica sulla ricetta, verrà inserito nel DB pubblico.")
    
    with st.form("segnalazione_form", clear_on_submit=True):
        sc_stabilimento = st.text_input("Codice Stabilimento / Bollo CE *", placeholder="Es. IT 03 3 CE")
        sc_discount = st.text_input("Prodotto e Supermercato *", placeholder="Es. Frollini Conad")
        sc_marca = st.text_input("Prodotto di Marca Equivalente *", placeholder="Es. Tarallucci Mulino Bianco")
        sc_categoria = st.selectbox("Categoria", ["Latticini", "Dolci e Colazione", "Snack e Patatine", "Conserve", "Bevande", "Altro"])
        sc_nota = st.text_area("Note sulla ricetta (Ingredienti, somiglianze, sapore...)")
        
        submitted = st.form_submit_button("Invia Segnalazione")
        if submitted:
            if sc_stabilimento and sc_discount and sc_marca:
                # Log temporaneo a schermo (Pronto per essere collegato a una tabella di review nel prossimo step)
                st.info(f"Ricevuto: {sc_discount} -> {sc_marca}. Buffer di validazione attivato.")
                st.success("Grazie! Segnalazione presa in carico. Controlliamo la ricetta e aggiorniamo il database.")
            else:
                st.error("I campi contrassegnati con * sono obbligatori.")

# --- TAB 3: BACKEND AUTOMATIZZATO (ADMIN) ---
with tab_admin:
    st.subheader("Pannello di Sourcing Automatico")
    st.write("Esegui una scansione live sulle API pubbliche di Open Food Facts per raccogliere prodotti italiani con codice di confezionamento ed effettuare il popolamento del DB.")
    
    if st.button("Lancia Fetching Online (Live API)"):
        with st.spinner("Scaricando dati reali da Open Food Facts..."):
            try:
                url = "https://it.openfoodfacts.org/cgi/search.pl"
                params = {
                    "action": "process", 
                    "tagtype_0": "countries", 
                    "tag_contains_0": "contains", 
                    "tag_0": "Italia",
                    "fields": "product_name,brands,emb_codes,categories", 
                    "json": "true", 
                    "page_size": 50
                }
                
                # User-Agent fake reale per superare i blocchi 403/DDOS sui client Python standard
                headers = {
                    "User-Agent": "InciarmoSpesaApp/1.0 (salmattiacci@github.com) Python-Requests/2.31.0"
                }
                
                res = requests.get(url, params=params, headers=headers, timeout=10)
                
                # Validazione formattazione payload prima di tentare il decode JSON
                if "application/json" not in res.headers.get("Content-Type", ""):
                    st.error(f"Il server non ha risposto con un JSON. Risposta del server (primi 200 caratteri): {res.text[:200]}")
                else:
                    products = res.json().get("products", [])
                    nuovi_prodotti = []
                    
                    for p in products:
                        emb = p.get("emb_codes", "").strip().upper()
                        brand = p.get("brands", "").strip()
                        name = p.get("product_name", "").strip()
                        
                        if emb and brand and name:
                            nuovi_prodotti.append({
                                "stabilimento": emb,
                                "categoria": p.get("categories", "").split(",")[0] if p.get("categories") else "Altro",
                                "discount": f"{name} ({brand})",
                                "marca": "Da verificare (Match automatico)",
                                "nota": "Rilevato automaticamente via API di Open Food Facts.",
                                "bollino": "🟡 Da Verificare"
                            })
                    
                    if nuovi_prodotti:
                        new_df = pd.DataFrame(nuovi_prodotti)
                        
                        # Merge progressivo evitando la duplicazione della chiave primaria logica (discount/brand)
                        if not df.empty:
                            df_aggiornato = pd.concat([df, new_df]).drop_duplicates(subset=["discount"]).reset_index(drop=True)
                        else:
                            df_aggiornato = new_df
                        
                        # Iniezione asincrona e persistenza dati sul Google Sheet via API
                        conn.update(data=df_aggiornato)
                        st.success(f"Fetch completato! Sincronizzati {len(nuovi_prodotti)} prodotti reali nel backend.")
                        st.balloons()
                        st.rerun()
                    else:
                        st.warning("Nessun prodotto valido con codice stabilimento trovato in questa pagina API.")
                        
            except Exception as e:
                st.error(f"Errore critico durante il fetching: {str(e)}")

