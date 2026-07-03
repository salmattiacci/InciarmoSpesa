import streamlit as str

# Configurazione pagina per Mobile PWA
str.set_page_config(page_title="L'Inciarmo della Spesa", page_icon="🛒", layout="centered")

DATABASE_PRODOTTI = [
    {
        "stabilimento": "IT 03 3 CE",
        "categoria": "Latticini",
        "discount": "Gorgonzola Dolce (Pascoli Italiani - Eurospin)",
        "marca": "Gorgonzola Gim (Invernizzi/Galbani)",
        "nota": "Prodotto da Egidio Galbani. Stessi ingredienti, stessa consistenza cremosa.",
        "bollino": "🟢 Identico"
    },
    {
        "stabilimento": "Molicino (Campobasso)",
        "categoria": "Dolci",
        "discount": "Frollini con Panna (Conad)",
        "marca": "Tarallucci (Mulino Bianco)",
        "nota": "Prodotti nello stabilimento Barilla. Ingredienti e valori nutrizionali identici al grammo.",
        "bollino": "🟢 Identico"
    },
    {
        "stabilimento": "Novara (Via Veveri 2)",
        "categoria": "Snack",
        "discount": "Patatine Classiche (Esselunga / Coop)",
        "marca": "Patatine Classiche (San Carlo)",
        "nota": "Stessa identica ricetta: solo patate, olio e sale, fritte nello stesso stabilimento.",
        "bollino": "🟢 Identico"
    },
    {
        "stabilimento": "Anagni (Frosinone)",
        "categoria": "Bevande",
        "discount": "Tè alla Pesca/Limone (Blues - Eurospin)",
        "marca": "Estathé Ferrero",
        "nota": "Imbottigliato negli stessi stabilimenti. Ricetta con vero infuso di tè, minime varianti.",
        "bollino": "🟡 Gemello"
    }
]

str.title("L'Inciarmo della Spesa 🛒")
str.caption("Trova i produttori reali dietro i brand da discount")

# Barra di ricerca reattiva
query = str.text_input("Cerca stabilimento, discount o marca...", placeholder="Es. Eurospin, IT 03 3 CE...")

# Filtro e rendering dinamico
for p in DATABASE_PRODOTTI:
    if not query or any(query.lower() in str(value).lower() for value in p.values()):
        with str.container(border=True):
            col1, col2 = str.columns([3, 1])
            with col1:
                str.markdown(f"**{p['discount']}**")
                str.markdown(f"💎 *Equivalente a:* **{p['marca']}**")
            with col2:
                str.caption(f"**{p['bollino']}**")
            
            str.divider()
            str.caption(f"🏭 Stabilimento: {p['stabilimento']} | Categoria: {p['categoria']}")
            str.write(p['nota'])

