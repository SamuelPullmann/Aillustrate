import flet as ft
import os
import threading
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

from components.art_style_selector import build_art_style_selector, ART_STYLES
from components.project_card import build_project_card
from components.footer_bar import build_footer_bar
from services.project_service import list_projects, delete_project, get_project_dir
from config import MAX_ANALYZE_CHAPTERS  # intentionally kept for future use

ACCENT = "#7c3aed"



def _btn(content, on_click, bgcolor="#2a2a2a", border_color="#444444", radius=8, height=40, expand=False):
    return ft.Container(
        content=content,
        bgcolor=bgcolor,
        border_radius=radius,
        border=ft.Border.all(1, border_color),
        height=height,
        on_click=on_click,
        ink=True,
        expand=expand,
        padding=ft.Padding.symmetric(horizontal=14, vertical=0),
        alignment=ft.Alignment.CENTER,
    )


def build_start_view(page: ft.Page, on_open_project, file_picker=None, on_analyze=None) -> ft.Column:
    selected_style_ref = {"value": "epic_fantasy"}
    art_style_container = ft.Ref[ft.Column]()
    drop_zone_ref = ft.Ref[ft.Container]()
    analyze_btn_ref = ft.Ref[ft.Container]()
    threshold_ref = {"value": 0}
    picked_file_ref = {"path": None}
    generate_all_ref = {"value": False}

    is_analyzing = {"value": False}
    projects_column_ref = ft.Ref[ft.Column]()
    _saved_projects_cache = {"items": None}
    modal_ref = ft.Ref[ft.Container]()

    def on_open(pid: str):
        items = _saved_projects_cache.get("items")
        if items:
            for p in items:
                if p["id"] == pid:
                    on_open_project(p.get("dir_path", pid))
                    return
        on_open_project(pid)

    def on_open_project_dialog(_e):
        on_open_project("open")

    # Helper to show in-UI confirm modal
    def hide_confirm_modal():
        try:
            if modal_ref.current:
                modal_ref.current.visible = False
                modal_ref.current.content = None
                page.update()
        except Exception:
            pass

    def show_confirm_modal(pid: str, title: str):
        try:
            confirm_box = ft.Container(
                width=520,
                height=140,
                padding=ft.Padding.all(16),
                bgcolor="#1b1b1b",
                border_radius=8,
                content=ft.Column(
                    controls=[
                        ft.Text("Confirm Delete", size=14, weight=ft.FontWeight.W_700),
                        ft.Container(height=6),
                        ft.Text(f"Are you sure you want to delete '{title}'?", size=12),
                        ft.Container(height=10),
                        ft.Row(
                            controls=[
                                ft.ElevatedButton("Cancel", on_click=lambda e: hide_confirm_modal(), bgcolor="#2a2a2a"),
                                ft.Container(width=12),
                                ft.ElevatedButton("Delete", on_click=lambda e: delete_confirmed(pid, modal_placeholder), bgcolor="#ff4444"),
                            ],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ],
                    spacing=6,
                ),
            )

            modal_content = ft.Container(
                content=confirm_box,
                alignment=ft.Alignment.CENTER,
                expand=True,
                bgcolor="#00000088",
            )

            if modal_ref and getattr(modal_ref, 'current', None):
                modal_ref.current.content = modal_content
                modal_ref.current.visible = True
                modal_ref.current.width = page.client_size.width if hasattr(page, 'client_size') else None
                page.update()
                return

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Confirm Delete"),
                content=ft.Text(f"Are you sure you want to delete '{title}'? This action cannot be undone."),
            )

            def _dlg_cancel(e):
                try:
                    dlg.open = False
                    page.update()
                except Exception:
                    pass

            def _dlg_delete(e):
                delete_confirmed(pid, dlg)

            dlg.actions = [
                ft.TextButton("Cancel", on_click=_dlg_cancel),
                ft.TextButton("Delete", on_click=_dlg_delete, style=ft.ButtonStyle(color="#ff4444")),
            ]
            dlg.actions_alignment = ft.MainAxisAlignment.END
            try:
                if hasattr(page, "open"):
                    page.open(dlg)
                else:
                    page.dialog = dlg
                    dlg.open = True
                    page.update()
            except Exception:
                pass
        except Exception:
            pass

    def refresh_projects():
        saved_projects = list_projects()
        _saved_projects_cache["items"] = saved_projects

        project_rows = []
        for i in range(0, len(saved_projects), 2):
            pair = saved_projects[i: i + 2]
            row_controls = []
            for p in pair:
                try:
                    card_ctrl = build_project_card(p, on_open, on_delete=on_delete_request)
                    row_controls.append(ft.Container(content=card_ctrl, expand=True))
                except Exception:
                    placeholder = ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Failed to render project", color="#ff4444"),
                                ft.Text(str(p.get("id")), color="#cccccc", size=11),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        height=180,
                        bgcolor="#222222",
                        border_radius=10,
                        padding=ft.Padding.all(12),
                        expand=True,
                    )
                    row_controls.append(placeholder)
            while len(row_controls) < 2:
                row_controls.append(ft.Container(expand=True))
            project_rows.append(ft.Row(controls=row_controls, spacing=12))

        if projects_column_ref.current:
            projects_column_ref.current.controls = project_rows
            projects_column_ref.current.update()

    def close_dialog(dlg):
        if hasattr(page, "close"):
            page.close(dlg)
        else:
            dlg.open = False
            page.update()

    def on_style_select(style_id: str):
        selected_style_ref["value"] = style_id
        try:
            new_selector = build_art_style_selector(style_id, on_style_select, page=page)
            # If the ref has been created and attached, replace its controls
            if art_style_container and getattr(art_style_container, 'current', None):
                art_style_container.current.controls = new_selector.controls
                art_style_container.current.update()
        except Exception:
            pass

    def delete_confirmed(pid: str, dlg):
        try:
            if dlg is not None:
                try:
                    close_dialog(dlg)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if modal_ref and getattr(modal_ref, 'current', None):
                modal_ref.current.visible = False
                modal_ref.current.content = None
                page.update()
        except Exception:
            pass

        try:
            p_path = Path(pid) if Path(pid).exists() else get_project_dir(pid)
            delete_project(p_path)
            try:
                page.snack_bar.content = ft.Text(f"Deleted project: {pid}")
                page.snack_bar.open = True
                page.update()
            except Exception:
                pass
        except Exception as exc:
            try:
                page.snack_bar.content = ft.Text(f"Failed to delete: {exc}")
                page.snack_bar.open = True
                page.update()
            except Exception:
                pass

        # 2. Refresh list
        refresh_projects()

    _delete_confirm_pending = set()

    def _clear_pending(pid: str):
        try:
            _delete_confirm_pending.discard(pid)
        except Exception:
            pass

    def on_delete_request(pid: str):
        title = pid
        for p in (_saved_projects_cache.get("items") or []):
            if p.get("id") == pid:
                title = p.get("title", pid)
                break

        try:
            show_confirm_modal(pid, title)
            return
        except Exception:
            pass

        try:
            modal_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Confirm Delete"),
                content=ft.Text(f"Are you sure you want to delete '{title}'? This action cannot be undone."),
            )

            def _on_yes(e):
                delete_confirmed(pid, modal_dlg)

            def _on_no(e):
                try:
                    modal_dlg.open = False
                    page.update()
                except Exception:
                    pass

            modal_dlg.actions = [
                ft.TextButton("Cancel", on_click=_on_no),
                ft.TextButton("Delete", on_click=_on_yes, style=ft.ButtonStyle(color="#ff4444")),
            ]
            modal_dlg.actions_alignment = ft.MainAxisAlignment.END

            if hasattr(page, "open"):
                page.open(modal_dlg)
            else:
                page.dialog = modal_dlg
                modal_dlg.open = True
                page.update()
        except Exception:
            pass
        return

    project_name_field = ft.TextField(
        hint_text="Enter project name...",
        hint_style=ft.TextStyle(color="#555555", size=13),
        border_radius=8,
        border_color="#444444",
        focused_border_color=ACCENT,
        bgcolor="#242424",
        color="#ffffff",
        text_size=13,
        height=44,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=0),
        prefix_icon=ft.Icons.DRIVE_FILE_RENAME_OUTLINE,
    )

    error_text = ft.Text("", size=12, color="#ff4444", text_align=ft.TextAlign.CENTER)
    progress_text = ft.Text("", size=11, color="#aaaaaa", text_align=ft.TextAlign.CENTER, italic=True)
    file_dialog_open = {"value": False}

    def on_file_pick_result(file_path):
        file_dialog_open["value"] = False
        if file_path:
            picked_file_ref["path"] = file_path
            file_name = os.path.basename(file_path)
            name_without_ext = file_name.rsplit(".", 1)[0]
            if not project_name_field.value:
                project_name_field.value = name_without_ext
            drop_zone_ref.current.content.controls[1].value = file_name
            drop_zone_ref.current.content.controls[1].color = "#aaaaaa"
            drop_zone_ref.current.border = ft.Border.all(2, ACCENT)
            error_text.value = ""
            page.update()

    def drop_zone_clicked(_e):
        if file_dialog_open["value"]:
            return
        file_dialog_open["value"] = True

        def pick():
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Select your story file",
                filetypes=[("Supported files", "*.txt *.pdf *.epub"), ("All files", "*.*")],
            )
            root.destroy()
            on_file_pick_result(path)

        threading.Thread(target=pick, daemon=True).start()

    def set_status(message: str):
        progress_text.value = message
        try:
            progress_text.update()
        except Exception:
            pass  # Control may not be on page yet

    def set_analyzing(state: bool):
        is_analyzing["value"] = state
        btn = analyze_btn_ref.current
        if state:
            btn.content = ft.Row(
                controls=[
                    ft.ProgressRing(width=20, height=20, stroke_width=2, color="#ffffff"),
                    ft.Text("Analyzing...", size=15, weight=ft.FontWeight.BOLD, color="#ffffff"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            )
            btn.bgcolor = "#5a2ea0"
            btn.on_click = None  # Disable clicking while analyzing
        else:
            btn.content = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_FIX_HIGH, color="#ffffff", size=20),
                    ft.Text(f"Analyze Book with AI", size=15, weight=ft.FontWeight.BOLD, color="#ffffff"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            )
            btn.bgcolor = ACCENT
            btn.on_click = analyze_clicked
            progress_text.value = ""
            try:
                progress_text.update()
            except Exception:
                pass
        btn.update()

    def analyze_clicked(_e):
        if is_analyzing["value"]:
            return

        if not picked_file_ref["path"]:
            error_text.value = "Please select a story file first."
            error_text.update()
            return

        error_text.value = ""
        error_text.update()

        if on_analyze:
            style_id = selected_style_ref["value"]
            style_prompt = style_id
            for s in ART_STYLES:
                if s["id"] == style_id:
                    style_prompt = f"{s['label']} - {s.get('prompt', '')}"
                    break

            def on_done(project_dir=None):
                set_analyzing(False)
                on_open_project(str(project_dir) if project_dir else (project_name_field.value or "Untitled"))

            def on_error(msg: str):
                set_analyzing(False)
                error_text.value = msg
                error_text.update()

            on_analyze(
                file_path=picked_file_ref["path"],
                project_name=project_name_field.value or "",
                art_style=style_prompt,
                art_style_id=style_id,
                set_analyzing=set_analyzing,
                set_status=set_status,
                on_done=on_done,
                on_error=on_error,
                character_threshold=int(threshold_ref["value"]),
                generate_all_images=generate_all_ref["value"],
            )

    analyze_btn = ft.Container(
        ref=analyze_btn_ref,
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.AUTO_FIX_HIGH, color="#ffffff", size=20),
                ft.Text(f"Analyze Book with AI", size=15, weight=ft.FontWeight.BOLD, color="#ffffff"),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        ),
        bgcolor=ACCENT,
        border_radius=10,
        height=52,
        on_click=analyze_clicked,
        ink=True,
    )

    saved_projects = list_projects()
    _saved_projects_cache["items"] = saved_projects
    initial_project_rows = []

    for i in range(0, len(saved_projects), 2):
        pair = saved_projects[i: i + 2]
        row_controls = []
        for p in pair:
            try:
                card_ctrl = build_project_card(p, on_open, on_delete=on_delete_request)
                row_controls.append(ft.Container(content=card_ctrl, expand=True))
            except Exception:
                placeholder = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Failed to render project", color="#ff4444"),
                            ft.Text(str(p.get("id")), color="#cccccc", size=11),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    height=180,
                    bgcolor="#222222",
                    border_radius=10,
                    padding=ft.Padding.all(12),
                    expand=True,
                )
                row_controls.append(placeholder)
        while len(row_controls) < 2:
            row_controls.append(ft.Container(expand=True))
        initial_project_rows.append(ft.Row(controls=row_controls, spacing=12))

    open_btn = _btn(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.FOLDER_OPEN, size=16, color="#cccccc"),
                ft.Text("OPEN PROJECT", size=12, color="#cccccc", weight=ft.FontWeight.W_600),
            ],
            spacing=6,
            tight=True,
        ),
        on_click=on_open_project_dialog,
        height=36,
    )

    left_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Row(controls=[
                            ft.Icon(ft.Icons.HISTORY, size=20, color=ACCENT),
                            ft.Text("Recent Projects", size=16, weight=ft.FontWeight.BOLD, color="#ffffff"),
                        ], spacing=8),
                        open_btn,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=10),
                ft.Column(
                    ref=projects_column_ref,
                    controls=initial_project_rows,
                    spacing=12,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True
                ),
            ],
            spacing=0,
            expand=True,
        ),
        expand=True,
        padding=ft.Padding.all(20),
        bgcolor="#1c1c1c",
        border_radius=10,
        border=ft.Border.all(1, "#2e2e2e"),
    )

    try:
        refresh_projects()
    except Exception:
        pass

    drop_zone = ft.Container(
        ref=drop_zone_ref,
        content=ft.Column(
            controls=[
                ft.Icon(ft.Icons.UPLOAD_FILE_OUTLINED, size=32, color="#555555"),
                ft.Text("Drop your story files here", size=14, weight=ft.FontWeight.W_600, color="#888888", text_align=ft.TextAlign.CENTER),
                ft.Text("(.txt, .pdf, .epub)", size=11, color="#555555", text_align=ft.TextAlign.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
        ),
        alignment=ft.Alignment.CENTER,
        border=ft.Border.all(2, "#444444"),
        border_radius=12,
        height=110,
        on_click=drop_zone_clicked,
        ink=True,
        bgcolor="#1e1e1e",
        expand=False,
    )

    initial_selector = build_art_style_selector(selected_style_ref["value"], on_style_select, page=page)

    art_col = ft.Column(
        ref=art_style_container,
        controls=initial_selector.controls,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=initial_selector.spacing,
    )

    threshold_label = ft.Text(f"CHARACTER THRESHOLD: {int(threshold_ref['value'])}%", size=11, color="#888888", weight=ft.FontWeight.W_600)

    def on_threshold_change(e):
        threshold_ref["value"] = e.control.value
        threshold_label.value = f"CHARACTER THRESHOLD: {int(e.control.value)}%"
        try:
            threshold_label.update()
        except Exception:
            pass

    threshold_slider = ft.Slider(
        min=0, max=100, value=threshold_ref["value"],
        divisions=20, label="{value}%",
        active_color=ACCENT,
        inactive_color="#333333",
        on_change=on_threshold_change,
        expand=True,
    )

    hover_helper = ft.Container(
        content=ft.Text("Sets required % of chapters a character must appear in to be kept. Characters used in scenes are always preserved.", size=11, color="#dddddd"),
        padding=ft.Padding.symmetric(horizontal=8, vertical=8),
        bgcolor="#222222",
        border_radius=6,
        visible=False,
        expand=True,
    )

    def on_info_enter(e=None):
        hover_helper.visible = True
        try:
            page.update()
        except Exception:
            pass

    def on_info_exit(e=None):
        hover_helper.visible = False
        try:
            page.update()
        except Exception:
            pass

    def _choose_icon():
        for n in ("INFO_OUTLINE", "INFO", "HELP", "HELP_OUTLINE"):
            try:
                if hasattr(ft.Icons, n):
                    return getattr(ft.Icons, n)
            except Exception:
                pass
        return ft.Icons.HELP

    info_icon_const = _choose_icon()

    info_widget = None
    MouseRegion = getattr(ft, 'MouseRegion', None)
    if MouseRegion is not None:
        try:
            info_widget = MouseRegion(
                content=ft.Container(content=ft.Icon(info_icon_const, size=16, color="#cccccc")),
                on_enter=on_info_enter,
                on_hover=on_info_enter,
                on_exit=on_info_exit,
            )
        except Exception:
            info_widget = None

    if info_widget is None:
        hover_helper.visible = False
        info_widget = ft.Container(
            content=ft.Icon(info_icon_const, size=16, color="#cccccc"),
            tooltip="Sets required % of chapters a character must appear in to be kept. Characters used in scenes are always preserved."
        )

    label_and_info_row = ft.Row(
        controls=[
            threshold_label,
            ft.Container(width=8),
            info_widget,
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.START,
    )

    threshold_block = ft.Column(
        controls=[
            label_and_info_row,
            ft.Container(height=6),
            ft.Container(content=threshold_slider, expand=True),
            ft.Container(height=8),
            hover_helper,
        ],
        spacing=0,
        expand=False,
    )

    def on_generate_all_change(e):
        generate_all_ref["value"] = e.control.value

    generate_all_checkbox = ft.Checkbox(
        label="Generate all images after analysis",
        value=False,
        on_change=on_generate_all_change,
        active_color=ACCENT,
        label_style=ft.TextStyle(size=12, color="#aaaaaa"),
    )

    analyze_btn = ft.Container(
        ref=analyze_btn_ref,
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.AUTO_FIX_HIGH, color="#ffffff", size=20),
                ft.Text(f"Analyze Book with AI", size=15, weight=ft.FontWeight.BOLD, color="#ffffff"),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        ),
        bgcolor=ACCENT,
        border_radius=10,
        height=52,
        on_click=analyze_clicked,
        ink=True,
    )

    right_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(height=8),
                ft.Text("Aillustrate", size=26, weight=ft.FontWeight.BOLD, color="#ffffff", text_align=ft.TextAlign.CENTER, expand=True),
                ft.Row(
                    controls=[ft.Container(height=3, width=50, bgcolor=ACCENT, border_radius=2)],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Container(height=16),
                drop_zone,
                ft.Container(height=10),
                ft.Text("PROJECT NAME", size=11, color="#888888", weight=ft.FontWeight.W_600),
                ft.Container(height=4),
                project_name_field,
                ft.Container(height=14),
                art_col,
                ft.Container(height=10),
                threshold_block,
                ft.Container(height=8),
                generate_all_checkbox,
                ft.Container(height=8),
                analyze_btn,
                ft.Container(height=4),
                error_text,
                progress_text,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        padding=ft.Padding.symmetric(horizontal=28, vertical=20),
        bgcolor="#1c1c1c",
        border_radius=10,
        border=ft.Border.all(1, "#2e2e2e"),
        expand=True,
    )

    import config as _config
    _all_models = getattr(_config, 'IMAGE_MODELS', [])
    if not _all_models:
        _fb = getattr(_config, 'IMAGE_MODEL', None)
        _all_models = [_fb] if _fb else []

    from components.top_nav import _view_models, get_active_model
    _current_model_val = _view_models.get("Characters") or get_active_model()
    model_text_start = ft.Text(_current_model_val or "", size=12, color="#cccccc")

    def _set_model_global(m, e=None):
        for tab in ["Characters", "Environments", "Scenes", "Export"]:
            _view_models[tab] = m
        try:
            model_text_start.value = m
            model_text_start.update()
        except Exception:
            pass
        try:
            page.snack_bar.content = ft.Text(f"Image model set: {m}")
            page.snack_bar.open = True
            page.update()
        except Exception:
            pass

    _model_popup_items = [
        ft.PopupMenuItem(content=ft.Text(m), on_click=lambda e, m=m: _set_model_global(m, e))
        for m in _all_models
    ]

    model_selector_start = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.IMAGE_OUTLINED, size=14, color="#aaaaaa"),
                ft.Text("Model:", size=12, color="#aaaaaa"),
                model_text_start,
                ft.PopupMenuButton(
                    icon=ft.Icons.ARROW_DROP_DOWN,
                    items=_model_popup_items,
                    tooltip="Select image model",
                    style=ft.ButtonStyle(
                        bgcolor={"": "#242424"},
                        padding={"": ft.Padding.symmetric(horizontal=8, vertical=6)},
                        shape={"": ft.RoundedRectangleBorder(radius=6)},
                    ),
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#242424",
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
    )

    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Row(controls=[
                    ft.Container(
                        content=ft.Text("S", size=14, weight=ft.FontWeight.BOLD, color="#ffffff"),
                        bgcolor=ACCENT, border_radius=6, width=28, height=28,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Text("Aillustrate", size=15, weight=ft.FontWeight.BOLD, color="#ffffff"),
                ], spacing=8),
                model_selector_start,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#141414",
        padding=ft.Padding.symmetric(horizontal=20, vertical=10),
        border=ft.Border.only(bottom=ft.BorderSide(1, "#2a2a2a")),
    )

    main_col = ft.Column(
        controls=[
            header,
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(content=left_panel, expand=3),
                        ft.Container(width=16),
                        ft.Container(content=right_panel, expand=2),
                    ],
                    spacing=0,
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
                expand=True,
                padding=ft.Padding.all(16),
                bgcolor="#141414",
            ),
            build_footer_bar(),
        ],
        spacing=0,
        expand=True,
    )

    modal_placeholder = ft.Container(ref=modal_ref, visible=False, expand=True)

    return ft.Stack(
        controls=[main_col, modal_placeholder],
        expand=True,
    )
