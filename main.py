import streamlit as st
import pandas as pd

# 1. Configurazione UI Mobile
st.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")
st.title("L'Inciarmo della Spesa 🛒")
st.caption("Database PostgreSQL dinamico dei produttori reali dietro i brand da discount")

# Inizializzazione della variabile di connessione
conn = None

# Inizializzazione Connettore Nativo PostgreSQL
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Impossibile connettersi al database di produzione: {e}")

# Navigazione Tab
tab_cerca, tab_segnala = st.tabs(["🔍 Cerca Prodotti", "📢 Segnala uno Sgamo"])

# --- TAB 1: LETTURA DATI DINAMICI ---
with tab_cerca:
    query = st.text_input("Cerca stabilimento, discount o marca...", placeholder="Es. Eurospin, Conad, IT...")

    # Controlliamo se la connessione è stata stabilita correttamente
    if conn is not None:
        try:
            # Query SQL dinamica (con cache di 10 secondi)
            df = conn.query("SELECT * FROM prodotti;", ttl=10)
            
            if not df.empty:
                if query:
                    mask = df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)
                    df_filtrato = df[mask]
                else:
                    df_filtrato = df

                if df_filtrato.empty:
                    st.warning("Nessun inciarmo trovato. Segnalalo tu!")
                else:
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
                st.info("Database vuoto.")
        except Exception as e:
            st.error(f"Errore di lettura dal database: {e}")
    else:
        st.warning("Funzionalità di ricerca non disponibile: connessione al database assente.")

# --- TAB 2: SCRITTURA DATI REALI ---
with tab_segnala:
    st.subheader("Hai scoperto un nuovo inciarmo?")
    st.caption("Inserisci i dati. Verranno salvati istantaneamente nel database PostgreSQL.")
    
    with st.form("segnalazione_form", clear_on_submit=True):
        sc_stabilimento = st.text_input("Codice Stabilimento / Bollo CE *")
        sc_discount = st.text_input("Prodotto e Supermercato *")
        sc_marca = st.text_input("Prodotto di Marca Equivalente *")
        sc_categoria = st.selectbox("Categoria", ["Latticini", "Dolci", "Snack", "Bevande", "Altro"])
        sc_nota = st.text_area("Note sulla ricetta")
        
        submitted = st.form_submit_button("Invia nel DB Real-Time")
        if submitted:
            if conn is not None:
                if sc_stabilimento and sc_discount and sc_marca:
                    try:
                        with conn.session as session:
                            sql = """
                                INSERT INTO prodotti (stabilimento, categoria, discount, marca, nota, bollino)
                                VALUES (:stabilimento, :categoria, :discount, :marca, :nota, :bollino);
                            """
                            session.execute(
                                sql, 
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
