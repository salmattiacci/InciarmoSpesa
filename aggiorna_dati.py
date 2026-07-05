import requests
import pandas as pd

def scarica_catalogo_off():
    print("Inizio scaricamento dati da Open Food Facts...")
    url = "https://it.openfoodfacts.org/api/v2/search"
    
    # Scarichiamo un bel blocco di prodotti italiani comuni
    params = {
        "search_terms": "biscotti", # Puoi fare più chiamate o estrarre macro-categorie
        "search_simple": "1",
        "action": "process",
        "fields": "product_name,brands,emb_codes",
        "page_size": 100, # Prendiamo i primi 100 prodotti principali
        "cc": "it",
        "lc": "it"
    }
    
    headers = {"User-Agent": "InciarmoSpesaBot/1.0 (Contatto: salmattiacci@github.com)"}
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        if res.status_code == 200:
            products = res.json().get("products", [])
            lista_final = []
            
            for p in products:
                name = p.get("product_name", "").strip()
                brand = p.get("brands", "Generico").strip()
                emb = p.get("emb_codes", "").strip().upper()
                
                if name and emb: # Salviamo solo quelli che hanno un bollo CE dichiarato!
                    lista_final.append({
                        "stabilimento": emb.split(",")[0].replace("EMB", "").strip(),
                        "categoria": "Online",
                        "discount": name,
                        "marca": brand,
                        "nota": "Sincronizzato automaticamente via API",
                        "bollino": "🔵 Dati Web"
                    })
            
            # Trasformiamo in DataFrame e salviamo in CSV
            df = pd.DataFrame(lista_final)
            df.to_csv("prodotti.csv", index=False)
            print(f"Sincronizzazione completata! Salvati {len(df)} prodotti con stabilimento.")
            
    except Exception as e:
        print(f"Errore durante l'automazione: {e}")

if __name__ == "__main__":
    scarica_catalogo_off()
