import flet as ft

ACCENT = "#7c3aed"


def build_chat_input(hint: str = "Change hair to red, add a scar...", on_submit=None, on_cancel=None, is_generating: bool = False, generating_message="Generating image…") -> ft.Container:
    text_field = ft.TextField(
        hint_text=hint,
        hint_style=ft.TextStyle(color="#555555", size=13),
        border_radius=10,
        border_color="#333333",
        focused_border_color=ACCENT,
        bgcolor="#2a2a2a",
        color="#ffffff",
        text_size=13,
        expand=True,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        multiline=True,
        min_lines=1,
        max_lines=3,
        shift_enter=True,
    )

    def _handle_submit(value: str, field: ft.TextField):
        if on_submit and value.strip():
            on_submit(value)
        field.value = ""
        try:
            field.update()
        except RuntimeError:
            pass

    def send_clicked(_e):
        _handle_submit(text_field.value, text_field)

    send_btn = ft.Container(
        content=ft.Icon(ft.Icons.SEND_ROUNDED, size=20, color=ACCENT if not is_generating else "#555555"),
        on_click=send_clicked if not is_generating else None,
        ink=not is_generating,
        visible=not is_generating,
        border_radius=8,
        padding=ft.Padding.all(8),
    )

    def cancel_clicked(_e):
        if on_cancel:
            on_cancel()

    cancel_btn = ft.Container(
        content=ft.Icon(ft.Icons.STOP_CIRCLE_ROUNDED, size=20, color="#ff4444"),
        on_click=cancel_clicked,
        ink=True,
        visible=is_generating,
        border_radius=8,
        padding=ft.Padding.all(8),
    )

    generating_indicator = ft.Row(
        controls=[
            ft.ProgressRing(width=16, height=16, stroke_width=2, color=ACCENT),
            ft.Text(generating_message, size=12, color="#aaaaaa", italic=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
        ],
        spacing=8,
        visible=is_generating,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    btn_row = ft.Row(controls=[send_btn, cancel_btn], spacing=0)

    return ft.Container(
        content=ft.Column(
            controls=[
                generating_indicator,
                ft.Row(
                    controls=[text_field, btn_row],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                )
            ],
            spacing=4,
        ),
        bgcolor="#1a1a1a",
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
    )
