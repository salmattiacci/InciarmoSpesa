import streamlit as st
import pandas as pd

st.set_page_config(page_title="L'Inciarmo della Spesa v3", page_icon="🛒", layout="centered")
st.title("L'Inciarmo della Spesa 🛒")
st.caption("Database potenziato: Grandi Marche vs Discount + Ricerca EAN/Barcode")

GITHUB_RAW_URL = "https://raw.githubusercontent.com/salmattiacci/InciarmoSpesa/main/prodotti.csv"

@st.cache_data(ttl=10)
def carica_dati(url):
    try:
        return pd.read_csv(url)
    except:
        return pd.DataFrame()

df_prodotti = carica_dati(GITHUB_RAW_URL)

query = st.text_input("Scannerizza il codice a barre o scrivi il prodotto (es. Pan di stelle, Mulino Bianco, Eurospin):", placeholder="Incolla l'EAN o scrivi il nome...")

if not query:
    st.info("💡 Inserisci il nome di un prodotto famoso o il suo codice a barre per scoprire l'alternativa economica.")
    st.stop()

if df_prodotti.empty:
    st.error("Il database si sta aggiornando su GitHub. Attendi un minuto e ricarica.")
    st.stop()

# --- FIX DI SICUREZZA ANTI-KEYERROR ---
for colonna_richiesta in ['discount', 'marca', 'stabilimento', 'barcode_discount', 'barcode_marca', 'bollino', 'categoria', 'nota']:
    if colonna_richiesta not in df_prodotti.columns:
        df_prodotti[colonna_richiesta] = ""

# Ricerca intelligente su tutte le colonne
query_str = str(query).strip()
mask = (
    df_prodotti['discount'].astype(str).str.contains(query_str, case=False) |
    df_prodotti['marca'].astype(str).str.contains(query_str, case=False) |
    df_prodotti['stabilimento'].astype(str).str.contains(query_str, case=False) |
    df_prodotti['barcode_discount'].astype(str).str.contains(query_str, case=False) |
    df_prodotti['barcode_marca'].astype(str).str.contains(query_str, case=False)
)

df_filtrato = df_prodotti[mask]

if df_filtrato.empty:
    st.warning(f"Nessun inciarmo registrato per '{query}'. Stiamo espandendo i controlli industriali.")
    st.stop()

st.subheader(f"🎯 Sgami Rilevati per la tua ricerca ({len(df_filtrato)})")

for _, row in df_filtrato.iterrows():
    bollino = str(row.get('bollino', ''))
    
    if "🟢" in bollino:
        badge = "🟢 EQUIVALENTE PERFETTO (STESSA RICETTA)"
    elif "🟡" in bollino:
        badge = "🟡 RICETTA SIMILE (GEMELLO)"
    else:
        badge = "🟠 SOLO STESSO STABILIMENTO"
        
    with st.container(border=True):
        st.markdown(f"### {badge}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("💸 **L'alternativa economica al Discount:**")
            st.warning(f"✨ {row.get('discount')}")
            b_disc = row.get('barcode_discount', '')
            txt_disc = str(b_disc) if pd.notna(b_disc) and b_disc != '' else 'Non mappato'
            st.caption(f"Code: {txt_disc}")
            
        with col2:
            st.markdown("👑 **Il Prodotto Originale di Marca:**")
            st.info(f"✨ {row.get('marca')}")
            b_marca = row.get('barcode_marca', '')
            txt_marca = str(b_marca) if pd.notna(b_marca) and b_marca != '' else 'Non mappato'
            st.caption(f"Code: {txt_marca}")
            
        st.divider()
        st.caption(f"🏭 **Fabbricati entrambi a:** `{row.get('stabilimento', 'N/D')}` | Categoria: {row.get('categoria', 'Altro')}")
        st.write(f"📋 **Esito dell'algoritmo:** {row.get('nota', '')}")
        
