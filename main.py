import flet as ft

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

def main(page: ft.Page):
    page.title = "L'Inciarmo della Spesa 🛒"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = "adaptive"
    page.padding = ft.padding.only(top=10, left=15, right=15, bottom=10)

    lista_prodotti = ft.ListView(expand=True, spacing=10, padding=ft.padding.only(top=10))

    def render_cards(filtro=""):
        lista_prodotti.controls.clear()
        for p in DATABASE_PRODOTTI:
            if any(filtro.lower() in str(value).lower() for value in p.values()):
                lista_prodotti.controls.add(
                    ft.Card(
                        elevation=2,
                        content=ft.Container(
                            padding=15,
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(p["categoria"].upper(), size=11, color=ft.colors.BLUE_700, weight=ft.FontWeight.BOLD),
                                    ft.Text(p["bollino"], size=12, weight=ft.FontWeight.BOLD)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(f"Discount: {p['discount']}", size=15, weight=ft.FontWeight.BOLD),
                                ft.Text(f"💎 Marca: {p['marca']}", size=14, color=ft.colors.GREEN_700, weight=ft.FontWeight.W_500),
                                ft.Divider(height=10, thickness=0.5),
                                ft.Text(f"🏭 Stabilimento: {p['stabilimento']}", size=11, italic=True, color=ft.colors.GREY_600),
                                ft.Text(p["nota"], size=12, color=ft.colors.GREY_800)
                            ], spacing=5)
                        )
                    )
                )
        page.update()

    barra_ricerca = ft.TextField(
        label="Cerca stabilimento, discount o marca...",
        prefix_icon=ft.icons.SEARCH,
        on_change=lambda e: render_cards(e.control.value),
        border_radius=10,
        text_size=14,
        content_padding=10
    )

    page.add(
        ft.Column([
            ft.Text("L'Inciarmo", size=26, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900),
            ft.Text("Trova i produttori reali dietro i brand da discount", size=12, color=ft.colors.GREY_600),
            ft.Container(height=5),
            barra_ricerca,
        ], spacing=2),
        lista_prodotti
    )
    
    render_cards()

app = ft.app(target=main, assets_dir="assets", view=ft.AppView.WEB_BROWSER)
