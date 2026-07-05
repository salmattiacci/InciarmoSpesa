import streamlit as st
import pandas as pd

# 1. Configurazione UI Mobile-First
st.set_page_config(
    page_title="L'Inciarmo della Spesa", 
    page_icon="🛒", 
    layout="centered"
)

st.title("L'Inciarmo della Spesa 🛒")
st.caption("Database Statico ospitato direttamente su GitHub")

# 2. Configura il link del tuo file
# IMPORTANTE: L'URL deve iniziare con 'raw.githubusercontent.com'
GITHUB_RAW_URL = "https://raw.githubusercontent.com/salmattiacci/InciarmoSpesa/main/prodotti.csv"

# Funzione per caricare i dati con cache
@st.cache_data(ttl=60)  # Ricarica automaticamente se modifichi il file su GitHub dopo 1 minuto
def carica_dati_da_github(url):
    try:
        # Pandas è in grado di leggere un CSV direttamente da un URL web
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Impossibile leggere il file dei dati da GitHub: {e}")
        return pd.DataFrame()

# Caricamento del database centralizzato
df_prodotti = carica_dati_da_github(GITHUB_RAW_URL)

# Interfaccia di Ricerca
query = st.text_input("Cerca stabilimento, discount, marca o parola chiave...", placeholder="Es. biscotti, Coop, Eurospin, IT...")

if query:
    if not df_prodotti.empty:
        # Filtro universale su tutte le colonne del file CSV
        mask = df_prodotti.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)
        df_filtrato = df_prodotti[mask]
        
        if not df_filtrato.empty:
            st.subheader(f"📦 Risultati Trovati ({len(df_filtrato)})")
            
            for _, row in df_filtrato.iterrows():
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{row.get('discount', 'N/D')}**")
                        st.markdown(f"💎 *Equivalente a:* **{row.get('marca', 'N/D')}**")
                    with col2:
                        st.caption(f"**{row.get('bollino', '🟡 Da Verificare')}**")
                    st.divider()
                    st.caption(f"🏭 Stabilimento: {row.get('stabilimento', 'N/D')} | Categoria: {row.get('categoria', 'N/D')}")
                    st.write(row.get('nota', ''))
        else:
            st.warning("Nessun inciarmo trovato nel database con questa parola chiave.")
    else:
        st.info("Il database è attualmente vuoto o non raggiungibile.")
else:
    st.info("Digita qualcosa qui sopra per scovare i prodotti gemelli!")
