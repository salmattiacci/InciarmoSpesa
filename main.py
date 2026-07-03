import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests

st.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")

st.title("L'Inciarmo della Spesa 🛒")

# 1. Connessione al DB (Google Sheets)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=60) # Cache ridotta a 1 minuto per vedere subito i dati fetchati
except Exception as e:
    st.error("Errore di connessione al database.")
    df = pd.DataFrame()

# 2. Definizione dei Tab
tab_cerca, tab_segnala, tab_admin = st.tabs(["🔍 Cerca", "📢 Segnala", "⚙️ Sincronizza Dati"])

with tab_cerca:
    # ... (Il codice di ricerca rimane identico a prima)
    query = st.text_input("Cerca stabilimento, discount o marca...")
    if not df.empty:
        mask = df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1) if query else [True]*len(df)
        for _, row in df[mask].iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['discount']}** ➡️ 💎 **{row['marca']}**")
                st.caption(f"🏭 Stabilimento: {row['stabilimento']} | {row['bollino']}")

with tab_segnala:
    # ... (Il form di segnalazione utenti rimane identico a prima)
    st.write("Form di segnalazione")

# 3. NUOVO TAB: FUNZIONE DI FETCH DALL'APP
with tab_admin:
    st.subheader("Pannello di Sourcing Automatico")
    st.write("Cliccando il bottone, l'app interrogherà le API di Open Food Facts, troverà i prodotti italiani con lo stesso stabilimento ma brand diversi e li salverà nel DB.")
    
    if st.button("Lancia Fetching Online (Live API)"):
        with st.spinner("Scaricando dati reali da Open Food Facts..."):
            try:
                # Chiamata API per raccogliere un sample di prodotti italiani
                url = "https://it.openfoodfacts.org/cgi/search.pl"
                params = {
                    "action": "process", "tagtype_0": "countries", "tag_contains_0": "contains", "tag_0": "Italia",
                    "fields": "product_name,brands,emb_codes,categories", "json": "true", "page_size": 50
                }
                res = requests.get(url, params=params, timeout=10)
                products = res.json().get("products", [])
                
                nuovi_prodotti = []
                for p in products:
                    emb = p.get("emb_codes", "").strip().upper()
                    brand = p.get("brands", "").strip()
                    name = p.get("product_name", "").strip()
                    
                    if emb and brand and name:
                        # Qui l'algoritmo dovrebbe fare il matching. Per l'MVP inseriamo i dati grezzi puliti
                        nuovi_prodotti.append({
                            "stabilimento": emb,
                            "categoria": p.get("categories", "").split(",")[0] if p.get("categories") else "Altro",
                            "discount": f"{name} ({brand})",
                            "marca": "Da verificare (Match automatico)",
                            "nota": "Rilevato automaticamente via API.",
                            "bollino": "🟡 Da Verificare"
                        })
                
                if nuovi_prodotti:
                    new_df = pd.DataFrame(nuovi_prodotti)
                    # Uniamo i vecchi dati con i nuovi per evitare duplicati sullo stabilimento
                    df_aggiornato = pd.concat([df, new_df]).drop_duplicates(subset=["discount"]).reset_index(drop=True)
                    
                    # SCRITTURA DIRETTA SUL GOOGLE SHEET
                    conn.update(data=df_aggiornato)
                    st.success(f"Fetch completato! Sincronizzati {len(nuovi_prodotti)} prodotti reali nel backend.")
                    st.balloons()
                else:
                    st.warning("Nessun dato utile trovato in questo slot di pagine API.")
                    
            except Exception as e:
                st.error(f"Errore durante il fetching: {str(e)}")
