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
st.caption("Ricerca integrata: Database Postgres (Supabase) + Live API Open Food Facts")

# Inizializzazione della variabile di connessione
conn = None

# Inizializzazione Connettore Nativo PostgreSQL via SQLAlchemy URL
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Impossibile connettersi al database di produzione: {e}")

# Navigazione Tab ottimizzata per smartphone
tab_cerca, tab_segnala = st.tabs(["🔍 Cerca Prodotti", "📢 Segnala uno Sgamo"])

# --- TAB 1: RICERCA LOCALE + ONLINE LIVE ---
with tab_cerca:
    query = st.text_input("Cerca stabilimento, discount, marca o categoria...", placeholder="Es. biscotti, snack, Eurospin, IT...")

    if query:
        # --- FASE 1: RICERCA SUL TUO DB SUPABASE ---
        st.subheader("📦 Risultati dal Database Privato")
        risultati_locali = False
        
        if conn is not None:
            try:
                # Interroghiamo la tabella su Postgres (cache veloce di 5 secondi)
                df = conn.query("SELECT * FROM prodotti;", ttl=5)
                if not df.empty:
                    # Filtro universale sulle colonne del DataFrame
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
            st.info("Nessun match esatto trovato nel database privato. Controllo online sul catalogo aperto...")

        # --- FASE 2: RICERCA LIVE ONLINE (CON DIZIONARIO DI CORREZIONE) ---
        st.subheader("🌐 Risultati in Tempo Reale dal Web")
        with st.spinner("Interrogando Open Food Facts..."):
            try:
                # Pulizia base dell'input utente per l'URL di OFF
                scelta_utente = query.lower().strip().replace(" ", "-")
                
                # Dizionario di mappatura per i termini più comuni verso i tag ufficiali di OFF
                mappa_categorie = {
                    "snack": "snacks",
                    "patatine": "patatine-fritte",
                    "patatina": "patatine-fritte",
                    "merendine": "merendine",
                    "merendina": "merendine",
                    "cioccolato": "cioccolati",
                    "biscotto": "biscotti",
                    "succo": "succhi-di-frutta",
                    "succhi": "succhi-di-frutta",
                    "latte": "latti",
                    "yogurt": "iogurt",
                    "the": "tè",
                    "te": "tè",
                    "pasta": "paste"
                }
                
                # Fallback sulla parola dell'utente se non presente in mappa
                categoria_clean = mappa_categorie.get(scelta_utente, scelta_utente)
                
                url = f"https://it.openfoodfacts.org/categoria/{categoria_clean}.json"
                
                # User-Agent che simula un browser mobile per abbattere i blocchi 403
                headers = {
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
                }
                
                res = requests.get(url, headers=headers, timeout=5)
                
                if res.status_code == 200:
                    data = res.json()
                    products = data.get("products", [])
                    
                    if products:
                        # Mostriamo al massimo i primi 10 risultati live per non saturare lo smartphone
                        for p in products[:10]:
                            name = p.get("product_name", "").strip()
                            brand = p.get("brands", "Brand non specificato").strip()
                            emb = p.get("emb_codes", "").strip().upper()
                            
                            if name:
                                with st.container(border=True):
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.markdown(f"**{name}**")
                                        st.caption(f"Marca/Produttore: *{brand}*")
                                    with col2:
                                        if emb:
                                            st.warning(f"🏭 {emb.split(',')[0]}")
                                        else:
                                            st.caption("❌ No Bollo CE")
                    else:
                        st.warning(f"Nessun prodotto trovato online per la categoria '{categoria_clean}'.")
                elif res.status_code == 404:
                    st.warning(f"La categoria '{categoria_clean}' non è riconosciuta online. Prova con parole plurali o macro-categorie (es. 'biscotti', 'snacks', 'paste').")
                else:
                    st.error(f"Il server di mappatura web ha risposto con codice di errore {res.status_code}.")
                    
            except Exception as e:
                st.error(f"Impossibile completare la ricerca online: {e}")

# --- TAB 2: SCRITTURA DATI REALI (CROWDSOURCING) ---
with tab_segnala:
    st.subheader("Hai scoperto un nuovo inciarmo?")
    st.caption("Inserisci i dati. Verranno salvati istantaneamente nel database PostgreSQL di Supabase.")
    
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
                        # Esecuzione del comando SQL CRUD nativo
                        with conn.session as session:
                            sql = """
                                INSERT INTO prodotti (stabilimento, category, discount, marca, nota, bollino)
                                VALUES (:stabilimento, :categoria, :discount, :marca, :nota, :bollino);
                            """
                            # Nota: Se nel tuo DB la colonna si chiama 'categoria', usa :categoria nel mapping
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

