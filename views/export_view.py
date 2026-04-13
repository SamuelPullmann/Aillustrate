import flet as ft
from components.footer_bar import build_footer_bar
from state.store import ProjectStore
import os

ACCENT = "#7c3aed"


def build_export_view(page: ft.Page, on_tab_change, project_store: ProjectStore = None, on_home=None, on_save=None, on_save_as=None) -> ft.Column:
    from components.top_nav import build_top_nav

    project = project_store.current_project if project_store else None

    char_count = len(project.characters) if project else 0
    env_count = len(project.environments) if project else 0
    scene_count = 0
    if project:
        for ch in project.chapters:
            scene_count += len(ch.scenes)

    export_stats = [
        {"label": "Characters", "value": str(char_count), "icon": ft.Icons.PERSON},
        {"label": "Environments", "value": str(env_count), "icon": ft.Icons.LANDSCAPE},
        {"label": "Scenes", "value": str(scene_count), "icon": ft.Icons.MOVIE_FILTER},
    ]

    selected_format = {"value": "pdf"}

    def format_changed(e):
        selected_format["value"] = e.control.value
        page.update()

    format_radio_group = ft.RadioGroup(
        content=ft.Column([
            ft.Container(
                content=ft.Row([
                   ft.Radio(value="pdf", active_color=ACCENT),
                   ft.Icon(ft.Icons.PICTURE_AS_PDF, size=16, color="#cccccc"),
                   ft.Column([
                       ft.Text("Export as PDF", size=14, color="#ffffff", weight=ft.FontWeight.W_500),
                       ft.Text("High-quality print-ready format", size=12, color="#666666"),
                   ], spacing=2)
                ]),
                bgcolor="#1e1e1e", border_radius=8,
                padding=ft.Padding.symmetric(horizontal=10, vertical=12),
                border=ft.Border.all(1, "#2e2e2e"),
                on_click=lambda _: (setattr(format_radio_group, "value", "pdf"), selected_format.__setitem__("value", "pdf"), page.update())
            ),
            ft.Container(height=8),
            ft.Container(
                content=ft.Row([
                   ft.Radio(value="epub", active_color=ACCENT),
                   ft.Icon(ft.Icons.IMPORT_CONTACTS, size=16, color="#cccccc"),
                   ft.Column([
                       ft.Text("Export as ePub", size=14, color="#ffffff", weight=ft.FontWeight.W_500),
                       ft.Text("Digital e-reader compatible format", size=12, color="#666666"),
                   ], spacing=2)
                ]),
                bgcolor="#1e1e1e", border_radius=8,
                padding=ft.Padding.symmetric(horizontal=10, vertical=12),
                border=ft.Border.all(1, "#2e2e2e"),
                on_click=lambda _: (setattr(format_radio_group, "value", "epub"), selected_format.__setitem__("value", "epub"), page.update())
            ),
        ]),
        value="pdf",
        on_change=format_changed
    )

    action_button_ref = ft.Ref[ft.Container]()
    action_text_ref = ft.Ref[ft.Text]()
    action_icon_ref = ft.Ref[ft.Icon]()

    export_result = {"path": None}

    def open_folder_clicked(_e):
        import subprocess
        import platform
        if export_result["path"]:
            path = export_result["path"]
            folder = os.path.dirname(path)
            if platform.system() == "Windows":
                os.startfile(folder)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])

    def compile_clicked(_e):
        if not project or not project_store or not project_store.project_dir:
            return

        action_button_ref.current.disabled = True
        action_button_ref.current.bgcolor = "#444444"
        action_text_ref.current.value = "Generating..."
        action_icon_ref.current.name = ft.Icons.HOURGLASS_TOP
        action_button_ref.current.on_click = None
        action_button_ref.current.update()

        page.snack_bar = ft.SnackBar(ft.Text("Generating book... please wait."), duration=60000)
        page.snack_bar.open = True
        page.update()

        def run_export_thread():
            from services.export_service import export_to_pdf, export_to_epub
            import time

            success_path = None
            error_msg = None

            try:
                if selected_format["value"] == "pdf":
                    success_path = export_to_pdf(project, project_store.project_dir)
                elif selected_format["value"] == "epub":
                    success_path = export_to_epub(project, project_store.project_dir)
            except Exception as e:
                error_msg = str(e)

            def update_ui_finished():
                try:
                    page.snack_bar.open = False
                except Exception:
                    pass
                if success_path:
                    export_result["path"] = success_path
                    try:
                        action_button_ref.current.disabled = False
                        action_button_ref.current.bgcolor = "#22c55e"
                        action_text_ref.current.value = "Open Export Folder"
                        action_icon_ref.current.name = ft.Icons.FOLDER_OPEN
                        action_button_ref.current.on_click = open_folder_clicked
                        action_button_ref.current.update()
                    except Exception:
                        pass
                    page.snack_bar = ft.SnackBar(ft.Text("Export successful! Saved to exports folder."), action="OK", duration=5000)
                else:
                    try:
                        action_button_ref.current.disabled = False
                        action_button_ref.current.bgcolor = ACCENT
                        action_text_ref.current.value = "Compile & Export Book"
                        action_icon_ref.current.name = ft.Icons.AUTO_AWESOME
                        action_button_ref.current.on_click = compile_clicked
                        action_button_ref.current.update()
                    except Exception:
                        pass
                    page.snack_bar = ft.SnackBar(ft.Text(f"Export failed: {error_msg}"), bgcolor="#ef4444", duration=10000)

                page.snack_bar.open = True
                page.update()

            time.sleep(0.5)
            update_ui_finished()

        if hasattr(page, 'run_thread'):
            page.run_thread(run_export_thread)
        else:
            import threading
            threading.Thread(target=run_export_thread).start()

    def stat_pill(stat: dict) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(stat["icon"], size=14, color=ACCENT),
                    ft.Text(stat["value"], size=13, color="#ffffff", weight=ft.FontWeight.BOLD),
                    ft.Text(stat["label"], size=12, color="#888888"),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#2a2a2a",
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border=ft.Border.all(1, "#3a3a3a"),
        )

    export_card = ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.Container(
                        content=ft.Icon(ft.Icons.MENU_BOOK, size=32, color="#ffffff"),
                        bgcolor=ACCENT, border_radius=14, width=60, height=60,
                        alignment=ft.Alignment.CENTER,
                    ),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(height=8),
                ft.Text("Export Your Book", size=22, weight=ft.FontWeight.BOLD, color="#ffffff", text_align=ft.TextAlign.CENTER),
                ft.Text("Compile your illustrated story into a complete book", size=13, color="#888888", text_align=ft.TextAlign.CENTER),
                ft.Container(height=16),
                ft.Row(controls=[stat_pill(s) for s in export_stats], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                ft.Container(height=20),
                ft.Text("EXPORT FORMATS", size=11, color="#888888", weight=ft.FontWeight.W_600),
                ft.Container(height=8),
                format_radio_group,
                ft.Container(height=24),
                ft.Container(
                    ref=action_button_ref,
                    content=ft.Row(controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME, color="#ffffff", size=20, ref=action_icon_ref),
                        ft.Text("Compile & Export Book", size=15, weight=ft.FontWeight.BOLD, color="#ffffff", ref=action_text_ref),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=10, tight=True),
                    bgcolor=ACCENT, border_radius=10, height=52,
                    on_click=compile_clicked, ink=True, alignment=ft.Alignment.CENTER,
                ),
                ft.Container(height=12),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
        ),
        width=500, bgcolor="#1e1e1e", border_radius=14,
        border=ft.Border.all(1, "#2e2e2e"),
        padding=ft.Padding.all(32),
    )

    nav = build_top_nav("Export", on_tab_change, on_home=on_home, on_save=on_save, on_save_as=on_save_as, project_store=project_store)

    body = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(controls=[export_card], alignment=ft.MainAxisAlignment.CENTER, expand=True),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True,
        ),
        expand=True, bgcolor="#141414",
        padding=ft.Padding.all(24),
    )

    return ft.Column(
        controls=[nav, body, build_footer_bar()],
        spacing=0, expand=True,
    )
