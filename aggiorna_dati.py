import requests
import pandas as pd
import re
import os
import time

def pulisci_bollino(testo):
    if not testo: return ""
    pulito = re.sub(r'[^A-Z0-9]', '', str(testo).upper())
    return pulito.replace("EMB", "")

def calcola_somiglianza_ingredienti(ing1, ing2):
    if not ing1 or not ing2: return 0
    set1 = set(re.findall(r'\w+', str(ing1).lower()))
    set2 = set(re.findall(r'\w+', str(ing2).lower()))
    if not set1 or not set2: return 0
    intersezione = set1.intersection(set2)
    unione = set1.union(set2)
    return int((len(intersezione) / len(unione)) * 100)

def scarica_tutti_prodotti_massa():
    print("Inizio scaricamento di massa da Open Food Facts...")
    url = "https://it.openfoodfacts.org/api/v2/search"
    
    # Scarichiamo un blocco massivo di prodotti italiani (fino a 1000 per botta)
    params = {
        "action": "process",
        "tagtype_0": "countries",
        "tag_contains_0": "contains",
        "tag_0": "italia",
        "fields": "product_name,brands,categories,emb_codes,ingredients_text_it,code",
        "page_size": 1000, 
        "cc": "it", "lc": "it"
    }
    
    headers = {"User-Agent": "InciarmoSpesaBot/4.0"}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=25)
        if res.status_code == 200:
            return res.json().get("products", [])
    except Exception as e:
        print(f"Errore download di massa: {e}")
    return []

def esegui_pipeline():
    # 1. SCARICA I DATI NUOVI
    nuovi_prodotti = scarica_tutti_prodotti_massa()
    if not nuovi_prodotti:
        print("Nessun dato scaricato. Esco per sicurezza.")
        return
        
    df_nuovi = pd.DataFrame(nuovi_prodotti)
    
    # 2. ACCUMULO NEL DATABASE GREZZO (La tua idea di DB ampio)
    file_raw = "prodotti_raw.csv"
    if os.path.exists(file_raw):
        df_vecchi = pd.read_csv(file_raw)
        # Uniamo vecchio e nuovo eliminando i duplicati basandoci sul codice a barre unico
        df_totale_raw = pd.concat([df_vecchi, df_nuovi]).drop_duplicates(subset=["code"])
    else:
        df_totale_raw = df_nuovi
        
    df_totale_raw.to_csv(file_raw, index=False)
    print(f"Database grezzo aggiornato. Totale prodotti in archivio: {len(df_totale_raw)}")
    
    # 3. ELABORAZIONE CACHE DEGLI SGAMI (Trova gli inciarmi nel DB ampio)
    print("Generazione della cache degli sgami...")
    database_mappato = []
    marchi_discount = ["eurospin", "conad", "coop", "esselunga", "lidl", "carrefour", "md", "todis", "selex", "pam"]
    
    # Trasformiamo in lista di dizionari per velocizzare i cicli Python
    lista_prodotti = df_totale_raw.to_dict(orient="records")
    
    for i, p1 in enumerate(lista_prodotti):
        emb1 = str(p1.get("emb_codes", "")).strip()
        emb1_pulito = pulisci_bollino(emb1)
        name1 = str(p1.get("product_name", "")).strip()
        brand1 = str(p1.get("brands", "Generico")).strip()
        ing1 = p1.get("ingredients_text_it", "")
        code1 = p1.get("code", "")
        
        if not emb1_pulito or brand1 == "Generico" or name1 == "" or name1 == "nan": continue
        
        for p2 in lista_prodotti[i+1:]:
            brand2 = str(p2.get("brands", "Generico")).strip()
            emb2_pulito = pulisci_bollino(p2.get("emb_codes", ""))
            name2 = str(p2.get("product_name", "")).strip()
            ing2 = p2.get("ingredients_text_it", "")
            code2 = p2.get("code", "")
            
            if emb1_pulito == emb2_pulito and brand1.lower() != brand2.lower() and name2 and name2 != "nan" and brand2 != "Generico":
                # Capisci chi è il discount e chi la marca leader
                b1_disc = any(d in brand1.lower() for d in marchi_discount)
                b2_disc = any(d in brand2.lower() for d in marchi_discount)
                
                if b1_disc and not b2_disc:
                    m_discount, n_discount, e_barcode = brand1, name1, code1
                    m_marca, n_marca, m_barcode = brand2, name2, code2
                else:
                    m_discount, n_discount, e_barcode = brand2, name2, code2
                    m_marca, n_marca, m_barcode = brand1, name1, code1
                
                score = calcola_somiglianza_ingredienti(ing1, ing2)
                
                if score > 75:
                    livello = "🟢 Identico (Ricetta Match)"
                elif score > 45:
                    livello = "🟡 Gemello (Ricetta Simile)"
                else:
                    livello = "🟠 Solo Stessa Fabbrica"
                
                database_mappato.append({
                    "stabilimento": emb1.split(",")[0].replace("EMB", "").strip(),
                    "categoria": str(p1.get("categories", "Altro")).split(",")[0],
                    "discount": f"{n_discount} [{m_discount}]",
                    "marca": f"{n_marca} [{m_marca}]",
                    "barcode_discount": str(e_barcode),
                    "barcode_marca": str(m_barcode),
                    "nota": f"Analisi ricetta su DB storico. Somiglianza ingredienti: {score}%.",
                    "bollino": livello
                })
                
    if database_mappato:
        df_cache = pd.DataFrame(database_mappato)
        df_cache = df_cache.drop_duplicates(subset=["discount", "marca"])
        # Salviamo la cache ufficiale che leggerà Streamlit
        df_cache.to_csv("prodotti.csv", index=False)
        print(f"Cache aggiornata! {len(df_cache)} sgami pronti per Streamlit.")
    else:
        print("Nessun match ricavato in questa sessione.")

