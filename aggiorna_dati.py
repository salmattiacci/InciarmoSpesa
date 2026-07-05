import requests
import pandas as pd
import re
import os

def pulisci_bollino(testo):
    if not testo or pd.isna(testo): return ""
    pulito = re.sub(r'[^A-Z0-9]', '', str(testo).upper())
    return pulito.replace("EMB", "")

def calcola_somiglianza_ingredienti(ing1, ing2):
    if not ing1 or not ing2 or pd.isna(ing1) or pd.isna(ing2): return 0
    set1 = set(re.findall(r'\w+', str(ing1).lower()))
    set2 = set(re.findall(r'\w+', str(ing2).lower()))
    if not set1 or not set2: return 0
    intersezione = set1.intersection(set2)
    unione = set1.union(set2)
    return int((len(intersezione) / len(unione)) * 100)

def scarica_tutti_prodotti_massa():
    print("Inizio scaricamento di massa da Open Food Facts...")
    url = "https://it.openfoodfacts.org/api/v2/search"
    
    params = {
        "action": "process",
        "tagtype_0": "countries",
        "tag_contains_0": "contains",
        "tag_0": "italia",
        "fields": "product_name,brands,categories,emb_codes,ingredients_text_it,code,price,price_value",
        "page_size": 1000, 
        "cc": "it", "lc": "it"
    }
    
    headers = {"User-Agent": "InciarmoSpesaBot/5.0"}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=25)
        if res.status_code == 200:
            return res.json().get("products", [])
        else:
            return []
    except Exception as e:
        print(f"Errore: {e}")
        return []

def esegui_pipeline():
    nuovi_prodotti = scarica_tutti_prodotti_massa()
    if not nuovi_prodotti:
        print("Nessun dato scaricato.")
        return
        
    df_nuovi = pd.DataFrame(nuovi_prodotti)
    
    file_raw = "prodotti_raw.csv"
    if os.path.exists(file_raw):
        df_vecchi = pd.read_csv(file_raw)
        df_totale_raw = pd.concat([df_vecchi, df_nuovi]).drop_duplicates(subset=["code"])
    else:
        df_totale_raw = df_nuovi
        
    df_totale_raw.to_csv(file_raw, index=False)
    
    print("Generazione della cache degli sgami reali...")
    database_mappato = []
    marchi_discount = ["eurospin", "conad", "coop", "esselunga", "lidl", "carrefour", "md", "todis", "selex", "pam", "galbusera", "amo essere bio", "tre mulini", "maribel", "sibamba", "blues"]
    
    lista_prodotti = df_totale_raw.to_dict(orient="records")
    
    for i, p1 in enumerate(lista_prodotti):
        emb1 = str(p1.get("emb_codes", "")).strip()
        emb1_pulito = pulisci_bollino(emb1)
        name1 = str(p1.get("product_name", "")).strip()
        brand1 = str(p1.get("brands", "Generico")).strip()
        cat1 = str(p1.get("categories", "Altro")).split(",")[0].strip()
        ing1 = p1.get("ingredients_text_it", "")
        code1 = p1.get("code", "")
        p1_prezzo = p1.get("price_value", p1.get("price", "N/D"))
        
        if brand1 == "Generico" or name1 in ["", "nan"]: continue
        
        for p2 in lista_prodotti[i+1:]:
            brand2 = str(p2.get("brands", "Generico")).strip()
            name2 = str(p2.get("product_name", "")).strip()
            cat2 = str(p2.get("categories", "Altro")).split(",")[0].strip()
            emb2_pulito = pulisci_bollino(p2.get("emb_codes", ""))
            ing2 = p2.get("ingredients_text_it", "")
            code2 = p2.get("code", "")
            p2_prezzo = p2.get("price_value", p2.get("price", "N/D"))
            
            if brand2 == "Generico" or name2 in ["", "nan"] or brand1.lower() == brand2.lower(): continue
            
            # Calcolo somiglianza ricetta
            score = calcola_somiglianza_ingredienti(ing1, ing2)
            match_valido = False
            tipo_match = ""
            
            # REGOLA 1: Stabilimenti identici compilati (Match di Fabbrica)
            if emb1_pulito and emb2_pulito and emb1_pulito != "NAN" and emb2_pulito != "NAN" and emb1_pulito == emb2_pulito:
                match_valido = True
                if score > 75: tipo_match = "🟢 Identico (Stessa Fabbrica + Ricetta)"
                elif score > 45: tipo_match = "🟡 Gemello (Stessa Fabbrica + Ricetta Simile)"
                else: tipo_match = "🟠 Solo Stessa Fabbrica"
                
            # REGOLA 2: Stabilimenti mancanti MA stessa categoria precisa e ricetta quasi identica (>70%)
            elif cat1 == cat2 and cat1 != "Altro" and score >= 70:
                match_valido = True
                tipo_match = "🟢 Identico (Analisi Ricette DB)" if score > 85 else "🟡 Gemello (Ricetta Simile)"

            if match_valido:
                b1_disc = any(d in brand1.lower() for d in marchi_discount)
                b2_disc = any(d in brand2.lower() for d in marchi_discount)
                
                if b1_disc and not b2_disc:
                    m_discount, n_discount, e_barcode, prezzo_disc = brand1, name1, code1, p1_prezzo
                    m_marca, n_marca, m_barcode, prezzo_marca = brand2, name2, code2, p2_prezzo
                else:
                    m_discount, n_discount, e_barcode, prezzo_disc = brand2, name2, code2, p2_prezzo
                    m_marca, n_marca, m_barcode, prezzo_marca = brand1, name1, code1, p1_prezzo
                
                stabilimento_finale = emb1_pulito if (emb1_pulito and emb1_pulito != "NAN") else "Verificato da Ricetta"
                
                database_mappato.append({
                    "stabilimento": stabilimento_finale,
                    "categoria": cat1,
                    "discount": f"{n_discount} [{m_discount}]",
                    "marca": f"{n_marca} [{m_marca}]",
                    "barcode_discount": str(e_barcode),
                    "barcode_marca": str(m_barcode),
                    "prezzo_discount": str(prezzo_disc),
                    "prezzo_marca": str(prezzo_marca),
                    "nota": f"Analisi di laboratorio digitale. Corrispondenza ingredienti: {score}%.",
                    "bollino": tipo_match
                })
                
    if database_mappato:
        df_cache = pd.DataFrame(database_mappato)
        df_cache = df_cache.drop_duplicates(subset=["discount", "marca"])
        df_cache.to_csv("prodotti.csv", index=False)
        print(f"Successo! Mappati {len(df_cache)} inciarmi reali con la strategia ibrida.")
    else:
        print("Nessun match trovato nemmeno con il controllo incrociato delle ricette.")

if __name__ == "__main__":
    esegui_pipeline()
    
