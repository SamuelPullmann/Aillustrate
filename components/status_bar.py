import flet as ft


def build_status_bar() -> ft.Container:
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Row(controls=[]),
                ft.Row(
                    controls=[
                        ft.Text(
                            "© 2026 AIllustrate",
                            size=11,
                            color="#444444",
                        ),
                    ],
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#111111",
        padding=ft.Padding.symmetric(horizontal=20, vertical=6),
        border=ft.Border.only(top=ft.BorderSide(1, "#2a2a2a")),
        height=30,
    )
