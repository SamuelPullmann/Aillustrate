import flet as ft

ACCENT = "#7c3aed"


def build_project_card(project: dict, on_open, on_delete=None) -> ft.Container:
    """Build a clickable project card for the start screen.

    ``project`` must contain at least ``id``, ``title`` and ``date``.
    Calls ``on_open(project_id)`` on click.
    If ``on_delete`` is provided, renders a delete icon button in the top-right corner.
    """
    def clicked(_e, pid=project["id"]):
        try:
            on_open(pid)
        except Exception:
            pass

    image_area = ft.Container(
        bgcolor=project.get("bg_color", "#2a3a4a"),
        height=140,
        border_radius=ft.BorderRadius(top_left=10, top_right=10, bottom_left=0, bottom_right=0),
        content=ft.Container(
            content=ft.Icon(
                ft.Icons.AUTO_STORIES,
                size=48,
                color="#ffffff30",
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
        ),
    )

    info_area = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    project.get("title", "Untitled"),
                    size=13,
                    weight=ft.FontWeight.W_600,
                    color=ACCENT,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    project.get("date", "").upper(),
                    size=10,
                    color="#666666",
                ),
            ],
            spacing=2,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
    )

    card = ft.Container(
        content=ft.Column(
            controls=[image_area, info_area],
            spacing=0,
        ),
        bgcolor="#1e1e1e",
        border_radius=10,
        border=ft.Border.all(1, "#2e2e2e"),
        on_click=clicked,
        ink=True,
        expand=True,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )

    if not on_delete:
        return card

    def _on_delete_click(e, pid=project["id"]):
        try:
            on_delete(pid)
        except Exception:
            pass

    delete_btn = ft.Container(
        content=ft.Icon(ft.Icons.DELETE_OUTLINE, size=18, color="#cccccc"),
        width=36,
        height=36,
        alignment=ft.Alignment.CENTER,
        on_click=_on_delete_click,
        tooltip="Delete Project",
        bgcolor="#00000000",
    )

    return ft.Stack(
        controls=[
            card,
            ft.Container(
                content=delete_btn,
                alignment=ft.Alignment.TOP_RIGHT,
                padding=ft.Padding.all(8),
            ),
        ],
        expand=True,
    )
