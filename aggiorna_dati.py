import requests
import pandas as pd
import re
import os
import time
import random

# Dizionario prezzi medi di mercato in Italia (Marca vs Discount) - Fallback di sicurezza
LISTINO_PREZZI_MEDIO = {
    "biscuits": {"marca": 2.99, "discount": 1.79},
    "chocolate biscuits": {"marca": 3.49, "discount": 1.99},
    "dry biscuits": {"marca": 2.49, "discount": 1.39},
    "sliced breads": {"marca": 1.89, "discount": 0.99},
    "sweetened beverages": {"marca": 2.20, "discount": 1.10},
    "colas": {"marca": 2.10, "discount": 0.95},
    "natural mineral waters": {"marca": 0.45, "discount": 0.22},
    "peanut butters": {"marca": 3.99, "discount": 2.49},
    "cocoa and hazelnuts spreads": {"marca": 5.49, "discount": 3.29},
    "tomato purées": {"marca": 1.39, "discount": 0.79},
    "yogurts": {"marca": 1.69, "discount": 0.99},
    "milks": {"marca": 1.59, "discount": 1.09}
}

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

def cerca_prezzo_reale_api_sicura(barcode):
    url = f"https://it.openfoodfacts.org/api/v2/product/{barcode}"
    headers = {"User-Agent": "InciarmoSpesaPrezziBot/5.0 (Privacy-Safe System)"}
    try:
        time.sleep(random.uniform(1.0, 2.0))
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            dati = res.json()
            prodotto = dati.get("product", {})
            prezzo = prodotto.get("price_value") or prodotto.get("price")
            if prezzo and str(prezzo).replace('.','',1).isdigit():
                return round(float(prezzo), 2)
    except:
        pass
    return None

def stimatore_prezzo(categoria, tipo_prodotto, barcode=None):
    if barcode:
        prezzo_reale = cerca_prezzo_reale_api_sicura(barcode)
        if prezzo_reale:
            return prezzo_reale

    cat_chiave = str(categoria).lower().strip()
    for k, prezzi in LISTINO_PREZZI_MEDIO.items():
        if k in cat_chiave:
            return prezzi[tipo_prodotto]
    return 2.49 if tipo_prodotto == "marca" else 1.49

def scarica_tutti_prodotti_massa():
    print("Inizio scaricamento progressivo da Open Food Facts...")
    url = "https://it.openfoodfacts.org/api/v2/search"
    tutti_i_prodotti = []
    
    for pagina in range(1, 4):
        print(f"Scaricamento pagina {pagina}...")
        params = {
            "action": "process",
            "tagtype_0": "countries",
            "tag_contains_0": "contains",
            "tag_0": "italia",
            "fields": "product_name,brands,categories,emb_codes,ingredients_text_it,code",
            "page_size": 250, 
            "page": pagina,
            "cc": "it", "lc": "it"
        }
        headers = {"User-Agent": "InciarmoSpesaBot/5.0"}
        
        for tentativo in range(3):
            try:
                res = requests.get(url, params=params, headers=headers, timeout=15)
                if res.status_code == 200:
                    prodotti_pagina = res.json().get("products", [])
                    tutti_i_prodotti.extend(prodotti_pagina)
                    print(f"Scaricati {len(prodotti_pagina)} prodotti dalla pagina {pagina}.")
                    break
                else:
                    print(f"Server ha risposto con status {res.status_code}, riprovo...")
            except Exception as e:
                print(f"Tentativo {tentativo + 1} fallito per timeout o errore: {e}")
            time.sleep(2)
            
        time.sleep(1)
        
    print(f"Scaricamento completato. Totale prodotti grezzi raccolti: {len(tutti_i_prodotti)}")
    return tutti_i_prodotti

