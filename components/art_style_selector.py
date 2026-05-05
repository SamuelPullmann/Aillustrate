import flet as ft
from pathlib import Path

ACCENT = "#7c3aed"

_PREVIEWS_DIR = Path(__file__).resolve().parent.parent / "artstyle_previews"

ART_STYLES = [
    {
        "id": "epic_fantasy",
        "label": "Epic Fantasy",
        "color": "#7c3aed",
        "prompt": "Masterpiece, epic fantasy concept art, highly detailed digital painting, vibrant colors, volumetric lighting, cinematic composition, reminiscent of D&D and Magic: The Gathering book covers, 8k resolution, professional illustration."
    },
    {
        "id": "cinematic_realism",
        "label": "Cinematic Realism",
        "color": "#6b7280",
        "prompt": "Masterpiece, cinematic realism, professional digital illustration, sharp focus, dramatic lighting and shadows, depth of field, atmospheric, high-fidelity details, clean and sophisticated composition, realistic textures, 8k resolution, suitable for high-end book covers."
    },
    {
        "id": "oil_painting",
        "label": "Oil Painting",
        "color": "#f59e0b",
        "prompt": "Traditional oil painting illustration, visible brushstrokes, rich colors, canvas texture, painterly style, classical composition, dramatic lighting, reminiscent of N.C. Wyeth and Frank Frazetta, masterpiece, timeless book cover art."
    },
    {
        "id": "storybook_watercolor",
        "label": "Storybook Watercolor",
        "color": "#22d3ee",
        "prompt": "Whimsical children's book illustration, watercolor and colored pencil texture, soft brush strokes, pastel colors, warm and cozy atmosphere, cute and friendly characters, no harsh lines, reminiscent of Beatrix Potter, vintage storybook feel."
    },
    {
        "id": "comic_book_illustration",
        "label": "Comic Book Illustration",
        "color": "#f97316",
        "prompt": "Masterpiece, classic comic book line art, vibrant and bold colors, clean inks, dramatic action poses, heroic composition, hand-drawn comic panel feel, reminiscent of iconic superhero or graphic novel art, highly detailed, genre-agnostic."
    },
]

DETAILS_IMG_H = 520
DETAILS_IMG_W = 300

