"""
InciarmoSpesa - Matching prodotti (marca vs private label)
senza dipendenza dal prezzo.

Logica:
1. Filtra prodotti per stessa categoria (evita confronti insensati)
2. Esclude coppie con lo stesso brand (vogliamo marca vs equivalente)
3. Calcola similarità ingredienti (token-based, con rapidfuzz)
4. Se disponibile, boosta lo score se lo stabilimento coincide
5. Ritorna le coppie ordinate per score decrescente

Dipendenze:
    pip install rapidfuzz
"""

from dataclasses import dataclass, field
from itertools import combinations
from rapidfuzz import fuzz


@dataclass
class Prodotto:
    barcode: str
    nome: str
    marca: str
    categorie: list[str] = field(default_factory=list)
    ingredienti: str = ""          # testo grezzo, es. da Open Food Facts "ingredients_text"
    stabilimento: str | None = None  # es. da "manufacturing_places" o codice bollo CE


@dataclass
class MatchCandidato:
    prodotto_a: Prodotto
    prodotto_b: Prodotto
    score_ingredienti: float
    score_stabilimento: float
    stesso_stabilimento: bool
    score_finale: float


def normalizza_ingredienti(testo: str) -> str:
    """Pulizia: minuscolo, rimozione percentuali/numeri, e taglio delle
    parti di 'provenienza'/'tracce' che non fanno parte della vera ricetta
    (es. 'Paese di coltivazione...', 'Può contenere...') così due prodotti
    con stessa ricetta ma metadati diversi vengono comunque riconosciuti."""
    import re
    testo = testo.lower()
    # taglia via le sezioni di provenienza/tracce, che non descrivono la ricetta
    testo = re.split(r"può contenere|paese di (coltivazione|molitura)|origine", testo)[0]
    testo = re.sub(r"\d+([.,]\d+)?\s*%?", "", testo)
    testo = re.sub(r"[^\w\s,]", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip()
    return testo


def normalizza_categoria(tag: str) -> str:
    """Toglie il prefisso lingua (es. 'en:', 'it:') così categorie
    equivalenti in lingue diverse vengono riconosciute come uguali."""
    return tag.split(":", 1)[-1] if ":" in tag else tag


def stessa_categoria(a: Prodotto, b: Prodotto) -> bool:
    # Se a uno dei due prodotti mancano le categorie, non blocchiamo il
    # confronto: lasciamo decidere alla similarità ingredienti.
    if not a.categorie or not b.categorie:
        return True
    cat_a = {normalizza_categoria(c) for c in a.categorie}
    cat_b = {normalizza_categoria(c) for c in b.categorie}
    return bool(cat_a & cat_b)


def calcola_similarita_ingredienti(a: Prodotto, b: Prodotto) -> float:
    ing_a = normalizza_ingredienti(a.ingredienti)
    ing_b = normalizza_ingredienti(b.ingredienti)
    if not ing_a or not ing_b:
        return 0.0
    # token_set_ratio gestisce bene il caso in cui un testo è più corto
    # ma comunque contenuto nell'altro (es. "semola di grano duro" vs
    # "semola di grano duro, acqua")
    return fuzz.token_set_ratio(ing_a, ing_b)


def calcola_similarita_stabilimento(a: Prodotto, b: Prodotto) -> float:
    """Confronto fuzzy tra i due campi stabilimento (bollino CE pulito o
    indirizzo/ragione sociale ripulita). Non serve più l'uguaglianza
    esatta: due varianti dello stesso indirizzo (es. 'Rummo SpA' vs
    'Rummo S.p.A. Benevento') ora vengono comunque riconosciute come
    simili invece di risultare sempre diverse."""
    if not a.stabilimento or not b.stabilimento:
        return 0.0
    return fuzz.token_set_ratio(a.stabilimento, b.stabilimento)


def prodotto_da_off_json(dati: dict) -> Prodotto | None:
    """
    Costruisce un Prodotto a partire dalla risposta JSON di Open Food Facts
    (endpoint https://world.openfoodfacts.org/api/v2/product/<barcode>.json).
    Ritorna None se mancano i campi minimi indispensabili.
    """
    prodotto = dati.get("product", dati)  # tollera sia risposta grezza che già estratta

    barcode = prodotto.get("code") or prodotto.get("_id")
    nome = prodotto.get("product_name") or prodotto.get("product_name_it")
    marca = prodotto.get("brands")

    if not (barcode and nome and marca):
        return None

    categorie = prodotto.get("categories_tags", [])
    ingredienti = prodotto.get("ingredients_text_it") or prodotto.get("ingredients_text", "")
    stabilimento = prodotto.get("manufacturing_places") or None

    return Prodotto(
        barcode=barcode,
        nome=nome,
        marca=marca,
        categorie=categorie,
        ingredienti=ingredienti,
        stabilimento=stabilimento,
    )


def valuta_coppia(
    a: Prodotto,
    b: Prodotto,
    soglia_ingredienti: float = 75.0,
    soglia_stabilimento: float = 80.0,
    boost_stabilimento: float = 15.0,
) -> MatchCandidato | None:
    """Valuta una singola coppia di prodotti. Ritorna None se non è un match valido.

    Il match scatta se ALMENO UNO tra ingredienti e stabilimento supera la
    propria soglia — non serve più che siano gli ingredienti a decidere da
    soli. Per prodotti a ricetta fissa (es. pasta: sempre semola+acqua per
    chiunque) gli ingredienti non sono un segnale utile, quindi deve poter
    bastare lo stabilimento uguale a far scattare il match."""
    if a.marca == b.marca:
        return None
    if not stessa_categoria(a, b):
        return None

    score_ing = calcola_similarita_ingredienti(a, b)
    score_stab = calcola_similarita_stabilimento(a, b)
    stesso_stab = score_stab >= soglia_stabilimento

    match_su_ingredienti = score_ing >= soglia_ingredienti
    if not match_su_ingredienti and not stesso_stab:
        return None

    score_finale = score_ing
    if stesso_stab:
        score_finale = min(100.0, score_finale + boost_stabilimento)
        # se il match è "portato" solo dallo stabilimento (ingredienti
        # sotto soglia, tipico della pasta), non lasciamo che uno score
        # ingredienti basso schiacci lo score finale verso il basso
        score_finale = max(score_finale, score_stab)

    return MatchCandidato(
        prodotto_a=a,
        prodotto_b=b,
        score_ingredienti=round(score_ing, 1),
        score_stabilimento=round(score_stab, 1),
        stesso_stabilimento=stesso_stab,
        score_finale=round(score_finale, 1),
    )


def trova_match(
    prodotti: list[Prodotto],
    soglia_ingredienti: float = 75.0,
    soglia_stabilimento: float = 80.0,
    boost_stabilimento: float = 15.0,
) -> list[MatchCandidato]:
    """Confronta tutti i prodotti di una lista tra loro (a coppie)."""
    candidati = [
        c for a, b in combinations(prodotti, 2)
        if (c := valuta_coppia(a, b, soglia_ingredienti, soglia_stabilimento, boost_stabilimento))
    ]
    return sorted(candidati, key=lambda c: c.score_finale, reverse=True)


def confronta_con_collezione(
    nuovo: Prodotto,
    collezione: list[Prodotto],
    soglia_ingredienti: float = 75.0,
    soglia_stabilimento: float = 80.0,
    boost_stabilimento: float = 15.0,
) -> list[MatchCandidato]:
    """
    Confronta UN prodotto nuovo contro una collezione già esistente.
    Utile quando i prodotti si cercano uno alla volta (es. app con ricerca
    singola) invece che tutti insieme.
    """
    candidati = [
        c for esistente in collezione
        if (c := valuta_coppia(nuovo, esistente, soglia_ingredienti, soglia_stabilimento, boost_stabilimento))
    ]
    return sorted(candidati, key=lambda c: c.score_finale, reverse=True)


if __name__ == "__main__":
    # Esempio d'uso con dati finti - da sostituire con dati veri da Open Food Facts
    prodotti = [
        Prodotto(
            barcode="8001",
            nome="Pasta di semola n.5",
            marca="Barilla",
            categorie=["pasta", "pasta-secca"],
            ingredienti="semola di grano duro, acqua",
            stabilimento="Foggia, IT",
        ),
        Prodotto(
            barcode="8002",
            nome="Semola rigata n.5",
            marca="Coop",
            categorie=["pasta", "pasta-secca"],
            ingredienti="semola di grano duro 100%, acqua",
            stabilimento="Foggia, IT",
        ),
        Prodotto(
            barcode="8003",
            nome="Biscotti frollini",
            marca="Mulino Bianco",
            categorie=["biscotti"],
            ingredienti="farina di frumento, zucchero, olio di girasole, uova",
            stabilimento=None,
        ),
    ]

    risultati = trova_match(prodotti)
    for r in risultati:
        print(
            f"{r.prodotto_a.nome} ({r.prodotto_a.marca}) "
            f"<-> {r.prodotto_b.nome} ({r.prodotto_b.marca}) "
            f"| ingredienti={r.score_ingredienti} "
            f"| stesso stabilimento={r.stesso_stabilimento} "
            f"| score finale={r.score_finale}"
        )
        
