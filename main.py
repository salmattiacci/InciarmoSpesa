import streamlit as st
import pandas as pd

st.set_page_config(page_title="L'Inciarmo della Spesa v4", page_icon="🛒", layout="centered")
st.title("L'Inciarmo della Spesa 🛒")
st.caption("Veri Inciarmi Industriali + Confronto Prezzi & Risparmio")

GITHUB_RAW_URL = "https://raw.githubusercontent.com/salmattiacci/InciarmoSpesa/main/prodotti.csv"

@st.cache_data(ttl=10)
def carica_dati(url):
    try:
        return pd.read_csv(url)
    except:
        return pd.DataFrame()

df_prodotti = carica_dati(GITHUB_RAW_URL)

query = st.text_input("Scannerizza il codice a barre o scrivi il prodotto:", placeholder="Es. Pan di Stelle, 8076809580755...")

if not query:
    st.info("💡 Inserisci il nome del brand o il codice a barre per calcolare lo sgamo ed il risparmio.")
    st.stop()

if df_prodotti.empty:
    st.error("Database in aggiornamento su GitHub. Riprova tra un istante.")
    st.stop()

# Configurazione colonne di sicurezza
for col in ['discount', 'marca', 'stabilimento', 'barcode_discount', 'barcode_marca', 'prezzo_discount', 'prezzo_marca', 'bollino', 'nota']:
    if col not in df_prodotti.columns:
        df_prodotti[col] = "N/D"

query_str = str(query).strip()
mask = (
    df_prodotti['discount'].astype(str).str.contains(query_str, case=False) |
    df_prodotti['marca'].astype(str).str.contains(query_str, case=False) |
    df_prodotti['barcode_discount'].astype(str).str.contains(query_str, case=False) |
    df_prodotti['barcode_marca'].astype(str).str.contains(query_str, case=False)
)

df_filtrato = df_prodotti[mask]

if df_filtrato.empty:
    st.warning(f"Nessun inciarmo sicuro trovato per '{query}'.")
    st.stop()

st.subheader(f"🎯 Sgami Verificati ({len(df_filtrato)})")

for _, row in df_filtrato.iterrows():
    bollino = str(row.get('bollino', ''))
    
    if "🟢" in bollino:
        badge = "🟢 STESSA RICETTA (IDENTICO)"
    elif "🟡" in bollino:
        badge = "🟡 RICETTA SIMILE (GEMELLO)"
    else:
        badge = "🟠 SOLO STESSA FABBRICA"
        
    with st.container(border=True):
        st.markdown(f"### {badge}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("💸 **Alternativa Discount:**")
            st.warning(f"✨ {row.get('discount')}")
            p_disc = row.get('prezzo_discount', 'N/D')
            prezzo_d_testo = f"{p_disc}€" if p_disc != "nan" and p_disc != "N/D" else "Prezzo n.d."
            st.markdown(f"💰 **Prezzo stimato:** `{prezzo_d_testo}`")
            
        with col2:
            st.markdown("👑 **Prodotto di Marca:**")
            st.info(f"✨ {row.get('marca')}")
            p_marca = row.get('prezzo_marca', 'N/D')
            prezzo_m_testo = f"{p_marca}€" if p_marca != "nan" and p_marca != "N/D" else "Prezzo n.d."
            st.markdown(f"💰 **Prezzo originale:** `{prezzo_m_testo}`")
            
        # Calcolo del risparmio se i prezzi ci sono
        try:
            if p_disc != "nan" and p_marca != "nan" and p_disc != "N/D" and p_marca != "N/D":
                risparmio = float(p_marca) - float(p_disc)
                if risparmio > 0:
                    st.success(f"🤑 Sgamo totale: Stai risparmiando **{risparmio:.2f}€** su questa confezione!")
        except:
            pass
            
        st.divider()
        st.caption(f"🏭 **Codice Stabilimento Unico:** `{row.get('stabilimento')}`")
        st.caption(f"📋 **Nota d'ispezione:** {row.get('nota')}")