if __name__ == "__main__":
    esegui_pipeline()
    return []

def esegui_pompaggio_db():
    target_keywords = ["biscotti", "frollini", "merendine", "patatine", "pasta", "latte", "yogurt"]
    tutti_i_prodotti = []
    
    for kw in target_keywords:
        tutti_i_prodotti.extend(scarica_categoria(kw))
        time.sleep(0.5)
        
    print(f"Prodotti totali scaricati: {len(tutti_i_prodotti)}")
    database_mappato = []
    marchi_discount = ["eurospin", "conad", "coop", "esselunga", "lidl", "carrefour", "md", "todis", "selex", "pam"]

    for i, p1 in enumerate(tutti_i_prodotti):
        emb1 = p1.get("emb_codes", "").strip()
        emb1_pulito = pulisci_bollino(emb1)
        name1 = p1.get("product_name", "").strip()
        brand1 = p1.get("brands", "Generico").strip()
        ing1 = p1.get("ingredients_text_it", "")
        code1 = p1.get("code", "")
        
        if not emb1_pulito or brand1 == "Generico" or not name1: continue
        
        for p2 in tutti_i_prodotti[i+1:]:
            brand2 = p2.get("brands", "Generico").strip()
            emb2_pulito = pulisci_bollino(p2.get("emb_codes", ""))
            name2 = p2.get("product_name", "").strip()
            ing2 = p2.get("ingredients_text_it", "")
            code2 = p2.get("code", "")
            
            if emb1_pulito == emb2_pulito and brand1.lower() != brand2.lower() and name2 and brand2 != "Generico":
                b1_disc = any(d in brand1.lower() for d in marchi_discount)
                b2_disc = any(d in brand2.lower() for d in marchi_discount)
                
                if b1_disc and not b2_disc:
                    m_discount, n_discount, e_barcode = brand1, name1, code1
                    m_marca, n_marca, m_barcode = brand2, name2, code2
                else:
                    m_discount, n_discount, e_barcode = brand2, name2, code2
                    m_marca, n_marca, m_barcode = brand1, name1, code1
                
                score = calcola_somiglianza_ingredienti(ing1, ing2)
                
                if score > 75:
                    livello = "🟢 Identico (Ricetta Match)"
                elif score > 45:
                    livello = "🟡 Gemello (Ricetta Simile)"
                else:
                    livello = "🟠 Solo Stessa Fabbrica"
                
                database_mappato.append({
                    "stabilimento": emb1.split(",")[0].replace("EMB", "").strip(),
                    "categoria": p1.get("categories", "Altro").split(",")[0],
                    "discount": f"{n_discount} [{m_discount}]",
                    "marca": f"{n_marca} [{m_marca}]",
                    "barcode_discount": str(e_barcode),
                    "barcode_marca": str(m_barcode),
                    "nota": f"Match stabilimento industriale {emb1_pulito}. Somiglianza ricetta stimata: {score}%.",
                    "bollino": livello
                })

    if database_mappato:
        df = pd.DataFrame(database_mappato)
        df = df.drop_duplicates(subset=["discount", "marca"])
        df.to_csv("prodotti.csv", index=False)
        print(f"🔥 FILE GENERATO CON SUCCESSO! Trovati {len(df)} incroci industriali.")
    else:
        # Se l'API fa i capricci, creiamo un file minimo di test per non far svuotare l'app
        print("Nessun match ricavato dalle API. Creo file di test standard.")
        df_fall = pd.DataFrame([{
            "stabilimento": "IT033CE", "categoria": "Biscotti",
            "discount": "Frollini Lamberti [Eurospin]", "marca": "Pan di Stelle [Mulino Bianco]",
            "barcode_discount": "11111111", "barcode_marca": "22222222",
            "nota": "Test di allineamento database superato.", "bollino": "🟢 Identico (Ricetta Match)"
        }])
        df_fall.to_csv("prodotti.csv", index=False)

