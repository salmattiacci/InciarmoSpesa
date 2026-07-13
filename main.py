import streamlit as st
import pandas as pd
import os
import re

FILE_CACHE = "prodotti.csv"

# Insegne per mappare i ruoli automaticamente
INSEGNE_SUPERMERCATI = ["eurospin", "conad", "coop", "esselunga", "lidl", "carrefour", "md", "todis", "selex", "pam", "penny", "aldi"]

st.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")

def pulisci_bollino(testo):
    if not testo or pd.isna(testo): return ""
    testo_str = str(testo).upper().strip()
    match = re.search(r'(IT\s*\d+[\s*\/]*\d*\s*CE|\d+[\s*\/]*\d*\s*CE)', testo_str)
    if match:
        return re.sub(r'\s+', '', match.group(1))
    return re.sub(r'[^A-Z0-9]', '', testo_str)[:10]

def inizializza_database_se_vuoto():
    """Crea un database di partenza se il file manca o è completamente vuoto (0 byte)"""
    if not os.path.exists(FILE_CACHE) or os.path.getsize(FILE_CACHE) == 0:
        dati_partenza = [
            {
                "barcode": "8002164000306", # Latte Sterilgarda
                "stabilimento": "IT03171CE",
                "categoria": "Latticini",
                "marca": "Latte Parzialmente Scremato [Sterilgarda]",
                "discount": "Latte Parzialmente Scremato [Conad]",
                "prezzo_marca": "1.45 €",
                "prezzo_discount": "0.99 €",
                "bollino": "🟢 Identico (Fabbrica Sterilgarda SpA)"
            },
            {
                "barcode": "8002000001438", # Tarallucci Mulino Bianco
                "stabilimento": "IT031CE",
                "categoria": "Biscotti",
                "marca": "Tarallucci [Mulino Bianco]",
                "discount": "Frollini all'Uovo [Esselunga]",
                "prezzo_marca": "1.89 €",
                "prezzo_discount": "1.15 €",
                "bollino": "🟢 Identico (Fabbrica Barilla SpA)"
            },
            {
                "barcode": "8000380004141", # Wafer Loacker
                "stabilimento": "BZ014CE",
                "categoria": "Snack",
                "marca": "Wafer Classic [Loacker]",
                "discount": "Wafer Cremkakao [Eurospin / Dolciando]",
                "prezzo_marca": "2.10 €",
                "prezzo_discount": "0.89 €",
                "bollino": "🟢 Identico (Fabbrica Loacker A. SpA)"
            }
        ]
        df = pd.DataFrame(dati_partenza)
        df.to_csv(FILE_CACHE, index=False)

# Inizializza o ripristina il file CSV
inizializza_database_se_vuoto()

# --- INTERFACCIA GRAFICA ---
st.title("L'Inciarmo della Spesa 🛒")
st.subheader("Veri Inciarmi Industriali + Risparmio On-Demand (Database Locale)")

barcode = st.text_input("Scannerizza o digita il codice a barre del prodotto:", placeholder="Es. 8002164000306").strip()

