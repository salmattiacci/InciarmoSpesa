import streamlit as st
import pandas as pd

st.set_page_config(page_title="L'Inciarmo della Spesa v3", page_icon="🛒", layout="centered")
st.title("L'Inciarmo della Spesa 🛒")
st.caption("Confronto Specifico: Marca vs Discount + Scanner Fotografico")

GITHUB_RAW_URL = "https://raw.githubusercontent.com/salmattiacci/InciarmoSpesa/main/prodotti.csv"

@st.cache_data(ttl=60)
def carica_dati(url):
    try:
        return pd.read_csv(url)
    except:
        return pd.DataFrame()

df_prodotti = carica_dati(GITHUB_RAW_URL)

# --- NUOVA FUNZIONE: SCANNER DA CELLULARE ---
st.subheader("📸 Scansiona o Digita")
usa_foto = st.toggle("Attiva Fotocamera per Codice a Barre / Bollo")

query = ""
if usa_foto:
    foto_catturata = st.camera_input("Inquadra il codice o lo stabilimento sul prodotto")
    if foto_catturata:
        st.info("Foto acquisita! Nota: Per estrarre il testo dalle foto in automatico servirà un modulo OCR, per ora inserisci il testo o usa la ricerca manuale qui sotto.")

# Campo di ricerca manuale (funziona sempre come fallback principale)
query_manuale = st.text_input("Inserisci Codice a Barre, Parola Chiave o Stabilimento CE:", placeholder="Es. 800123456789, biscotti, IT 03 3 CE...")

# Scegliamo quale query usare
if query_manuale:
    query = query_manuale

# Se non c'è testo da cercare, ci fermiamo qui
if not query:
    st.info("Usa la tastiera o la fotocamera per scovare i prodotti gemelli!")
    st.stop()

if df_prodotti.empty:
    st.error("Il database è in fase di caricamento. Attendi la sincronizzazione di GitHub.")
    st.stop()

# --- RICERCA E CORRISPONDENZA SPECIFICA ---
mask = df_prodotti.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)
df_filtrato = df_prodotti[mask]

if df_filtrato.empty:
    st.warning(f"Nessun match trovato per '{query}'. L'algoritmo sta raccogliendo nuovi dati.")
    st.stop()

st.subheader(f"🔍 Risultati Specifici Trovati ({len(df_filtrato)})")

for _, row in df_filtrato.iterrows():
    bollino = str(row.get('bollino', ''))
    
    # Colore visivo del livello di somiglianza degli ingredienti
    if "🟢" in bollino:
        colore_box = "success"
        badge = "🟢 RICETTA IDENTICA"
    elif "🟡" in bollino:
        colore_box = "warning"
        badge = "🟡 RICETTA SIMILE (GEMELLO)"
    else:
        colore_box = "normal"
        badge = "🟠 STESSA FABBRICA, RICETTA DIVERSA"
        
    with st.container(border=True):
        st.markdown(f"### {badge}")
        
        # Mappatura Specifica: Chi produce per chi
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("🏭 **Fabbricato da (Grande Marca):**")
            st.code(row.get('marca', 'N/D'))
        with col2:
            st.markdown("🏪 **Venduto come (Alternativa Economica):**")
            st.code(row.get('discount', 'N/D'))
            
        st.divider()
        st.caption(f"📍 **Stabilimento d'Origine:** `{row.get('stabilimento', 'N/D')}`")
        st.write(f"ℹ️ **Analisi Fabbrica:** {row.get('nota', '')}")
