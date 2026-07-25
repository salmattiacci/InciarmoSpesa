"""
Pipeline di aggiornamento prezzi per L'Inciarmo della Spesa.

Legge i barcode da prodotti_raw.csv, recupera nome/marca/stabilimento da
Open Food Facts, e cerca il prezzo reale nel volantino Decò (VolantinoPiù).
Scrive il risultato in prodotti.csv.

prodotti_raw.csv atteso con una colonna: barcode
"""

import csv
import re
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "InciarmoDellaSpesaApp/2.0 (contatto: inciarmospesa_app@gmail.com)"
}

FILE_INPUT = "prodotti_raw.csv"
FILE_OUTPUT = "prodotti.csv"

# Cambia questo link ogni settimana con l'URL del volantino corrente
URL_VOLANTINO = "https://deco.volantinopiu.com/volantino2793400pv615.html"

CAMPI_OUTPUT = [
    "barcode",
    "nome",
    "marca",
    "stabilimento",
    "bollino_ce",
    "prezzo",
    "fonte_prezzo",
]


def pulisci_bollino(testo):
    if not testo:
        return ""
    testo_str = str(testo).upper().strip()
    match = re.search(r"(IT\s*\d+[\s*/]*\d*\s*CE|\d+[\s*/]*\d*\s*CE)", testo_str)
    if match:
        return re.sub(r"\s+", "", match.group(1))
    return ""


def leggi_barcode(path):
    barcode_list = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for riga in reader:
                bc = (riga.get("barcode") or "").strip()
                if bc:
                    barcode_list.append(bc)
    except FileNotFoundError:
        print(f"Attenzione: {path} non trovato, nessun barcode da processare.")
    return barcode_list


def interroga_open_food_facts(barcode):
    """Recupera nome, marca e stabilimento dal barcode."""
    url = f"https://world.openfoodfacts.net/api/v2/product/{barcode}.json"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == 1:
                prodotto = data.get("product", {})
                return {
                    "nome": prodotto.get("product_name") or "Prodotto sconosciuto",
                    "marca": prodotto.get("brands") or "Marca non indicata",
                    "stabilimento": prodotto.get("manufacturing_places") or "",
                }
    except requests.RequestException as e:
        print(f"[OFF] Errore per {barcode}: {e}")
    return {"nome": "Prodotto sconosciuto", "marca": "", "stabilimento": ""}


def scrape_volantino_deco(url):
    """Scarica il volantino e restituisce lista di {prezzo, descrizione}."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[Volantino] Errore nel caricare il volantino: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    risultati = []
    for prezzo_tag in soup.find_all(string=re.compile(r"€\s*\d+[.,]\d{2}")):
        contenitore = prezzo_tag.find_parent("div") or prezzo_tag.find_parent()
        testo = contenitore.get_text(" ", strip=True) if contenitore else ""
        risultati.append({"prezzo": prezzo_tag.strip(), "descrizione": testo[:150]})
    print(f"[Volantino] Trovati {len(risultati)} prodotti in promozione.")
    return risultati


def trova_prezzo_volantino(nome_prodotto, prodotti_volantino):
    """Cerca nome prodotto (case-insensitive) dentro le descrizioni del volantino."""
    if not nome_prodotto:
        return None, None
    nome_lower = nome_prodotto.lower()
    for p in prodotti_volantino:
        if nome_lower in p["descrizione"].lower():
            return p["prezzo"], p["descrizione"]
    return None, None


def processa_barcode(barcode, prodotti_volantino):
    info = interroga_open_food_facts(barcode)
    prezzo, fonte_testo = trova_prezzo_volantino(info["nome"], prodotti_volantino)

    riga = {
        "barcode": barcode,
        "nome": info["nome"],
        "marca": info["marca"],
        "stabilimento": info["stabilimento"],
        "bollino_ce": pulisci_bollino(info["stabilimento"]),
        "prezzo": prezzo or "",
        "fonte_prezzo": f"Volantino Decò: {fonte_testo}" if prezzo else "Non trovato nel volantino",
    }
    return riga


def main():
    barcodes = leggi_barcode(FILE_INPUT)
    print(f"Barcode da processare: {len(barcodes)}")

    prodotti_volantino = scrape_volantino_deco(URL_VOLANTINO)

    risultati = []
    for i, bc in enumerate(barcodes, start=1):
        print(f"[{i}/{len(barcodes)}] Elaboro {bc}...")
        risultati.append(processa_barcode(bc, prodotti_volantino))
        time.sleep(1)  # rispetto verso le API pubbliche, evita rate-limit

    with open(FILE_OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPI_OUTPUT)
        writer.writeheader()
        writer.writerows(risultati)

    trovati = sum(1 for r in risultati if r["prezzo"] != "")
    print(f"Fatto. {trovati}/{len(risultati)} prodotti con prezzo trovato nel volantino.")
    print(f"Output salvato in {FILE_OUTPUT}")


if __name__ == "__main__":
    main()
    
