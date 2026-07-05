import requests
import pandas as pd
import re

def pulisci_bollino(testo):
    if not testo: return ""
    # Estrae solo i numeri e le lettere importanti (es: IT033CE)
    pulito = re.sub(r'[^A-Z0-9]', '', str(testo).upper())
    return pulito.replace("EMB", "")

def calcola_somiglianza_ingredienti(ing_p1, ing_p2):
    if not ing_p1 or not ing_p2: return 0
    # Trasforma le stringhe degli ingredienti in set di parole per il confronto
    set1 = set(re.findall(r'\w+', ing_p1.lower()))
    set2 = set(re.findall(r'\w+', ing_p2.lower()))
    if not set1 or not set2: return 0
    # Indice di Jaccard (parole in comune / parole totali)
    intersezione = set1.intersection(set2)
    unione = set1.union(set2)
    return int((len(intersezione) / len(unione)) * 100)

def scarica_e_incrocia():
    print("Avvio download intensivo da Open Food Facts...")
    url = "https://it.openfoodfacts.org/api/v2/search"
    
    # Parametri per scaricare i prodotti italiani con stabilimento noto
    params = {
        "action": "process",
        "tagtype_0": "countries",
        "tag_contains_0": "contains",
        "tag_0": "italia",
        "fields": "product_name,brands,categories,emb_codes,ingredients_text_it",
        "page_size": 250, # Alziamo il tiro per avere molti più dati
        "cc": "it", "lc": "it"
    }
    
    headers = {"User-Agent": "InciarmoSpesaBot/2.0"}
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=20)
        if res.status_code != 200: return
        
        products = res.json().get("products", [])
        print(f"Scaricati {len(products)} prodotti. Inizio analisi incrociata...")
        
        # Dividiamo i prodotti in Grandi Marche e Discount/MDD (In base ai brand più comuni)
        # Nota: OFF classifica tutto, noi incrociamo per Stabilimento Comune
        database_mappato = []
        
        for i, p1 in enumerate(products):
            emb1 = p1.get("emb_codes", "").strip()
            emb1_pulito = pulisci_bollino(emb1)
            name1 = p1.get("product_name", "").strip()
            brand1 = p1.get("brands", "Generico").strip()
            ing1 = p1.get("ingredients_text_it", "")
            
            if not emb1_pulito or not name1: continue
            
            # Cerchiamo un altro prodotto nel mucchio con lo STESSO stabilimento pulito
            for p2 in products[i+1:]:
                emb2_pulito = pulisci_bollino(p2.get("emb_codes", ""))
                name2 = p2.get("product_name", "").strip()
                brand2 = p2.get("brands", "Generico").strip()
                ing2 = p2.get("ingredients_text_it", "")
                
                # Se lo stabilimento è lo stesso ma le marche sono diverse -> Abbiamo un Inciarmo!
                if emb1_pulito == emb2_pulito and brand1.lower() != brand2.lower() and name2:
                    
                    # Valutiamo il livello in base agli ingredienti
                    score = calcola_somiglianza_ingredienti(ing1, ing2)
                    
                    if score > 75:
                        livello = "🟢 Identico (Ricetta Match)"
                    elif score > 45:
                        livello = "🟡 Gemello (Ricetta Simile)"
                    else:
                        livello = "🟠 Solo Stessa Fabbrica"
                        
                    database_mappato.append({
                        "stabilimento": emb1.split(",")[0],
                        "categoria": p1.get("categories", "Altro").split(",")[0],
                        "discount": f"{name1} ({brand1})",
                        "marca": f"{name2} ({brand2})",
                        "nota": f"Somiglianza ricetta: {score}%. Analizzato automaticamente.",
                        "bollino": livello
                    })
                    
        # Salviamo il CSV finale con gli incroci reali
        df = pd.DataFrame(database_mappato)
        # Elimina i duplicati speculari
        df = df.drop_duplicates(subset=["discount", "marca"])
