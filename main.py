import streamlit as st
import pandas as pd
import requests

# 1. Configurazione UI Mobile-First
st.set_page_config(
    page_title="L'Inciarmo della Spesa", 
    page_icon="🛒", 
    layout="centered"
)

st.title("L'Inciarmo della Spesa 🛒")
st.caption("Ricerca integrata: Database Postgres (Supabase) + Doppia API Open Food Facts con Failover")

# Inizializzazione della variabile di connessione Postgres
conn = None

# Connessione nativa a Supabase via stringa URL nei Secrets
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Impossibile connettersi al database di produzione: {e}")

# Navigazione Tab ottimizzata per smartphone
tab_cerca, tab_segnala = st.tabs(["🔍 Cerca Prodotti", "📢 Segnala uno Sgamo"])

# --- TAB 1: RICERCA IBRIDA (LOCALE + WEB LIVE CON CONTROMISURE) ---
with tab_cerca:
    query = st.text_input("Cerca stabilimento, discount, marca o parola chiave...", placeholder="Es. biscotti, Coop, Eurospin, IT 03 3 CE...")

    if query:
        # --- FASE 1: RICERCA SUL TUO DB SUPABASE ---
        st.subheader("📦 Risultati dal Database Privato")
        risultati_locali = False
        
        if conn is not None:
            try:
                df = conn.query("SELECT * FROM prodotti;", ttl=5)
                if not df.empty:
                    mask = df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)
                    df_filtrato = df[mask]
                    
                    if not df_filtrato.empty:
                        risultati_locali = True
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
            except Exception as e:
                st.error(f"Errore lettura DB locale: {e}")
        
        if not risultati_locali:
            st.info("Nessun match nel database privato. Controllo online sul database mondiale...")

        # --- FASE 2: RICERCA LIBERA LIVE ONLINE CON SISTEMA DI FAILOVER ANTI-BLOCCO ---
        st.subheader("🌐 Risultati in Tempo Reale dal Web")
        with st.spinner(f"Ricerca di '{query}' su Open Food Facts..."):
            try:
                # 1. Tentativo standard con API v2 (Endpoint moderno)
                url_v2 = "https://it.openfoodfacts.org/api/v2/search"
                params_v2 = {
                    "search_terms": query,
                    "search_simple": "1",
                    "action": "process",
                    "fields": "product_name,brands,emb_codes",
                    "page_size": 10,
                    "cc": "it",
                    "lc": "it"
                }
                headers_v2 = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json"
                }
                
                res = requests.get(url_v2, params=params_v2, headers=headers_v2, timeout=4)
                
                # Se l'endpoint moderno risponde correttamente, mostriamo i dati
                if res.status_code == 200:
                    data = res.json()
                    products = data.get("products", [])
                    
                    if products:
                        for p in products:
                            name = p.get("product_name", "").strip()
                            brand = p.get("brands", "Marca non specificata").strip()
                            emb = p.get("emb_codes", "").strip().upper()
                            if name:
                                with st.container(border=True):
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.markdown(f"**{name}**")
                                        st.caption(f"Marca: *{brand}*")
                                    with col2:
                                        if emb:
                                            st.warning(f"🏭 {emb.split(',')[0].replace('EMB', '').strip()}")
                                        else:
                                            st.caption("❌ No Bollo")
                    else:
                        st.warning("Nessun riscontro trovato online.")
                
                # 2. SE DA 503/403, SCATTA IL FAILOVER SULL'ENDPOINT LEGACY (Cluster Server Diversificato)
                else:
                    st.warning("⚠️ Endpoint principale limitato dal Cloud. Tento il recupero dal canale secondario...")
                    
                    # Costruiamo la query per il vecchio script CGI che bypassa i blocchi standard della v2
                    url_legacy = f"https://it.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1&page_size=10"
                    
                    res_legacy = requests.get(url_legacy, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"}, timeout=5)
                    
                    if res_legacy.status_code == 200:
                        data_legacy = res_legacy.json()
                        products_legacy = data_legacy.get("products", [])
                        
                        if products_legacy:
                            for p in products_legacy:
                                name = p.get("product_name", "").strip()
                                brand = p.get("brands", "Marca non specificata").strip()
                                emb = p.get("emb_codes", "").strip().upper()
                                if name:
                                    with st.container(border=True):
                                        col1, col2 = st.columns([3, 1])
                                        with col1:
                                            st.markdown(f"**{name}** *(via Canale di Backup)*")
                                            st.caption(f"Marca: *{brand}*")
                                        with col2:
                                            if emb:
                                                st.warning(f"🏭 {emb.split(',')[0].replace('EMB', '').strip()}")
                                            else:
                                                st.caption("❌ No Bollo")
                        else:
                            st.warning("Nessun riscontro trovato nel canale di backup.")
                    else:
                        st.error(f"I server cloud di Streamlit sono completamente bloccati (Codice {res_legacy.status_code}). Esegui l'app localmente da Termux per sbloccarla con il tuo IP.")
                        
            except Exception as e:
                st.error(f"Errore di rete durante la connessione web: {e}")

# --- TAB 2: SCRITTURA DATI REALI (CROWDSOURCING) ---
with tab_segnala:
    st.subheader("Hai scoperto un nuovo inciarmo?")
    st.caption("Inserisci i dati per salvarli istantaneamente nel database PostgreSQL di Supabase.")
    
    with st.form("segnalazione_form", clear_on_submit=True):
        sc_stabilimento = st.text_input("Codice Stabilimento / Bollo CE *", placeholder="Es. IT 03 3 CE")
        sc_discount = st.text_input("Prodotto e Supermercato *", placeholder="Es. Frollini con panna Eurospin")
        sc_marca = st.text_input("Prodotto di Marca Equivalente *", placeholder="Es. Tarallucci Mulino Bianco")
        sc_categoria = st.selectbox("Categoria", ["Latticini", "Dolci", "Snack", "Bevande", "Altro"])
        sc_nota = st.text_area("Note sulla ricetta")
        
        submitted = st.form_submit_button("Invia nel DB Real-Time")
        if submitted:
            if conn is not None:
                if sc_stabilimento and sc_discount and sc_marca:
                    try:
                        with conn.session as session:
                            sql_corretto = """
                                INSERT INTO prodotti (stabilimento, categoria, discount, marca, nota, bollino)
                                VALUES (:stabilimento, :categoria, :discount, :marca, :nota, :bollino);
                            """
                            session.execute(
                                sql_corretto, 
                                {
                                    "stabilimento": sc_stabilimento, 
                                    "categoria": sc_categoria, 
                                    "discount": sc_discount, 
                                    "marca": sc_marca, 
                                    "nota": sc_nota, 
                                    "bollino": "🟡 Da Verificare"
                                }
                            )
                            session.commit()
                        st.success("Sgamo registrato con successo nel database di Supabase!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Errore durante la scrittura sul DB: {e}")
                else:
                    st.error("I campi contrassegnati con * sono obbligatori.")
            else:
                st.error("Impossibile inviare la segnalazione: database non connesso.")
