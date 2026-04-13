import flet as ft

_rate_limit_message: str | None = None
_footer_refs: list[ft.Ref] = []


def set_rate_limit_error(msg: str | None):
    global _rate_limit_message
    _rate_limit_message = msg
    for ref in list(_footer_refs):
        try:
            if ref.current and ref.current.page:
                _refresh_footer(ref.current)
                ref.current.update()
        except Exception:
            pass


def _refresh_footer(container: ft.Container):
    left_controls = []
    if _rate_limit_message:
        left_controls.append(
            ft.Text(_rate_limit_message, size=11, color="#ef4444", weight=ft.FontWeight.W_500)
        )
    container.content = ft.Row(
        controls=[
            ft.Row(controls=left_controls),
            ft.Row(controls=[ft.Text("© 2026 AIllustrate", size=11, color="#444444")]),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def build_footer_bar() -> ft.Container:
    ref = ft.Ref[ft.Container]()
    _footer_refs.append(ref)

    container = ft.Container(
        ref=ref,
        bgcolor="#111111",
        padding=ft.Padding.symmetric(horizontal=20, vertical=6),
        border=ft.Border.only(top=ft.BorderSide(1, "#2a2a2a")),
        height=30,
    )
    _refresh_footer(container)
    return container
