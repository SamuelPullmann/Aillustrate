import warnings
warnings.filterwarnings("ignore", message="Unrecognized FinishReason enum value", category=UserWarning, module="proto")

import flet as ft
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
import asyncio
import sys


def _suppress_connection_reset(loop, context):
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError):
        return
    msg = context.get("message", "")
    if "call_connection_lost" in msg or "ConnectionResetError" in msg:
        return
    loop.default_exception_handler(context)


if sys.platform == "win32":
    try:
        _loop = asyncio.get_event_loop()
        _loop.set_exception_handler(_suppress_connection_reset)
    except RuntimeError:
        pass

from views.start_view import build_start_view
from views.characters_view import build_characters_view
from views.environments_view import build_environments_view
from views.scenes_view import build_scenes_view
from views.export_view import build_export_view
from state.store import ProjectStore, UIStore
from services.project_service import create_project, save_project, load_project, save_project_as
from services.document_service import split_into_chapters
from services.ai_text_service import analyze_all_chapters
from services.ai_image_service import generate_character_portrait, generate_environment_image, generate_scene_image

ACCENT = "#7c3aed"


def pick_project_folder():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askdirectory(title="Select project folder", parent=root)
    root.destroy()
    if not path:
        return None
    return Path(path)


def main(page: ft.Page):
    page.title = "Aillustrate"
    page.window.width = 1600
    page.window.height = 950
    page.window.min_width = 1280
    page.window.min_height = 720
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#141414"
    page.padding = 0

    project_store = ProjectStore()
    ui_store = UIStore()
    workspace_views: dict = {}
    main.project_dialog_open = False

    root_container = ft.Container(expand=True)

    page.snack_bar = ft.SnackBar(content=ft.Text(""))
    page.add(
        ft.Column(
            controls=[root_container],
            expand=True,
            spacing=0,
        )
    )

    def handle_save():
        if project_store.current_project and project_store.project_dir:
            save_project(project_store.current_project, project_store.project_dir)
            page.snack_bar.content = ft.Text("Project saved!")
            page.snack_bar.open = True
            page.update()

    def handle_save_as(new_name):
        if project_store.current_project:
            _, new_dir = create_project(new_name, project_store.current_project.art_style)
            save_project_as(project_store.current_project, new_dir)
            project_store.project_dir = new_dir
            page.snack_bar.content = ft.Text(f"Project saved as '{new_name}'!")
            page.snack_bar.open = True
            page.update()

    def get_workspace_view(tab_name: str) -> ft.Control:
        if tab_name not in workspace_views:
            if tab_name == "Characters":
                workspace_views[tab_name] = build_characters_view(
                    page, on_tab_change,
                    project_store=project_store,
                    ui_store=ui_store,
                    on_home=show_start,
                    on_save=handle_save,
                    on_save_as=handle_save_as,
                )
            elif tab_name == "Environments":
                workspace_views[tab_name] = build_environments_view(
                    page, on_tab_change,
                    project_store=project_store,
                    ui_store=ui_store,
                    on_home=show_start,
                    on_save=handle_save,
                    on_save_as=handle_save_as,
                )
            elif tab_name == "Scenes":
                workspace_views[tab_name] = build_scenes_view(
                    page, on_tab_change,
                    project_store=project_store,
                    ui_store=ui_store,
                    on_home=show_start,
                    on_save=handle_save,
                    on_save_as=handle_save_as,
                )
            elif tab_name == "Export":
                workspace_views[tab_name] = build_export_view(
                    page, on_tab_change,
                    project_store=project_store,
                    on_home=show_start,
                    on_save=handle_save,
                    on_save_as=handle_save_as,
                )
        return workspace_views[tab_name]

    def show_start():
        ui_store.current_screen = "start"
        root_container.content = build_start_view(
            page,
            on_open_project,
            on_analyze=on_analyze,
        )
        root_container.update()
        page.update()

    def show_workspace(tab_name: str = None):
        if tab_name:
            ui_store.active_tab = tab_name
        ui_store.current_screen = "workspace"
        root_container.content = get_workspace_view(ui_store.active_tab)
        root_container.update()
        page.update()

    def on_analyze(
        file_path: str,
        project_name: str,
        art_style: str,
        set_analyzing,
        set_status,
        on_done,
        on_error,
        art_style_id: str = None,
        character_threshold: int = 2,
        generate_all_images: bool = False,
    ):
        """
        Runs heavy work in a background thread so the UI stays responsive.
        """
        ui_store.is_analyzing_book = True
        set_analyzing(True)

        def work():
            try:
                title = project_name.strip() if project_name.strip() else "Untitled"

                set_status("Creating project folder...")
                project, project_dir = create_project(title, art_style_id or art_style, source_file_path=file_path)

                set_status("Splitting text into chapters...")
                chapters = split_into_chapters(file_path)
                project.chapters = chapters

                set_status("Starting AI analysis...")
                characters, environments = analyze_all_chapters(
                    chapters,
                    on_progress=set_status,
                    character_threshold=character_threshold,
                )
                project.characters = characters
                project.environments = environments

                if generate_all_images:
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    import time

                    def _snack(msg: str):
                        try:
                            page.snack_bar.content = ft.Text(msg)
                            page.snack_bar.open = True
                            page.update()
                        except Exception:
                            pass

                    BATCH_SIZE = 6

                    def _run_in_batches(tasks, total_done_offset, total_count, status_label):
                        #Submit tasks in batches of BATCH_SIZE, wait for each batch before submitting next.
                        done = total_done_offset
                        with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
                            for batch_start in range(0, len(tasks), BATCH_SIZE):
                                batch = tasks[batch_start: batch_start + BATCH_SIZE]
                                futures = {}
                                for i, (fn, args, name) in enumerate(batch):
                                    if i > 0:
                                        time.sleep(5)
                                    futures[executor.submit(fn, *args)] = name
                                for f in as_completed(futures):
                                    done += 1
                                    try:
                                        f.result()
                                    except Exception as exc:
                                        _snack(f"Image failed for {futures[f]}: {exc}")
                                    set_status(f"Generated {done}/{total_count} {status_label}...")
                        return done

                    set_status("Generating character and environment images...")
                    char_env_tasks = (
                        [(generate_character_portrait, (char, art_style, project_dir), char.name) for char in characters] +
                        [(generate_environment_image, (env, art_style, project_dir), env.name) for env in environments]
                    )
                    _run_in_batches(char_env_tasks, 0, len(char_env_tasks), "character/environment images")

                    save_project(project, project_dir)

                    all_scenes = [sc for ch in chapters for sc in ch.scenes]
                    if all_scenes:
                        set_status("Generating scene images...")
                        scene_tasks = [
                            (
                                generate_scene_image,
                                (
                                    sc,
                                    [c for c in characters if c.id in sc.character_ids][:5],
                                    next((e for e in environments if e.id == sc.environment_id), None),
                                    art_style, project_dir, characters,
                                ),
                                sc.title,
                            )
                            for sc in all_scenes
                        ]
                        _run_in_batches(scene_tasks, 0, len(scene_tasks), "scene images")
                        save_project(project, project_dir)

                set_status("Saving project...")
                save_project(project, project_dir)

                project_store.current_project = project
                project_store.project_dir = project_dir
                ui_store.is_analyzing_book = False
                on_done(project_dir)

            except Exception as exc:
                ui_store.is_analyzing_book = False
                on_error(str(exc))

        page.run_thread(work)

    def on_open_project(project_id: str = "open"):
        if project_id == "open":
            if main.project_dialog_open:
                return
            main.project_dialog_open = True
            try:
                project_dir = pick_project_folder()
                if not project_dir:
                    return
                project = load_project(project_dir)
                project_store.current_project = project
                project_store.project_dir = project_dir
            except Exception as exc:
                root_container.content = ft.Text(f"Failed to load project: {exc}")
                root_container.update()
                return
            finally:
                main.project_dialog_open = False

        elif project_id != "new":
            if not (project_store.current_project is not None
                    and project_store.project_dir is not None
                    and str(project_store.project_dir) == project_id):
                try:
                    project_dir = Path(project_id)
                    project = load_project(project_dir)
                    project_store.current_project = project
                    project_store.project_dir = project_dir
                except Exception as exc:
                    root_container.content = ft.Text(f"Failed to load project: {exc}")
                    root_container.update()
                    return

        workspace_views.clear()
        show_workspace("Characters")

    def on_tab_change(tab_name: str):
        workspace_views.clear()
        show_workspace(tab_name)

    def on_keyboard(e):
        if e.key == "Escape" and ui_store.current_screen == "workspace":
            show_start()

    page.on_keyboard_event = on_keyboard

    show_start()


ft.run(main)