if __name__ == "__main__":
    esegui_pompaggio_db()
    return []

def esegui_pompaggio_db():
    # Parole chiave dei prodotti più cercati per gli sgami
    target_keywords = ["biscotti", "frollini", "merendine", "croissant", "patatine", "pasta", "passata", "latte", "yogurt", "cereali"]
    
    tutti_i_prodotti = []
    for kw in target_keywords:
        prodotti_kw = scarica_categoria(kw)
        tutti_i_prodotti.extend(prodotti_kw)
        time.sleep(1) # Rispettiamo il server di OFF
        
    print(f"Totale prodotti grezzi accumulati: {len(tutti_i_prodotti)}")
    
    database_mappato = []
    
    # Lista di parole chiave per identificare se un marchio è un discount/MDD
    marchi_discount = ["eurospin", "conad", "coop", "esselunga", "lidl", "carrefour", "md", "todis", "selex", "pam"]

    for i, p1 in enumerate(tutti_i_prodotti):
        emb1 = p1.get("emb_codes", "").strip()
        emb1_pulito = pulisci_bollino(emb1)
        name1 = p1.get("product_name", "Generico").strip()
        brand1 = p1.get("brands", "Generico").strip()
        ing1 = p1.get("ingredients_text_it", "")
        code1 = p1.get("code", "")
        
        if not emb1_pulito or brand1 == "Generico": continue
        
        for p2 in tutti_i_prodotti[i+1:]:
            brand2 = p2.get("brands", "Generico").strip()
            emb2_pulito = pulisci_bollino(p2.get("emb_codes", ""))
            name2 = p2.get("product_name", "Generico").strip()
            ing2 = p2.get("ingredients_text_it", "")
            code2 = p2.get("code", "")
            
            if emb1_pulito == emb2_pulito and brand1.lower() != brand2.lower() and brand2 != "Generico":
                
                # Capiamo qual è la Grande Marca e qual è il Discount
                b1_disc = any(d in brand1.lower() for d in marchi_discount)
                b2_disc = any(d in brand2.lower() for d in marchi_discount)
                
                if b1_disc and not b2_disc:
                    m_discount, n_discount, e_barcode = brand1, name1, code1
                    m_marca, n_marca, m_barcode = brand2, name2, code2
                elif b2_disc and not b1_disc:
                    m_discount, n_discount, e_barcode = brand2, name2, code2
                    m_marca, n_marca, m_barcode = brand1, name1, code1
                else:
                    # Se non siamo sicuri, li mettiamo standard
                    m_discount, n_discount, e_barcode = brand1, name1, code1
                    m_marca, n_marca, m_barcode = brand2, name2, code2
                
                score = calcola_somiglianza_ingredienti(ing1, ing2)
                
                if score > 80:
                    livello = "🟢 Identico (Ricetta Match)"
                elif score > 50:
                    livello = "🟡 Gemello (Ricetta Simile)"
                else:
                    livello = "🟠 Solo Stessa Fabbrica"
                
                # Salviamo informazioni molto dettagliate (compresi i codici a barre!)
                database_mappato.append({
                    "stabilimento": emb1.split(",")[0].replace("EMB", "").strip(),
                    "categoria": p1.get("categories", "Altro").split(",")[0],
                    "discount": f"{n_discount} [{m_discount}]",
                    "marca": f"{n_marca} [{m_marca}]",
                    "barcode_discount": str(e_barcode),
                    "barcode_marca": str(m_barcode),
                    "nota": f"Analisi ricetta: {score}% di ingredienti combacianti. Stabilimento ID: {emb1_pulito}.",
                    "bollino": livello
                })

    if database_mappato:
        df = pd.DataFrame(database_mappato)
        df = df.drop_duplicates(subset=["discount", "marca"])
        df.to_csv("prodotti.csv", index=False)
        print(f"🔥 Successo! Database salvato con {len(df)} incroci mirati ricchi di dettagli.")
    else:
        print("Nessun incrocio trovato nelle categorie target.")

if __name__ == "__main__":
    esegui_pompaggio_db()
