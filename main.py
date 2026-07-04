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
st.caption("Ricerca integrata: Database Postgres (Supabase) + Live API Open Food Facts (Bypass Cloud)")

# Inizializzazione della variabile di connessione Postgres
conn = None

# Connessione nativa a Supabase via SQLAlchemy stringa URL
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Impossibile connettersi al database di produzione: {e}")

# Navigazione Tab per smartphone
tab_cerca, tab_segnala = st.tabs(["🔍 Cerca Prodotti", "📢 Segnala uno Sgamo"])

# --- TAB 1: RICERCA IBRIDA (LOCALE + WEB LIVE) ---
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

        # --- FASE 2: RICERCA TESTUALE LIBERA LIVE ONLINE (Sintassi testata su Termux) ---
        st.subheader("🌐 Risultati in Tempo Reale dal Web")
        with st.spinner(f"Ricerca di '{query}' su Open Food Facts..."):
            try:
                url = "https://it.openfoodfacts.org/api/v2/search"
                
                # Parametri ottimizzati e geolocalizzati per evitare sovraccarichi
                params = {
                    "search_terms": query,
                    "search_simple": "1",
                    "action": "process",
                    "fields": "product_name,brands,emb_codes",
                    "page_size": 12,
                    "cc": "it",  # Forza il database italiano
                    "lc": "it"   # Forza la lingua italiana
                }
                
                # L'User-Agent identico a quello che ha risposto con successo su Termux
                headers = {
                    "User-Agent": "InciarmoSpesaApp/1.0 (Contatto: salmattiacci@github.com)"
                }
                
                res = requests.get(url, params=params, headers=headers, timeout=6)
                
                if res.status_code == 200:
                    data = res.json()
                    products = data.get("products", [])
                    
                    if products:
                        prodotti_validi = 0
                        for p in products:
                            name = p.get("product_name", "").strip()
                            brand = p.get("brands", "Marca non specificata").strip()
                            emb = p.get("emb_codes", "").strip().upper()
                            
                            if name:
                                prodotti_validi += 1
                                with st.container(border=True):
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.markdown(f"**{name}**")
                                        st.caption(f"Marca dichiarata: *{brand}*")
                                    with col2:
                                        if emb:
                                            # Isola il primo bollo CE utile e pulisce la stringa
                                            emb_clean = emb.split(",")[0].replace("EMB", "").strip()
                                            st.warning(f"🏭 {emb_clean}")
                                        else:
                                            st.caption("❌ No Bollo CE")
                        
                        if prodotti_validi == 0:
                            st.warning("Nessun prodotto valido con nome trovato online.")
                    else:
                        st.warning("Nessun riscontro trovato online. Prova a cambiare parole chiave.")
                else:
                    st.error(f"Il server remoto ha risposto con codice {res.status_code}. I server cloud sono temporaneamente limitati dal firewall di Open Food Facts.")
                    
            except Exception as e:
                st.error(f"Errore di rete durante la ricerca online: {e}")

# --- TAB 2: SCRITTURA DATI REALI (CROWDSOURCING) ---
with tab_segnala:
    st.subheader("Hai scoperto un nuovo inciarmo?")
    st.caption("Inserisci i dati per salvarli istantaneamente nel database PostgreSQL di Supabase.")
    
    with st.form("segnalazione_form", clear_on_submit=True):
        sc_stabilimento = st.text_input("Codice Stabilimento / Bollo CE *", placeholder="Es. IT 03 3 CE")
        sc_discount = st.text_input("Prodotto e Supermercato *", placeholder="Es. Frollini con panna Eurospin")
        sc_marca = st.text_input("Prodotto di Marca Equivalente *", placeholder="Es. Tarallucci Mulino Bianco")
        sc_categoria = st.selectbox("Categoria", ["Latticini", "Dolci", "Snack", "Bevande", "Altro"])
        sc_nota = st.text_area("Note sulla ricetta (ingredienti, sapore...)")
        
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
