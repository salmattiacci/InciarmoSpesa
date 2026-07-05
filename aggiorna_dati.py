import requests
import pandas as pd
import re
import time

def pulisci_bollino(testo):
    if not testo: return ""
    pulito = re.sub(r'[^A-Z0-9]', '', str(testo).upper())
    return pulito.replace("EMB", "")

def calcola_somiglianza_ingredienti(ing_p1, ing_p2):
    if not ing_p1 or not ing_p2: return 0
    set1 = set(re.findall(r'\w+', ing_p1.lower()))
    set2 = set(re.findall(r'\w+', ing_p2.lower()))
    if not set1 or not set2: return 0
    intersezione = set1.intersection(set2)
    unione = set1.union(set2)
    return int((len(intersezione) / len(unione)) * 100)

def scarica_categoria(parola_chiave):
    print(f"Sfecciando prodotti per: {parola_chiave}...")
    url = "https://it.openfoodfacts.org/api/v2/search"
    params = {
        "search_terms": parola_chiave,
        "action": "process",
        "fields": "product_name,brands,categories,emb_codes,ingredients_text_it,code",
        "page_size": 150,
        "cc": "it", "lc": "it"
    }
    headers = {"User-Agent": "InciarmoSpesaBot/3.0"}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        if res.status_code == 200:
            return res.json().get("products", [])
    except Exception as e:
        print(f"Errore download {parola_chiave}: {e}")
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