def build_art_style_selector(selected_id: str, on_select, page: ft.Page = None) -> ft.Column:
    """Build the art style picker row with clickable style thumbnails.

    Highlights the currently selected style. Calls ``on_select(style_id)`` on click.
    If ``page`` is provided, also renders a "View Art Style Details" button that
    opens a full-screen overlay with the style preview and prompt.
    """
    base_selected_id = selected_id.split(" - ")[0] if selected_id else ""

    def style_btn(style: dict) -> ft.Column:
        is_selected = style["id"] == base_selected_id

        def clicked(_e, sid=style["id"]):
            on_select(sid)

        preview_path = _PREVIEWS_DIR / f"{style['id']}.png"
        has_preview = preview_path.is_file()

        IMG_SIZE = 56
        BOX_SIZE = 62
        ITEM_W = 80

        if has_preview:
            inner = ft.Container(
                width=IMG_SIZE, height=IMG_SIZE,
                border_radius=8,
                image=ft.DecorationImage(
                    src=str(preview_path),
                    fit=ft.BoxFit.COVER,
                    alignment=ft.Alignment(0, -1),
                ),
            )
        else:
            inner = ft.Container(
                width=IMG_SIZE, height=IMG_SIZE,
                bgcolor=style["color"],
                border_radius=8,
            )

        check_overlay = ft.Container(
            width=IMG_SIZE, height=IMG_SIZE,
            border_radius=8,
            bgcolor="#00000066" if is_selected else None,
            content=ft.Icon(ft.Icons.CHECK, size=20, color="#ffffff",
                            opacity=1.0 if is_selected else 0.0),
            alignment=ft.Alignment(0, 0),
        )

        color_box = ft.Container(
            width=BOX_SIZE, height=BOX_SIZE,
            border_radius=10,
            border=ft.Border.all(3, ACCENT) if is_selected else ft.Border.all(2, "#444444"),
            content=ft.Stack(controls=[inner, check_overlay]),
            on_click=clicked,
            ink=True,
            padding=ft.Padding.all(3),
        )

        return ft.Column(
            controls=[
                ft.Container(content=color_box, alignment=ft.Alignment.CENTER),
                ft.Container(
                    content=ft.Text(
                        style["label"].upper(),
                        size=9,
                        color=ACCENT if is_selected else "#666666",
                        weight=ft.FontWeight.W_600,
                        text_align=ft.TextAlign.CENTER,
                        no_wrap=False,
                        max_lines=2,
                    ),
                    height=28,
                    alignment=ft.Alignment(0, -1),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
            width=ITEM_W,
        )

    def show_details(_e):
        style = next((s for s in ART_STYLES if s["id"] == base_selected_id), None)
        if not style or not page:
            return

        preview_path = _PREVIEWS_DIR / f"{style['id']}.png"
        has_preview = preview_path.is_file()

        if has_preview:
            img_ctrl = ft.Container(
                width=DETAILS_IMG_W, height=DETAILS_IMG_H,
                border_radius=8,
                image=ft.DecorationImage(
                    src=str(preview_path),
                    fit=ft.BoxFit.COVER,
                    alignment=ft.Alignment(0, -1),
                ),
            )
        else:
            img_ctrl = ft.Container(
                width=DETAILS_IMG_W, height=DETAILS_IMG_H,
                bgcolor=style["color"],
                border_radius=8,
            )

        overlay_ref = ft.Ref[ft.Container]()

        def close_overlay(_e=None):
            try:
                page.overlay.remove(overlay_ref.current)
                page.update()
            except Exception:
                pass

        card = ft.Container(
            width=640,
            bgcolor="#1a1a1a",
            border_radius=12,
            padding=ft.Padding.all(20),
            on_click=lambda e: None,
            content=ft.Column(
                tight=True,
                spacing=0,
                controls=[
                    ft.Row(
                        height=DETAILS_IMG_H,
                        controls=[
                            img_ctrl,
                            ft.Container(width=20),
                            ft.Column(
                                spacing=0,
                                expand=True,
                                controls=[
                                    ft.Text(style["label"], size=18,
                                            weight=ft.FontWeight.BOLD, color="#ffffff"),
                                    ft.Container(height=12),
                                    ft.Text("STYLE PROMPT", size=11, color="#666666",
                                            weight=ft.FontWeight.W_600),
                                    ft.Container(height=6),
                                    ft.Text(style["prompt"], size=12, color="#bbbbbb",
                                            no_wrap=False),
                                    ft.Container(expand=True),
                                    ft.Row(
                                        controls=[
                                            ft.TextButton("Close", on_click=close_overlay,
                                                style=ft.ButtonStyle(color="#888888")),
                                        ],
                                        alignment=ft.MainAxisAlignment.END,
                                    ),
                                ],
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        spacing=0,
                    ),
                ],
            ),
        )

        overlay = ft.Container(
            ref=overlay_ref,
            expand=True,
            bgcolor="#88000000",
            alignment=ft.Alignment(0, 0),
            content=card,
            on_click=close_overlay,
        )

        page.overlay.append(overlay)
        page.update()

    detail_btn = ft.TextButton(
        "View Art Style Details",
        icon=ft.Icons.PALETTE_OUTLINED,
        on_click=show_details,
        style=ft.ButtonStyle(color="#888888"),
    ) if page else ft.Container()

    return ft.Column(
        controls=[
            ft.Text(
                "GLOBAL ART STYLE",
                size=11,
                color="#888888",
                weight=ft.FontWeight.W_600,
            ),
            ft.Row(
                controls=[style_btn(s) for s in ART_STYLES],
                spacing=20,
                run_spacing=14,
                alignment=ft.MainAxisAlignment.CENTER,
                wrap=True,
            ),
            detail_btn,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
    )
