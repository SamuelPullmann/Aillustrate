import flet as ft
import random
from pathlib import Path

from components.chat_input import build_chat_input
from components.image_source import get_refreshable_image_src
from components.footer_bar import build_footer_bar
from state.store import ProjectStore
from services.ai_image_service import generate_environment_image, edit_image, undo_image_edit
from services.project_service import save_project
from models.environment import Environment

ACCENT = "#7c3aed"

_AVATAR_COLORS = ["#7c3aed", "#16a34a", "#0369a1", "#b45309", "#dc2626", "#4338ca", "#0f766e", "#7c2d12"]


def _color_for_index(i: int) -> str:
    return _AVATAR_COLORS[i % len(_AVATAR_COLORS)]


def _initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()


def build_environments_view(page: ft.Page, on_tab_change, project_store: ProjectStore = None, ui_store=None, on_home=None, on_save=None, on_save_as=None) -> ft.Column:
    project = project_store.current_project if project_store else None
    environments = project.environments if project else []

    # Restore previously selected environment from ui_store, fallback to first
    _initial_sel = None
    if ui_store and getattr(ui_store, 'selected_environment_id', None):
        if any(e.id == ui_store.selected_environment_id for e in environments):
            _initial_sel = ui_store.selected_environment_id
    if _initial_sel is None:
        _initial_sel = environments[0].id if environments else None
    selected_ref = {"value": _initial_sel}
    wrapper_ref = {"container": None}

    if not hasattr(page, "generating_ids"):
        page.generating_ids = set()
    generating_ids = page.generating_ids

    error_ref = {"value": ""}
    if not hasattr(page, "gen_status"):
        page.gen_status = {}
    gen_status = page.gen_status

    def get_env(eid):
        for e in environments:
            if e.id == eid:
                return e
        return environments[0] if environments else None

    def on_select(eid):
        selected_ref["value"] = eid
        if ui_store:
            ui_store.selected_environment_id = eid
        rebuild()

    def on_add():
        try:
            def close_dlg(_e):
                dlg.open = False
                page.update()

            def save_new(_e):
                try:
                    if not name_field.value:
                        name_field.error_text = "Name is required"
                        name_field.update()
                        return

                    new_env = Environment(
                        name=name_field.value,
                        merged_description=desc_field.value
                    )

                    if project:
                        project.environments.append(new_env)
                        save_project(project, project_store.project_dir)

                    dlg.open = False
                    page.update()

                    on_select(new_env.id)
                    rebuild()

                    page.snack_bar = ft.SnackBar(ft.Text(f"Added environment: {new_env.name}"))
                    page.snack_bar.open = True
                    page.update()

                except Exception as e:
                    dlg.open = False
                    page.update()
                    _show_error(f"Failed to add environment: {e}")

            name_field = ft.TextField(
                label="Name",
                autofocus=True,
                text_size=14,
                bgcolor="#252525",
                border_color="#444444",
                focused_border_color=ACCENT,
                border_radius=8,
                height=48,
                content_padding=ft.Padding.symmetric(horizontal=15, vertical=12),
            )
            desc_field = ft.TextField(
                hint_text="Description",
                multiline=True,
                min_lines=5,
                max_lines=10,
                text_size=14,
                bgcolor="#252525",
                border_color="#444444",
                focused_border_color=ACCENT,
                border_radius=8,
                content_padding=ft.Padding.all(15),
            )

            dlg = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_ROUNDED, color=ACCENT, size=28),
                    ft.Text("Create Environment", size=22, weight=ft.FontWeight.W_600, color="#ffffff")
                ], spacing=12, alignment=ft.MainAxisAlignment.START),
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("Define a new location or setting.", size=14, color="#AAAAAA"),
                        ft.Container(height=10),
                        name_field,
                        ft.Container(height=5),
                        desc_field
                    ], tight=True, spacing=5, width=500, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                    padding=ft.Padding.symmetric(vertical=10, horizontal=5),
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=close_dlg, style=ft.ButtonStyle(color="#888888")),
                    ft.Container(width=5),
                    ft.ElevatedButton(
                        "Create Environment",
                        icon=ft.Icons.CHECK,
                        on_click=save_new,
                        style=ft.ButtonStyle(
                            bgcolor=ACCENT,
                            color="#ffffff",
                            elevation=0,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=20, vertical=12)
                        )
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                bgcolor="#1a1a1a",
                shape=ft.RoundedRectangleBorder(radius=12),
                modal=True
            )
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

        except Exception as e:
            _show_error(f"Error opening dialog: {e}")

    if not hasattr(page, "cancel_events"):
        page.cancel_events = {}

    def on_generate(_e):
        import threading as _threading
        env = get_env(selected_ref["value"])
        if not env or not project_store or not project_store.project_dir:
            return

        old_ev = page.cancel_events.get(env.id)
        if old_ev:
            old_ev.set()

        if not getattr(env, "seed_locked", False):
            env.seed = random.randint(0, 2147483647)
            _save()

        error_ref["value"] = ""
        cancel_event = _threading.Event()
        page.cancel_events[env.id] = cancel_event
        generating_ids.add(env.id)
        gen_status.pop(env.id, None)
        rebuild()

        def on_gen_status(msg: str, eid=env.id, ev=cancel_event):
            if ev.is_set():
                return
            gen_status[eid] = msg
            if wrapper_ref["container"] and wrapper_ref["container"].page:
                rebuild()

        def work(ev=cancel_event):
            try:
                generate_environment_image(
                    env, project.art_style, project_store.project_dir,
                    on_status=on_gen_status, cancel_event=ev,
                )
                if not ev.is_set():
                    env.refinement_history.clear()
                    save_project(project, project_store.project_dir)
            except InterruptedError:
                pass
            except Exception as exc:
                if not ev.is_set() and wrapper_ref["container"] and wrapper_ref["container"].page:
                    _show_error(f"Environment image generation failed: {exc}")

            if page.cancel_events.get(env.id) is ev:
                page.cancel_events.pop(env.id, None)
                if env.id in generating_ids:
                    generating_ids.discard(env.id)
                gen_status.pop(env.id, None)
                if wrapper_ref["container"] and wrapper_ref["container"].page:
                    rebuild()

        page.run_thread(work)

    def on_undo(_e):
        env = get_env(selected_ref["value"])
        if not env or not env.image_path_history or env.id in generating_ids:
            return
        env.image_path = env.image_path_history.pop()
        _save()
        rebuild()

    global_cancel_ref = {"cancelled": False}

    def on_chat_submit(text: str):
        env = get_env(selected_ref["value"])
        if not env or not env.image_path or not Path(env.image_path).is_file() or env.id in generating_ids:
            return
        error_ref["value"] = ""
        generating_ids.add(env.id)
        global_cancel_ref["cancelled"] = False
        rebuild()

        def work():
            local_cancel = dict(global_cancel_ref)
            try:
                old_path = env.image_path
                new_path = edit_image(env.image_path, text)
                if not local_cancel.get("cancelled", False):
                    if not hasattr(env, 'image_path_history'):
                        env.image_path_history = []
                    env.image_path_history.append(old_path)
                    env.image_path = new_path
                    if not hasattr(env, 'refinement_history'):
                        env.refinement_history = []
                    env.refinement_history.append(text)
                    save_project(project, project_store.project_dir)
                else:
                    try:
                        Path(new_path).unlink(missing_ok=True)
                    except Exception:
                        pass
            except Exception as exc:
                if not local_cancel.get("cancelled", False) and wrapper_ref["container"] and wrapper_ref["container"].page:
                    _show_error(f"Environment image edit failed: {exc}")

            if env.id in generating_ids:
                generating_ids.remove(env.id)
            if wrapper_ref["container"] and wrapper_ref["container"].page:
                rebuild()

        page.run_thread(work)

    def cancel_refinement():
        global_cancel_ref["cancelled"] = True
        env = get_env(selected_ref["value"])
        if env:
            ev = page.cancel_events.get(env.id)
            if ev:
                ev.set()
            gen_status.pop(env.id, None)
            generating_ids.discard(env.id)
        rebuild()

    def _save():
        if project_store and project_store.project_dir:
            save_project(project, project_store.project_dir)

    def _show_error(message: str):
        error_ref["value"] = message
        try:
            if page:
                page.snack_bar.content = ft.Text(message)
                page.snack_bar.open = True
                page.update()
        except Exception:
            pass

    def _sidebar_items():
        current_list = project.environments if project else []
        items = []
        for i, e in enumerate(current_list):
            items.append({
                "id": e.id,
                "name": e.name,
                "subtitle": f"{len(e.descriptions_by_chapter)} chapters",
                "initials": _initials(e.name),
                "color": _color_for_index(i),
            })
        return items

    def build_sidebar() -> ft.Container:
        items = _sidebar_items()
        search_val = {"text": ""}

        controls_ref = {"list": None}

        def on_search_change(e):
            search_val["text"] = e.control.value.lower()
            filtered = [i for i in items if search_val["text"] in i["name"].lower()]
            if controls_ref["list"]:
                controls_ref["list"].controls = [item_row(i) for i in filtered]
                try:
                    controls_ref["list"].update()
                except Exception:
                    pass

        search_field = ft.TextField(
            hint_text="Search environments...",
            hint_style=ft.TextStyle(color="#666666", size=13),
            prefix_icon=ft.Icons.SEARCH,
            border_radius=8, border_color="#333333", focused_border_color=ACCENT,
            bgcolor="#242424", color="#ffffff", height=42, text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            on_change=on_search_change,
        )

        def item_row(item):
            is_sel = item["id"] == selected_ref["value"]

            def clicked(_e, eid=item["id"]):
                on_select(eid)

            env_obj = get_env(item["id"])
            has_image = env_obj and env_obj.image_path and Path(env_obj.image_path).is_file()

            avatar_content = ft.Text(item["initials"], size=11, weight=ft.FontWeight.BOLD, color="#ffffff")
            if has_image:
                 avatar_content = ft.Image(
                     src=get_refreshable_image_src(env_obj.image_path),
                     fit=ft.BoxFit.COVER,
                     expand=True,
                     border_radius=20
                 )

            return ft.Container(
                content=ft.Row(controls=[
                    ft.Container(
                        content=avatar_content,
                        bgcolor=item["color"] if not has_image else None,
                        border_radius=20, width=40, height=40,
                        alignment=ft.Alignment.CENTER,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    ),
                    ft.Column(controls=[
                        ft.Text(item["name"], size=13, weight=ft.FontWeight.W_600, color="#ffffff", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(item["subtitle"], size=11, color="#888888"),
                    ], spacing=1, expand=True),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color=ACCENT if is_sel else "#555555"),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                on_click=clicked, padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=8, bgcolor=ACCENT + "22" if is_sel else "transparent", ink=True,
            )

        controls_list = ft.Column(controls=[item_row(i) for i in items], spacing=2, scroll=ft.ScrollMode.AUTO, expand=True)
        controls_ref["list"] = controls_list

        return ft.Container(
            width=240, bgcolor="#1a1a1a",
            border=ft.Border.only(right=ft.BorderSide(1, "#2e2e2e")),
            content=ft.Column(controls=[
                ft.Container(
                    content=ft.Row(controls=[
                        ft.Icon(ft.Icons.LANDSCAPE, size=18, color=ACCENT),
                        ft.Text("Environments", size=16, weight=ft.FontWeight.BOLD, color="#ffffff"),
                    ], spacing=8),
                    padding=ft.Padding.only(left=12, right=12, top=16, bottom=10),
                ),
                ft.Container(content=search_field, padding=ft.Padding.symmetric(horizontal=10)),
                ft.Container(height=8),
                controls_ref["list"],
                ft.Divider(height=1, color="#2e2e2e"),
                ft.Container(
                    content=ft.Row(controls=[
                        ft.Icon(ft.Icons.ADD, size=16, color=ACCENT),
                        ft.Text("Manually Add Environment", size=13, color=ACCENT),
                    ], spacing=6, tight=True),
                    on_click=lambda _e: on_add(), ink=True, border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                ),
            ], spacing=0, expand=True),
        )

    def build_center(env) -> ft.Container:
        if env and env.image_path and Path(env.image_path).is_file():
            img_src = get_refreshable_image_src(env.image_path)

            def open_file_location(_e, p=env.image_path):
                import subprocess, os
                subprocess.Popen(f'explorer /select,"{os.path.abspath(p)}"')

            return ft.Container(
                expand=True,
                bgcolor="#1a1a1a",
                content=ft.Stack(
                    controls=[
                        ft.Container(
                            alignment=ft.Alignment.CENTER,
                            expand=True,
                            content=ft.Image(src=img_src, fit=ft.BoxFit.CONTAIN, expand=True),
                        ),
                        ft.Container(
                            content=ft.IconButton(
                                icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                                icon_color="#aaaaaa",
                                icon_size=18,
                                tooltip="Open file location",
                                on_click=open_file_location,
                                bgcolor="#1a1a1acc",
                                width=36, height=36,
                            ),
                            alignment=ft.Alignment(1.0, -1.0),
                            padding=ft.Padding.all(8),
                        ),
                    ],
                    expand=True,
                ),
            )
        return ft.Container(
            expand=True, bgcolor="#1e1e1e",
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.LANDSCAPE, size=80, color="#ffffff15"),
                    ft.Text("No image generated yet", size=13, color="#555555"),
                    ft.Text("Click 'GENERATE NEW' to create a landscape", size=11, color="#444444"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER, spacing=8,
            ),
        )

    def build_right(env) -> ft.Column:
        if not env:
            return ft.Column(controls=[ft.Text("No environment selected", color="#666")])

        desc_field = ft.TextField(
            value=env.merged_description or "",
            multiline=True, min_lines=5, max_lines=8,
            text_size=12, color="#bbbbbb", bgcolor="#242424",
            border_color="#333333", focused_border_color=ACCENT,
            border_radius=6,
            content_padding=ft.Padding.all(10),
        )

        def on_desc_blur(_e):
            env.merged_description = desc_field.value
            _save()

        desc_field.on_blur = on_desc_blur

        def on_remerge(_e):
            if not env.descriptions_by_chapter:
                return
            try:
                from services.ai_text_service import merge_descriptions
                page.snack_bar.content = ft.Text(f"Merging descriptions for {env.name}...")
                page.snack_bar.open = True
                page.update()
                merged = merge_descriptions(env.descriptions_by_chapter)
                env.merged_description = merged
                _save()
                rebuild()
            except Exception as exc:
                page.snack_bar.content = ft.Text(f"Merge failed: {exc}")
                page.snack_bar.open = True
                page.update()

        remerge_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=16, icon_color="#888888",
            tooltip="Regenerate merged description from chapter descriptions",
            on_click=on_remerge,
            width=28, height=28,
        ) if env.descriptions_by_chapter else ft.Container()

        chapter_desc_controls = []
        if env.descriptions_by_chapter:
            for i, cd in enumerate(env.descriptions_by_chapter):
                def make_blur_handler(idx):
                    def on_chapter_desc_blur(_e):
                        env.descriptions_by_chapter[idx] = _e.control.value
                        _save()
                    return on_chapter_desc_blur

                chapter_desc_controls.append(
                    ft.TextField(
                        value=cd,
                        multiline=True, min_lines=2, max_lines=6,
                        text_size=11, color="#999999", bgcolor="#2a2a2a",
                        border_color="#333333", focused_border_color=ACCENT,
                        border_radius=4,
                        content_padding=ft.Padding.all(8),
                        on_blur=make_blur_handler(i),
                    )
                )

        chapter_panel = ft.ExpansionPanelList(
            controls=[
                ft.ExpansionPanel(
                    header=ft.ListTile(
                        title=ft.Text("DESCRIPTIONS BY CHAPTER", size=11, color="#666666", weight=ft.FontWeight.W_600),
                        dense=True,
                        content_padding=ft.Padding.symmetric(horizontal=0),
                    ),
                    content=ft.Container(
                        content=ft.Column(controls=chapter_desc_controls, spacing=2),
                        padding=ft.Padding.only(left=4, right=4, bottom=8),
                    ),
                    bgcolor="#1e1e1e",
                    expanded=False,
                    can_tap_header=True,
                ),
            ],
            elevation=0,
            expand_icon_color="#666666",
        ) if env.descriptions_by_chapter else ft.Container()

        seed_field = ft.TextField(
            value=str(env.seed) if env.seed is not None else "",
            hint_text="Random",
            hint_style=ft.TextStyle(color="#555555", size=11),
            width=120, height=32, text_size=11, color="#bbbbbb",
            bgcolor="#242424", border_color="#333333", focused_border_color=ACCENT,
            border_radius=4,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        )

        def on_seed_submit(_e):
            try:
                new_seed = int(seed_field.value)
                if new_seed != env.seed:
                    env.seed = new_seed
                    _save()
            except (ValueError, TypeError):
                if env.seed is not None:
                    env.seed = None
                    _save()
            seed_field.value = str(env.seed) if env.seed is not None else ""
            seed_field.update()

        seed_field.on_blur = on_seed_submit
        seed_field.on_submit = on_seed_submit

        def toggle_seed_lock(_e):
            env.seed_locked = not getattr(env, "seed_locked", False)
            _save()
            rebuild()

        def confirm_delete(_e):
            def close_dlg(_e):
                confirm_dlg.open = False
                page.update()

            def delete_confirmed(_e):
                confirm_dlg.open = False
                page.update()
                if env in project.environments:
                    project.environments.remove(env)
                    _save()
                    new_sel = project.environments[0].id if project.environments else None
                    on_select(new_sel)

            confirm_dlg = ft.AlertDialog(
                title=ft.Text(f"Delete Environment?"),
                content=ft.Text(f"Are you sure you want to delete '{env.name}'?"),
                actions=[
                    ft.TextButton("Cancel", on_click=close_dlg, style=ft.ButtonStyle(color="#888888")),
                    ft.TextButton("Delete", on_click=delete_confirmed, style=ft.ButtonStyle(color=ft.Colors.RED)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                bgcolor="#1a1a1a",
                shape=ft.RoundedRectangleBorder(radius=12),
            )

            page.overlay.append(confirm_dlg)
            confirm_dlg.open = True
            page.update()

        delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.RED_400,
            tooltip="Delete Environment",
            on_click=confirm_delete
        )

        def rollback_history(index: int):
            if not env or not env.image_path:
                return
            img_history = getattr(env, 'image_path_history', [])
            ref_history = getattr(env, 'refinement_history', [])
            try:
                if index + 1 < len(img_history):
                    target_path = img_history[index + 1]
                elif index == len(ref_history) - 1:
                    target_path = env.image_path
                    return
                else:
                    return
                if target_path and Path(target_path).is_file():
                    env.image_path = target_path
                    _save()
                    rebuild()
            except Exception as exc:
                _show_error(f"Rollback failed: {exc}")

        def delete_history_entry(index: int):
            if not env:
                return
            ref_history = getattr(env, 'refinement_history', [])
            img_history = getattr(env, 'image_path_history', [])
            if index < 0 or index >= len(ref_history):
                return
            ref_history.pop(index)
            if index < len(img_history):
                img_history.pop(index)
            _save()
            rebuild()

        history_items = []
        if hasattr(env, 'refinement_history') and env.refinement_history:
            history_items.append(ft.Container(height=4))
            history_items.append(ft.Text("REFINEMENT HISTORY", size=11, color="#666666", weight=ft.FontWeight.W_600))
            for idx, text in enumerate(env.refinement_history):
                img_history = getattr(env, 'image_path_history', [])
                if idx + 1 < len(img_history):
                    thumb_path = img_history[idx + 1]
                elif idx == len(env.refinement_history) - 1:
                    thumb_path = env.image_path
                else:
                    thumb_path = None
                has_thumb = Path(thumb_path).is_file() if thumb_path else False

                if has_thumb:
                     icon_content = ft.Image(
                         src=get_refreshable_image_src(thumb_path),
                         fit=ft.BoxFit.CONTAIN,
                         expand=True,
                         border_radius=12
                     )
                     icon = ft.Container(
                         content=icon_content,
                         width=24, height=24, border_radius=12,
                         clip_behavior=ft.ClipBehavior.HARD_EDGE
                     )
                else:
                     icon = ft.Container(
                         content=ft.Icon(ft.Icons.IMAGE, size=12, color="#888888"),
                         width=24, height=24, border_radius=12,
                         bgcolor="#333333", alignment=ft.Alignment.CENTER
                     )

                history_items.append(
                    ft.Container(
                        content=ft.Row([
                            icon,
                            ft.Container(width=4) if not has_thumb else ft.Container(width=0),
                            ft.Text(text, size=12, color="#aaaaaa", expand=True, no_wrap=False),
                            ft.IconButton(
                                icon=ft.Icons.RESTORE,
                                icon_size=14,
                                icon_color="#aaaaaa",
                                tooltip="Rollback to this point",
                                on_click=lambda e, i=idx: rollback_history(i),
                                padding=0,
                                width=24, height=24,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=14,
                                icon_color="#ff6666",
                                tooltip="Delete this entry",
                                on_click=lambda e, i=idx: delete_history_entry(i),
                                padding=0,
                                width=24, height=24,
                            )
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.Padding.symmetric(vertical=4, horizontal=0)
                    )
                )

        aspect_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option("16:9", "16:9 (Landscape)"),
                ft.dropdown.Option("9:16", "9:16 (Portrait)"),
            ],
            value=getattr(env, 'aspect_ratio', "16:9"),
            text_size=11, color="#bbbbbb",
            bgcolor="#242424", border_color="#333333", focused_border_color=ACCENT,
            border_radius=4, dense=True,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

        def on_aspect_select(e):
            new_val = e.control.value
            if new_val:
                env.aspect_ratio = new_val
                _save()

        aspect_dropdown.on_select = on_aspect_select

        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(controls=[
                                ft.Row(controls=[
                                    ft.Icon(ft.Icons.AUTO_AWESOME, size=14, color=ACCENT),
                                    ft.Text("ENVIRONMENT INSIGHT", size=11, color=ACCENT, weight=ft.FontWeight.W_700),
                                ], spacing=6),
                                delete_btn
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Text(env.name, size=22, weight=ft.FontWeight.BOLD, color="#ffffff"),
                            ft.Container(height=16),
                            ft.Row(controls=[
                                ft.Container(width=85, height=40, alignment=ft.Alignment(-1, 0), content=ft.Text("ASPECT RATIO:", size=11, color="#666666", weight=ft.FontWeight.W_600)),
                                ft.Container(
                                    width=185, height=40,
                                    content=aspect_dropdown
                                ),
                            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                            ft.Container(height=16),
                            ft.Container(
                                content=ft.Column(controls=[
                                    ft.Row(controls=[
                                        ft.Icon(ft.Icons.MENU_BOOK_OUTLINED, size=14, color=ACCENT),
                                        ft.Text("DESCRIPTION", size=11, color="#888888", weight=ft.FontWeight.W_600),
                                        ft.Row(expand=True),
                                        remerge_btn,
                                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                    desc_field,
                                    chapter_panel,
                                ], spacing=8),
                                bgcolor="#1e1e1e", border_radius=8, padding=ft.Padding.all(14), border=ft.Border.all(1, "#2e2e2e"),
                            ),
                            ft.Container(height=8),
                            ft.Row(controls=[
                                ft.Text("SEED:", size=11, color="#666666", weight=ft.FontWeight.W_600),
                                seed_field,
                                ft.IconButton(
                                    icon=ft.Icons.LOCK if getattr(env, "seed_locked", False) else ft.Icons.LOCK_OPEN,
                                    icon_size=16,
                                    icon_color=ACCENT if getattr(env, "seed_locked", False) else "#888888",
                                    on_click=toggle_seed_lock,
                                    tooltip="Seed locked (same seed each generation)" if getattr(env, "seed_locked", False) else "Seed unlocked (new random seed each generation)",
                                    width=32, height=32,
                                ),
                                ft.Container(width=4),
                                ft.IconButton(
                                    icon=ft.Icons.UNDO, icon_size=16, icon_color="#aaaaaa",
                                    on_click=on_undo, tooltip="Undo last generation",
                                    width=32, height=32,
                                    visible=bool(getattr(env, 'image_path_history', None)) if env else False
                                ),
                                ft.Row(expand=True),
                            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Divider(height=1, color="#2e2e2e"),
                            ft.Container(height=6),
                            ft.Row(controls=[
                                ft.Container(
                                    content=ft.Row(controls=[ft.Icon(ft.Icons.BOLT, size=16, color="#aaaaaa"), ft.Text("GENERATE NEW", size=12, color="#aaaaaa", weight=ft.FontWeight.W_600)], spacing=6, tight=True),
                                    bgcolor="#1e1e1e", border_radius=8, border=ft.Border.all(1, "#333333"),
                                    height=40, on_click=on_generate, ink=True, expand=True,
                                    padding=ft.Padding.symmetric(horizontal=12), alignment=ft.Alignment.CENTER,
                                ),
                            ], spacing=8),
                            *history_items,
                        ], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True,
                    ),
                    padding=ft.Padding.all(16), expand=True,
                ),
                ft.Container(
                    content=ft.Column(controls=[
                        ft.Text("REFINE CURRENT:", size=11, color="#aaaaaa", weight=ft.FontWeight.W_700),
                        build_chat_input(
                            hint="Add fog, change lighting...",
                            on_submit=on_chat_submit,
                            on_cancel=cancel_refinement,
                            is_generating=(env.id in generating_ids if hasattr(env, 'id') else False),
                            generating_message=gen_status.get(env.id, f"Generating image of {env.name}...") if hasattr(env, 'id') else "Generating image..."
                        ),
                    ], spacing=6),
                    padding=ft.Padding.only(left=12, right=12, bottom=12),
                    bgcolor="#1a1a1a",
                ),
            ],
            spacing=0, expand=True,
        )

    def build_view_content() -> ft.Row:
        env = get_env(selected_ref["value"])
        return ft.Row(
            controls=[
                build_sidebar(),
                build_center(env),
                ft.Container(
                    content=build_right(env),
                    width=340, bgcolor="#1a1a1a",
                    border=ft.Border.only(left=ft.BorderSide(1, "#2e2e2e")),
                ),
            ],
            spacing=0, expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    from components.top_nav import build_top_nav

    nav = build_top_nav("Environments", on_tab_change, on_home=on_home, on_save=on_save, on_save_as=on_save_as, project_store=project_store)

    wrapper = ft.Container(content=build_view_content(), expand=True)
    wrapper_ref["container"] = wrapper

    def rebuild():
        try:
            if wrapper_ref["container"] and getattr(wrapper_ref["container"], "page", None):
                new_content = build_view_content()
                wrapper_ref["container"].content = new_content
                wrapper_ref["container"].update()
                page.update()
        except Exception:
            pass

    return ft.Column(
        controls=[nav, wrapper, build_footer_bar()],
        spacing=0, expand=True,
    )