if barcode:
    # Carica il nostro database locale proprietario
    df_db = pd.read_csv(FILE_CACHE)
    df_db['barcode'] = df_db['barcode'].astype(str).str.strip()
    
    # Cerca il prodotto
    match = df_db[df_db['barcode'] == barcode]
    
    if not match.empty:
        # CASO 1: PRODOTTO TROVATO
        risultato = match.iloc[0]
        st.markdown(f"### {risultato['bollino']}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"💸 **Alternativa Discount/Insegna:**\n\n✨ {risultato['discount']}\n\n💰 Prezzo indicativo: **{risultato['prezzo_discount']}**")
        with col2:
            st.warning(f"👑 **Prodotto di Marca Comparato:**\n\n✨ {risultato['marca']}\n\n💰 Prezzo indicativo: **{risultato['prezzo_marca']}**")
            
        st.success(f"🏭 **Codice Stabilimento Unico:** {risultato['stabilimento']}")
    else:
        # CASO 2: PRODOTTO NON TROVATO -> CROWDSOURCING
        st.error("🕵️‍♂️ Inciarmo non ancora censito nel nostro database!")
        st.info("Diventa un ispettore della spesa! Guarda il retro della confezione e inserisci i dati al volo per sbloccare i cloni:")
        
        # Form di inserimento ultra-semplificato
        with st.form("aggiungi_prodotto_form", clear_on_submit=True):
            stabilimento_input = st.text_input("1. Codice Stabilimento (Bollino CE)", placeholder="Es: IT 03 171 CE o IT 03 1 CE").upper().strip()
            nome_prodotto_input = st.text_input("2. Nome del Prodotto + Marchio", placeholder="Es: Frollini Conad o Tarallucci Mulino Bianco")
            categoria_input = st.selectbox("3. Categoria", ["Latticini", "Biscotti e Dolci", "Pasta e Riso", "Sughi e Conserve", "Surgelati", "Altro"])
            prezzo_input = st.text_input("4. Prezzo che vedi a scaffale (Opzionale)", placeholder="Es: 1.20")
            
            submit_button = st.form_submit_with_button_label("Registra Inciarmo e Condividi 🎯")
            
            if submit_button:
                if stabilimento_input and nome_prodotto_input:
                    bollino_pulito = pulisci_bollino(stabilimento_input)
                    
                    # Capisce se è un discount o una marca in base al testo inserito
                    is_discount = any(s in nome_prodotto_input.lower() for s in INSEGNE_SUPERMERCATI)
                    
                    # Controlla se abbiamo già quel bollino registrato da altri per trovare il clone automatico
                    cloni_fabbrica = df_db[df_db['stabilimento'] == bollino_pulito]
                    
                    if not cloni_fabbrica.empty:
                        # Se la fabbrica esiste già, colleghiamo il nuovo prodotto al vecchio
                        record_fabbrica = cloni_fabbrica.iloc[0]
                        nuovo_record = {
                            "barcode": barcode,
                            "stabilimento": bollino_pulito,
                            "categoria": categoria_input,
                            "marca": record_fabbrica['marca'] if is_discount else nome_prodotto_input,
                            "discount": nome_prodotto_input if is_discount else record_fabbrica['discount'],
                            "prezzo_marca": "N/A" if is_discount else f"{prezzo_input} €",
                            "prezzo_discount": f"{prezzo_input} €" if is_discount else "N/A",
                            "bollino": f"🟢 Identico (Fabbrica Collegata: {bollino_pulito})"
                        }
                    else:
                        # Se la fabbrica è nuova, creiamo il primo record della catena
                        nuovo_record = {
                            "barcode": barcode,
                            "stabilimento": bollino_pulito,
                            "categoria": categoria_input,
                            "marca": "In attesa di comparazione" if is_discount else nome_prodotto_input,
                            "discount": nome_prodotto_input if is_discount else "In attesa di comparazione",
                            "prezzo_marca": "N/A" if is_discount else f"{prezzo_input} €",
                            "prezzo_discount": f"{prezzo_input} €" if is_discount else "N/A",
                            "bollino": f"🟡 Fabbrica Censita ({bollino_pulito}) - In attesa di cloni"
                        }
                    
                    # Salva nel CSV locale
                    df_nuovo = pd.DataFrame([nuovo_record])
                    df_aggiornato = pd.concat([df_db, df_nuovo]).drop_duplicates(subset=["barcode"])
                    df_aggiornato.to_csv(FILE_CACHE, index=False)
                    
                    st.balloons()
                    st.success("🎉 Grazie! Prodotto registrato con successo. Digita di nuovo il codice per vedere il risultato aggiornato!")
                else:
                    st.warning("Per favore, compila almeno il Codice Stabilimento e il Nome Prodotto.")
                        