def esegui_pipeline():
    nuovi_prodotti = scarica_tutti_prodotti_massa()
    if not nuovi_prodotti:
        print("Nessun dato scaricato dopo tutti i tentativi.")
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
    contatore_richieste = 0
    
    for i, p1 in enumerate(lista_prodotti):
        emb1 = str(p1.get("emb_codes", "")).strip()
        emb1_pulito = pulisci_bollino(emb1)
        name1 = str(p1.get("product_name", "")).strip()
        brand1 = str(p1.get("brands", "Generico")).strip()
        cat1 = str(p1.get("categories", "Altro")).split(",")[0].strip()
        ing1 = p1.get("ingredients_text_it", "")
        code1 = p1.get("code", "")
        
        if brand1 == "Generico" or name1 in ["", "nan"]: continue
        
        for p2 in lista_prodotti[i+1:]:
            brand2 = str(p2.get("brands", "Generico")).strip()
            name2 = str(p2.get("product_name", "")).strip()
            cat2 = str(p2.get("categories", "Altro")).split(",")[0].strip()
            emb2_pulito = pulisci_bollino(p2.get("emb_codes", ""))
            ing2 = p2.get("ingredients_text_it", "")
            code2 = p2.get("code", "")
            
            if brand2 == "Generico" or name2 in ["", "nan"] or brand1.lower() == brand2.lower(): continue
            
            score = calcola_somiglianza_ingredienti(ing1, ing2)
            match_valido = False
            tipo_match = ""
            
            is_acqua_o_singolo = "water" in cat1.lower() or "acque" in cat1.lower() or "beverages" in cat1.lower()
            
            # FILTRO DI SICUREZZA AGGIORNATO (SOLUZIONE A):
            # Se lo stabilimento coincide, richiediamo COMUNQUE uno score minimo del 65% per confermare il clone commerciale.
            if emb1_pulito and emb2_pulito and emb1_pulito != "NAN" and emb2_pulito != "NAN" and emb1_pulito == emb2_pulito:
                if score >= 85:
                    match_valido = True
                    tipo_match = "🟢 Identico (Stessa Fabbrica + Ricetta)"
                elif score >= 65:
                    match_valido = True
                    tipo_match = "🟡 Gemello (Stessa Fabbrica + Ricetta Simile)"
                else:
                    # Scartato: escono dallo stesso posto ma sono prodotti completamente diversi (Evita il caso Galbusera-Misura errato)
                    continue
            
            # Match basato solo sulla ricetta analoga nel database (senza bollino)
            elif cat1 == cat2 and cat1 != "Altro" and score >= 75 and not is_acqua_o_singolo:
                match_valido = True
                tipo_match = "🟢 Identico (Analisi Ricette DB)" if score > 85 else "🟡 Gemello (Ricetta Simile)"

            if match_valido:
                b1_disc = any(d in brand1.lower() for d in marchi_discount)
                b2_disc = any(d in brand2.lower() for d in marchi_discount)
                
                if b1_disc and not b2_disc:
                    m_discount, n_discount, e_barcode = brand1, name1, code1
                    m_marca, n_marca, m_barcode = brand2, name2, code2
                else:
                    m_discount, n_discount, e_barcode = brand2, name2, code2
                    m_marca, n_marca, m_barcode = brand1, name1, code1
                
                usa_api_reale = contatore_richieste < 30
                prezzo_disc = stimatore_prezzo(cat1, "discount", e_barcode if usa_api_reale else None)
                prezzo_marca = stimatore_prezzo(cat1, "marca", m_barcode if usa_api_reale else None)
                
                if usa_api_reale:
                    contatore_richieste += 2
                
                stabilimento_finale = emb1_pulito if (emb1_pulito and emb1_pulito != "NAN") else "Verificato da Ricetta"
                
                database_mappato.append({
                    "stabilimento": stabilimento_finale,
                    "categoria": cat1,
                    "discount": f"{n_discount} [{m_discount}]",
                    "marca": f"{n_marca} [{m_marca}]",
                    "barcode_discount": str(e_barcode),
                    "barcode_marca": str(m_barcode),
                    "prezzo_discount": float(prezzo_disc),
                    "prezzo_marca": float(prezzo_marca),
                    "nota": f"Analisi di laboratorio digitale. Corrispondenza ingredienti: {score}%.",
                    "bollino": tipo_match
                })
                
    if database_mappato:
        df_cache = pd.DataFrame(database_mappato)
        df_cache = df_cache.drop_duplicates(subset=["discount", "marca"])
        df_cache.to_csv("prodotti.csv", index=False)
        print(f"Successo! Mappati {len(df_cache)} prodotti puliti e sicuri nel DB finale.")
    else:
        print("Nessun match valido e sicuro trovato in questa sessione.")

if __name__ == "__main__":
    esegui_pipeline()
                     
