import streamlit as st
import pandas as pd

st.set_page_config(page_title="L'Inciarmo della Spesa v2", page_icon="🛒", layout="centered")
st.title("L'Inciarmo della Spesa 🛒")
st.caption("Algoritmo di match per Stabilimento + Analisi Molecolare degli Ingredienti")

GITHUB_RAW_URL = "https://raw.githubusercontent.com/salmattiacci/InciarmoSpesa/main/prodotti.csv"

@st.cache_data(ttl=60)
def carica_dati(url):
    try:
        return pd.read_csv(url)
    except:
        return pd.DataFrame()

df_prodotti = carica_dati(GITHUB_RAW_URL)

query = st.text_input("Cerca un prodotto, una marca o un codice stabilimento...", placeholder="Es. biscotti, Coop, Conad, IT...")

# Se l'utente non ha cercato nulla, mostriamo l'info e fermiamo l'esecuzione dello script
if not query:
    st.info("Digita qualcosa qui sopra per scovare i prodotti gemelli!")
    st.stop()

# Se il database è vuoto, mostriamo l'errore e fermiamo lo script
if df_prodotti.empty:
    st.error("Il database è attualmente vuoto o non raggiungibile su GitHub. Attendi la sincronizzazione.")
    st.stop()

# --- DA QUI IN POI ESEGUIAMO LA RICERCA (Logica piatta senza ELSE annidati) ---
mask = df_prodotti.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)
df_filtrato = df_prodotti[mask]

if df_filtrato.empty:
    st.warning("Nessun incrocio trovato con questa parola chiave. L'algoritmo sta espandendo il database...")
    st.stop()

st.subheader(f"🔍 Sgami Rilevati ({len(df_filtrato)})")

for _, row in df_filtrato.iterrows():
    bollino = str(row.get('bollino', ''))
    
    if "🟢" in bollino:
        border_color = "🟢"
    elif "🟡" in bollino:
        border_color = "🟡"
    else:
        border_color = "🟠"
        
    with st.container(border=True):
        st.markdown(f"### {border_color} {row.get('bollino', 'Analizzato')}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.error("**Prodotto A:**")
            st.write(row.get('discount', 'N/D'))
        with col2:
            st.success("**Prodotto B:**")
            st.write(row.get('marca', 'N/D'))
            
        st.divider()
        st.caption(f"🏭 **Bollo CE di provenienza:** `{row.get('stabilimento', 'N/D')}` | Categoria: {row.get('categoria', 'Altro')}")
        st.info(f"📋 **Esito Analisi:** {row.get('nota', '')}")
