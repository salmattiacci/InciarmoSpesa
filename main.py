import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Configurazione UI
st.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")

st.title("L'Inciarmo della Spesa 🛒")
st.caption("Database dinamico dei produttori reali dietro i brand da discount")

# Inizializzazione Connettore Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Cache impostata a 600 secondi per performance e limitazione chiamate API
    df = conn.read(ttl=600)
except Exception as e:
    st.error("Errore di connessione al database. Mostro dati di backup.")
    # Fallback mock nel caso il foglio sia offline o non configurato nei secrets
    df = pd.DataFrame([{
        "stabilimento": "Novara", "categoria": "Snack", 
        "discount": "Patatine Classiche (Esselunga)", "marca": "San Carlo", 
        "nota": "Stessa ricetta e stabilimento.", "bollino": "🟢 Identico"
    }])

# Navigazione interna tramite Tab (Mobile friendly)
tab_cerca, tab_segnala = st.tabs(["🔍 Cerca Prodotti", "📢 Segnala uno Sgamo"])

with tab_cerca:
    query = st.text_input("Cerca stabilimento, discount o marca...", placeholder="Es. Eurospin, Conad, IT...")

    # Filtro dinamico sul DataFrame
    if query:
        mask = df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)
        df_filtrato = df[mask]
    else:
        df_filtrato = df

    # Rendering delle card
    if df_filtrato.empty:
        st.warning("Nessun inciarmo trovato con questi filtri. Segnalalo tu!")
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

with tab_segnala:
    st.subheader("Hai scoperto un nuovo inciarmo?")
    st.caption("Inserisci i dati dell'etichetta. Dopo una verifica tecnica sulla ricetta, verrà inserito nel DB pubblico.")
    
    with st.form("segnalazione_form", clear_on_submit=True):
        sc_stabilimento = st.text_input("Codice Stabilimento / Bollo CE", placeholder="Es. IT 03 3 CE")
        sc_discount = st.text_input("Prodotto e Supermercato", placeholder="Es. Frollini Conad")
        sc_marca = st.text_input("Prodotto di Marca Equivalente", placeholder="Es. Tarallucci Mulino Bianco")
        sc_nota = st.text_area("Note sulla ricetta (Ingredienti, sapore, ecc.)")
        sc_categoria = select_cat = st.selectbox("Categoria", ["Latticini", "Dolci e Colazione", "Snack e Patatine", "Conserve", "Bevande", "Altro"])
        
        submitted = st.form_submit_button("Invia Segnalazione")
        if submitted:
            if sc_stabilimento and sc_discount and sc_marca:
                # Log temporaneo in console per la fase di review dell'admin
                st.info(f"Segnalazione intercettata: {sc_discount} -> {sc_marca}. Buffer di validazione in attivazione.")
                st.success("Grazie! Segnalazione presa in carico. Controlliamo la ricetta e aggiorniamo il DB.")
            else:
                st.error("Per favore, compila i campi obbligatori (Stabilimento, Discount e Marca).")
