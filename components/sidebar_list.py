import flet as ft

ACCENT = "#7c3aed"
BG_CARD = "#242424"
BG_SIDEBAR = "#1a1a1a"


def build_sidebar_list(
    items: list[dict],
    selected_id: str | None,
    on_select,
    on_add,
    search_hint: str = "Search characters...",
    add_label: str = "Manually Add Character",
    header_title: str = "Characters",
    header_icon=None,
) -> ft.Container:
    """Build a generic filterable sidebar list with a search box and an add button.

    Each item dict must contain ``id``, ``name`` and optionally ``initials``,
    ``color`` and ``subtitle``.
    Calls ``on_select(item_id)`` when a row is clicked and ``on_add()`` when
    the add button is clicked.
    """
    if header_icon is None:
        header_icon = ft.Icons.PERSON

    search_val = {"text": ""}

    def on_search_change(e):
        search_val["text"] = e.control.value.lower()
        update_list()

    search_field = ft.TextField(
        hint_text=search_hint,
        hint_style=ft.TextStyle(color="#666666", size=13),
        border_radius=8,
        border_color="#333333",
        focused_border_color=ACCENT,
        bgcolor="#242424",
        color="#ffffff",
        height=42,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        prefix_icon=ft.Icons.SEARCH,
        on_change=on_search_change,
    )

    def item_row(item: dict) -> ft.Container:
        is_selected = item["id"] == selected_id

        def clicked(_e, item_id=item["id"]):
            on_select(item_id)

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            item.get("initials", "?"),
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color="#ffffff",
                        ),
                        bgcolor=item.get("color", "#555555"),
                        border_radius=20,
                        width=40,
                        height=40,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                item["name"],
                                size=13,
                                weight=ft.FontWeight.W_600,
                                color="#ffffff",
                            ),
                            ft.Text(
                                item.get("subtitle", ""),
                                size=11,
                                color="#888888",
                            ),
                        ],
                        spacing=1,
                        expand=True,
                    ),
                    ft.Icon(
                        ft.Icons.CHEVRON_RIGHT,
                        size=16,
                        color=ACCENT if is_selected else "#555555",
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=clicked,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border_radius=8,
            bgcolor=ACCENT + "22" if is_selected else "transparent",
            ink=True,
        )

    list_items = ft.Column(
        controls=[item_row(i) for i in items],
        spacing=2,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    def update_list():
        filtered_items = [i for i in items if search_val["text"] in i["name"].lower()]
        list_items.controls = [item_row(i) for i in filtered_items]
        try:
            list_items.update()
        except AssertionError:
            pass

    add_btn = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.ADD, size=16, color=ACCENT),
                ft.Text(add_label, size=13, color=ACCENT),
            ],
            spacing=6,
            tight=True,
        ),
        on_click=lambda _e: on_add(),
        ink=True,
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
    )

    return ft.Container(
        width=240,
        bgcolor=BG_SIDEBAR,
        border=ft.Border.only(right=ft.BorderSide(1, "#2e2e2e")),
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(header_icon, size=18, color=ACCENT),
                            ft.Text(
                                header_title,
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color="#ffffff",
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=ft.Padding.only(left=12, right=12, top=16, bottom=10),
                ),
                ft.Container(
                    content=search_field,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                ),
                ft.Container(height=8),
                list_items,
                ft.Divider(height=1, color="#2e2e2e"),
                add_btn,
            ],
            spacing=0,
            expand=True,
        ),
    )
