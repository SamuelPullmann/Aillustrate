import flet as ft
import random
from pathlib import Path
import json

from components.chat_input import build_chat_input
from components.image_source import get_refreshable_image_src
from components.footer_bar import build_footer_bar
from state.store import ProjectStore
from services.ai_image_service import generate_scene_image, edit_image, undo_image_edit
from services.project_service import save_project
from models.scene import Scene

ACCENT = "#7c3aed"

_AVATAR_COLORS = ["#7c3aed", "#0e7490", "#16a34a", "#0369a1", "#b45309", "#dc2626", "#4338ca", "#0f766e"]


def _color_for_index(i: int) -> str:
    return _AVATAR_COLORS[i % len(_AVATAR_COLORS)]


def _initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()


def build_scenes_view(page: ft.Page, on_tab_change, project_store: ProjectStore = None, ui_store=None, on_home=None, on_save=None, on_save_as=None) -> ft.Column:
    project = project_store.current_project if project_store else None
    characters = project.characters if project else []
    environments = project.environments if project else []

    all_scenes = []
    if project:
        for ch in project.chapters:
            for sc in ch.scenes:
                all_scenes.append(sc)

    _initial_sel = None
    if ui_store and getattr(ui_store, 'selected_scene_id', None):
        if any(sc.id == ui_store.selected_scene_id for sc in all_scenes):
            _initial_sel = ui_store.selected_scene_id
    if _initial_sel is None:
        _initial_sel = all_scenes[0].id if all_scenes else None
    selected_ref = {"value": _initial_sel}
    wrapper_ref = {"container": None}

    if not hasattr(page, "generating_ids"):
        page.generating_ids = set()
    generating_ids = page.generating_ids

    if not hasattr(page, "gen_status"):
        page.gen_status = {}
    gen_status = page.gen_status

    composition_state = {"char_value": None}
    local_env_map = {}
    env_map = None
    if ui_store is not None:
        if not hasattr(ui_store, 'scene_env_snapshot'):
            ui_store.scene_env_snapshot = {}
        composition_env_snapshot = ui_store.scene_env_snapshot
    else:
        composition_env_snapshot = {}

    def _snapshot_path():
        try:
            if project_store and getattr(project_store, 'project_dir', None):
                return Path(project_store.project_dir) / ".scene_env_snapshot.json"
        except Exception:
            pass
        return None

    def save_snapshot_to_disk():
        p = _snapshot_path()
        if not p:
            return
        try:
            p.write_text(json.dumps(composition_env_snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass

    def load_snapshot_from_disk():
        p = _snapshot_path()
        if not p:
            return
        try:
            if p.is_file():
                data = json.loads(p.read_text(encoding='utf-8'))
                if isinstance(data, dict):
                    for k, v in data.items():
                        composition_env_snapshot.setdefault(k, v)
                        env_map.setdefault(k, v)
        except Exception:
            pass

    env_map = None
    if ui_store is not None:
        if not hasattr(ui_store, 'scene_env_map'):
            ui_store.scene_env_map = {}
        env_map = ui_store.scene_env_map
    else:
        env_map = local_env_map

    load_snapshot_from_disk()

    for sc in all_scenes:
        env_map.setdefault(sc.id, sc.environment_id if sc.environment_id else "__none__")
        composition_env_snapshot.setdefault(sc.id, env_map.get(sc.id))
    error_ref = {"value": ""}

    def _is_attached(ctrl):
        try:
            return bool(ctrl and ctrl.page)
        except RuntimeError:
            return False
        except Exception:
            return False

    def _show_error(message: str):
        error_ref["value"] = message
        try:
            page.snack_bar.content = ft.Text(message)
            page.snack_bar.open = True
            page.update()
        except Exception:
            pass

    def get_scene(sid):
        if project:
            for ch in project.chapters:
                for sc in ch.scenes:
                    if sc.id == sid:
                        return sc
        return None

    def _char_by_id(cid):
        for c in characters:
            if c.id == cid:
                return c
        return None

    def _env_by_id(eid):
        for e in environments:
            if e.id == eid:
                return e
        return None

    def _comp_env(sid):
        sc = get_scene(sid)
        if sc and sc.environment_id:
            return sc.environment_id
        return "__none__"

    def on_select(sid):
        selected_ref["value"] = sid
        if ui_store:
            ui_store.selected_scene_id = sid
        scene = get_scene(sid)
        if scene:
            env_map.setdefault(sid, scene.environment_id if scene.environment_id else "__none__")
            composition_env_snapshot[sid] = env_map.get(sid)
            save_snapshot_to_disk()
        composition_state["char_value"] = None
        rebuild()

    def on_add():
        try:
            if not project or not project.chapters:
                _show_error("No chapters available to add a scene to.")
                return

            def close_dlg(_e):
                dlg.open = False
                page.update()

            def save_new(_e):
                try:
                    if not title_field.value:
                        title_field.error_text = "Title is required"
                        title_field.update()
                        return

                    sel_chapter_id = chapter_dropdown.value

                    target_chapter = next((c for c in project.chapters if str(c.order_index) == sel_chapter_id), project.chapters[0])

                    new_scene = Scene(
                        title=title_field.value,
                        description=desc_field.value
                    )
                    target_chapter.scenes.append(new_scene)
                    all_scenes.append(new_scene)

                    save_project(project, project_store.project_dir)

                    dlg.open = False
                    page.update()

                    on_select(new_scene.id)
                    rebuild()

                    page.snack_bar = ft.SnackBar(ft.Text(f"Added scene: {new_scene.title}"))
                    page.snack_bar.open = True
                    page.update()

                except Exception as e:
                    dlg.open = False
                    page.update()
                    _show_error(f"Failed to add scene: {e}")


            title_field = ft.TextField(
                label="Title",
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

            chapter_opts = [
                ft.dropdown.Option(str(c.order_index), f"Chapter {c.order_index}")
                for c in project.chapters
            ]

            chapter_dropdown = ft.Dropdown(
                options=chapter_opts,
                value=str(project.chapters[0].order_index) if project.chapters else None,
                text_size=12, color="#ffffff", bgcolor="#242424",
                border_color="#333333", focused_border_color=ACCENT,
                border_radius=6, height=42,
                content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            )

            dlg = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.MOVIE_CREATION_ROUNDED, color=ACCENT, size=28),
                    ft.Text("Create Scene", size=22, weight=ft.FontWeight.W_600, color="#ffffff")
                ], spacing=12, alignment=ft.MainAxisAlignment.START),
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("Add a new scene to a specific chapter.", size=14, color="#AAAAAA"),
                        ft.Container(height=10),
                        title_field,
                        ft.Container(height=5),
                        chapter_dropdown,
                        ft.Container(height=5),
                        desc_field
                    ], tight=True, spacing=5, width=500, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                    padding=ft.Padding.symmetric(vertical=10, horizontal=5),
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=close_dlg, style=ft.ButtonStyle(color="#888888")),
                    ft.Container(width=5),
                    ft.ElevatedButton(
                        "Create Scene",
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


    def _save():
        if project_store and project_store.project_dir:
            save_project(project, project_store.project_dir)

    if not hasattr(page, "cancel_events"):
        page.cancel_events = {}

    def on_generate(_e):
        import threading as _threading
        scene = get_scene(selected_ref["value"])
        if not scene or not project_store or not project_store.project_dir:
            return

        old_ev = page.cancel_events.get(scene.id)
        if old_ev:
            old_ev.set()

        if not getattr(scene, "seed_locked", False):
            scene.seed = random.randint(0, 2147483647)
            _save()

        scene_chars = [c for c in characters if c.id in scene.character_ids][:5]
        scene_env = _env_by_id(scene.environment_id)

        error_ref["value"] = ""
        cancel_event = _threading.Event()
        page.cancel_events[scene.id] = cancel_event
        generating_ids.add(scene.id)
        gen_status.pop(scene.id, None)
        rebuild()

        def on_gen_status(msg: str, sid=scene.id, ev=cancel_event):
            if ev.is_set():
                return
            gen_status[sid] = msg
            if _is_attached(wrapper_ref.get("container")):
                rebuild()

        def work(ev=cancel_event):
            try:
                generate_scene_image(
                    scene, scene_chars, scene_env,
                    project.art_style, project_store.project_dir,
                    all_characters=characters,
                    on_status=on_gen_status,
                    cancel_event=ev,
                )
                if not ev.is_set():
                    scene.refinement_history.clear()
                    save_project(project, project_store.project_dir)
            except InterruptedError:
                pass
            except Exception as exc:
                if not ev.is_set() and _is_attached(wrapper_ref.get("container")):
                    _show_error(f"Scene image generation failed: {exc}")

            if page.cancel_events.get(scene.id) is ev:
                page.cancel_events.pop(scene.id, None)
                generating_ids.discard(scene.id)
                gen_status.pop(scene.id, None)
                if _is_attached(wrapper_ref.get("container")):
                    rebuild()

        page.run_thread(work)

    def on_undo(_e):
        scene = get_scene(selected_ref["value"])
        if not scene or not getattr(scene, "image_path_history", []) or scene.id in generating_ids:
            return
        scene.image_path = scene.image_path_history.pop()
        _save()
        rebuild()

    global_cancel_ref = {"cancelled": False}

    def on_chat_submit(text: str):
        scene = get_scene(selected_ref["value"])
        if not scene or not scene.image_path or not Path(scene.image_path).is_file() or scene.id in generating_ids:
            return
        error_ref["value"] = ""
        generating_ids.add(scene.id)
        global_cancel_ref["cancelled"] = False
        rebuild()

        def work():
            try:
                old_path = scene.image_path
                new_path = edit_image(scene.image_path, text)
                if not global_cancel_ref["cancelled"]:
                    if not hasattr(scene, 'image_path_history'):
                        scene.image_path_history = []
                    scene.image_path_history.append(old_path)
                    scene.image_path = new_path
                    if not hasattr(scene, 'refinement_history'):
                        scene.refinement_history = []
                    scene.refinement_history.append(text)
                    save_project(project, project_store.project_dir)
                else:
                    try:
                        Path(new_path).unlink(missing_ok=True)
                    except Exception:
                        pass
            except Exception as exc:
                if not global_cancel_ref["cancelled"] and _is_attached(wrapper_ref.get("container")):
                    _show_error(f"Scene image edit failed: {exc}")

            generating_ids.discard(scene.id)
            if _is_attached(wrapper_ref.get("container")):
                rebuild()

        page.run_thread(work)

    def cancel_refinement():
        global_cancel_ref["cancelled"] = True
        scene = get_scene(selected_ref["value"])
        if scene:
            ev = page.cancel_events.get(scene.id)
            if ev:
                ev.set()
            gen_status.pop(scene.id, None)
            generating_ids.discard(scene.id)
        rebuild()

    def _sidebar_items():
        items = []
        for i, sc in enumerate(all_scenes):
            items.append({
                "id": sc.id,
                "name": sc.title,
                "subtitle": sc.description[:40] + "..." if len(sc.description) > 40 else sc.description,
                "initials": _initials(sc.title),
                "color": _color_for_index(i),
            })
        return items

    def build_sidebar() -> ft.Container:
        items = _sidebar_items()

        search_val = {"text": ""}

        def on_search_change(e):
            search_val["text"] = e.control.value.lower()
            filtered = [i for i in items if search_val["text"] in i["name"].lower()]
            controls_list.controls = [item_row(i) for i in filtered]
            try:
                controls_list.update()
            except Exception:
                pass

        search_field = ft.TextField(
            hint_text="Search scenes...",
            hint_style=ft.TextStyle(color="#666666", size=13),
            prefix_icon=ft.Icons.SEARCH,
            border_radius=8, border_color="#333333", focused_border_color=ACCENT,
            bgcolor="#242424", color="#ffffff", height=42, text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            on_change=on_search_change,
        )

        def item_row(item):
            is_sel = item["id"] == selected_ref["value"]

            def clicked(_e, sid=item["id"]):
                on_select(sid)

            scene_obj = get_scene(item["id"])
            has_image = scene_obj and scene_obj.image_path and Path(scene_obj.image_path).is_file()

            avatar_content = ft.Text(item["initials"], size=11, weight=ft.FontWeight.BOLD, color="#ffffff")
            if has_image:
                 avatar_content = ft.Image(
                     src=get_refreshable_image_src(scene_obj.image_path),
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
                        ft.Text(item["subtitle"], size=11, color="#888888", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=1, expand=True),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color=ACCENT if is_sel else "#555555"),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                on_click=clicked, padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=8, bgcolor=ACCENT + "22" if is_sel else "transparent", ink=True,
            )

        controls_list = ft.Column(controls=[item_row(i) for i in items], spacing=2, scroll=ft.ScrollMode.AUTO, expand=True)

        return ft.Container(
            width=240, bgcolor="#1a1a1a",
            border=ft.Border.only(right=ft.BorderSide(1, "#2e2e2e")),
            content=ft.Column(controls=[
                ft.Container(
                    content=ft.Row(controls=[
                        ft.Icon(ft.Icons.MOVIE_FILTER, size=18, color=ACCENT),
                        ft.Text("Scenes", size=16, weight=ft.FontWeight.BOLD, color="#ffffff"),
                    ], spacing=8),
                    padding=ft.Padding.only(left=12, right=12, top=16, bottom=10),
                ),
                ft.Container(content=search_field, padding=ft.Padding.symmetric(horizontal=10)),
                ft.Container(height=8),
                controls_list,
                ft.Divider(height=1, color="#2e2e2e"),
                ft.Container(
                    content=ft.Row(controls=[
                        ft.Icon(ft.Icons.ADD, size=16, color=ACCENT),
                        ft.Text("Manually Add Scene", size=13, color=ACCENT),
                    ], spacing=6, tight=True),
                    on_click=lambda _e: on_add(), ink=True, border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                ),
            ], spacing=0, expand=True),
        )

    def build_center(scene) -> ft.Container:
        if scene and scene.image_path and Path(scene.image_path).is_file():
            scene_chars = [_char_by_id(cid) for cid in scene.character_ids]
            char_chips = [
                ft.Container(
                    content=ft.Text(c.name, size=10, color="#ffffff", weight=ft.FontWeight.W_500),
                    bgcolor="#00000066", border=ft.Border.all(1, "#ffffff33"),
                    border_radius=4, padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                )
                for c in scene_chars if c
            ]
            scene_img_src = get_refreshable_image_src(scene.image_path)

            def open_file_location(_e, p=scene.image_path):
                import subprocess, os
                subprocess.Popen(f'explorer /select,"{os.path.abspath(p)}"')

            return ft.Container(
                expand=True,
                bgcolor="#1a1a1a",
                alignment=ft.Alignment.CENTER,
                content=ft.Stack(
                    controls=[
                        ft.Container(
                            alignment=ft.Alignment.CENTER,
                            expand=True,
                            content=ft.Image(src=scene_img_src, fit=ft.BoxFit.CONTAIN, expand=True),
                        ),
                        ft.Container(
                            content=ft.Row(controls=char_chips, spacing=6, wrap=True),
                            alignment=ft.Alignment.TOP_LEFT,
                            padding=ft.Padding.all(14),
                        ) if char_chips else ft.Container(),
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
                    ft.Icon(ft.Icons.MOVIE_CREATION_OUTLINED, size=80, color="#ffffff15"),
                    ft.Text("No image generated yet", size=13, color="#555555"),
                    ft.Text("Click 'GENERATE NEW' to create an illustration", size=11, color="#444444"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER, spacing=8,
            ),
        )

    def build_composition_section(scene) -> ft.Container:
        if not scene:
            return ft.Container()

        env_opts = [ft.dropdown.Option(key="none", text="— No environment —")]
        for e in environments:
            env_opts.append(ft.dropdown.Option(key=e.id, text=e.name))

        vybrane_prostredie = "none"
        if scene.environment_id and any(e.id == scene.environment_id for e in environments):
            vybrane_prostredie = scene.environment_id
        else:
            scene.environment_id = None

        def on_env_change(e):
            nova_hodnota = e.control.value
            scene.environment_id = None if nova_hodnota == "none" else nova_hodnota
            if project_store and project_store.project_dir:
                save_project(project, project_store.project_dir)
            rebuild()

        env_dropdown = ft.Dropdown(
            options=env_opts,
            value=vybrane_prostredie,
            on_select=on_env_change,
            text_size=12, color="#ffffff", bgcolor="#242424",
            border_color="#333333", focused_border_color=ACCENT,
            border_radius=6, height=42,
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        )

        current_env = _env_by_id(scene.environment_id)

        env_thumb = ft.Container(width=0, height=0)
        if current_env and getattr(current_env, 'image_path', None) and Path(current_env.image_path).is_file():
            env_src = get_refreshable_image_src(current_env.image_path)
            env_thumb = ft.Container(
                content=ft.Image(src=env_src, fit=ft.BoxFit.COVER, width=36, height=36),
                width=36, height=36, border_radius=6,
                border=ft.Border.all(2, ACCENT),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )

        scene_chars = [_char_by_id(cid) for cid in scene.character_ids]

        def remove_char(cid):
            if cid in scene.character_ids:
                scene.character_ids.remove(cid)
                _save()
                rebuild()

        char_chips = []
        for c in scene_chars:
            if not c:
                continue
            try:
                c_index = characters.index(c)
                c_color = _color_for_index(c_index)
            except ValueError:
                c_color = ACCENT

            if getattr(c, 'image_path', None) and Path(c.image_path).is_file():
                c_src = get_refreshable_image_src(c.image_path)
                avatar = ft.Container(
                    content=ft.Image(src=c_src, fit=ft.BoxFit.COVER, width=28, height=28),
                    width=28, height=28, border_radius=14,
                    border=ft.Border.all(2, c_color),
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                )
            else:
                avatar = ft.Container(
                    content=ft.Text(_initials(c.name), size=9, weight=ft.FontWeight.BOLD, color="#ffffff"),
                    bgcolor=c_color, border_radius=14, width=28, height=28,
                    alignment=ft.Alignment.CENTER,
                )

            chip = ft.Container(
                content=ft.Row(controls=[
                    avatar,
                    ft.Text(c.name, size=10, color="#ffffff"),
                    ft.Container(
                        content=ft.Icon(ft.Icons.CLOSE, size=12, color="#888888"),
                        on_click=lambda _e, cid=c.id: remove_char(cid),
                        ink=True, border_radius=10, width=20, height=20,
                        alignment=ft.Alignment.CENTER,
                    ),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=ACCENT + "22", border_radius=14,
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border=ft.Border.all(1, ACCENT + "55"),
            )
            char_chips.append(chip)

        available_chars = [c for c in characters if c.id not in scene.character_ids]
        current_char_value = composition_state.get("char_value")
        if current_char_value not in {c.id for c in available_chars}:
            current_char_value = None
            composition_state["char_value"] = None

        add_char_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(key=c.id, text=c.name) for c in available_chars],
            value=current_char_value,
            hint_text="Add character...",
            hint_style=ft.TextStyle(color="#666666", size=11),
            text_size=11, color="#ffffff", bgcolor="#242424",
            border_color="#333333", focused_border_color=ACCENT,
            border_radius=6, height=36, expand=True,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        ) if available_chars else ft.Text("All characters assigned", size=11, color="#555555", italic=True)

        if isinstance(add_char_dropdown, ft.Dropdown):
            def on_add_char_select(_e):
                composition_state["char_value"] = add_char_dropdown.value
            add_char_dropdown.on_select = on_add_char_select

        def on_add_char(_e):
            if isinstance(add_char_dropdown, ft.Dropdown) and add_char_dropdown.value:
                if len(scene.character_ids) < 5:
                    scene.character_ids.append(add_char_dropdown.value)
                    composition_state["char_value"] = None
                    _save()
                    rebuild()

        add_btn = ft.Container(
            content=ft.Icon(ft.Icons.ADD, size=16, color=ACCENT),
            on_click=on_add_char, ink=True, border_radius=18,
            width=32, height=32, alignment=ft.Alignment.CENTER,
            border=ft.Border.all(1, "#444444"),
        ) if available_chars else ft.Container()

        return ft.Container(
            content=ft.Column(controls=[
                ft.Row(controls=[
                    ft.Icon(ft.Icons.LAYERS, size=14, color=ACCENT),
                    ft.Text("SCENE COMPOSITION", size=11, color=ACCENT, weight=ft.FontWeight.W_700),
                ], spacing=6),
                ft.Container(height=6),
                ft.Text("ENVIRONMENT", size=10, color="#666666", weight=ft.FontWeight.W_600),
                ft.Container(height=4),
                ft.Row(controls=[
                    env_thumb,
                    ft.Container(content=env_dropdown, expand=True),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=10),
                ft.Row(controls=[
                    ft.Text("CHARACTERS", size=10, color="#666666", weight=ft.FontWeight.W_600),
                    ft.Text(f"({len(scene.character_ids)}/5)", size=10, color="#555555"),
                ], spacing=4),
                ft.Container(height=4),
                ft.Row(controls=char_chips, wrap=True, spacing=6, run_spacing=6),
                ft.Container(height=4),
                ft.Row(controls=[
                    add_char_dropdown if isinstance(add_char_dropdown, ft.Control) else ft.Container(content=add_char_dropdown),
                    add_btn,
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER) if available_chars else ft.Container(),
            ], spacing=0),
            bgcolor="#1e1e1e", border_radius=8,
            padding=ft.Padding.all(12),
            border=ft.Border.all(1, "#2e2e2e"),
        )

    def build_right(scene) -> ft.Column:
        if not scene:
            return ft.Column(controls=[ft.Text("No scene selected", color="#666")])

        desc_field = ft.TextField(
            value=scene.description or "",
            multiline=True, min_lines=5, max_lines=8,
            text_size=12, color="#bbbbbb", bgcolor="#242424",
            border_color="#333333", focused_border_color=ACCENT,
            border_radius=6,
            content_padding=ft.Padding.all(10),
        )

        def on_desc_blur(_e):
            scene.description = desc_field.value
            _save()

        desc_field.on_blur = on_desc_blur

        seed_field = ft.TextField(
            value=str(scene.seed) if scene.seed is not None else "",
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
                if new_seed != scene.seed:
                    scene.seed = new_seed
                    _save()
            except (ValueError, TypeError):
                if scene.seed is not None:
                    scene.seed = None
                    _save()
            seed_field.value = str(scene.seed) if scene.seed is not None else ""
            seed_field.update()

        seed_field.on_blur = on_seed_submit
        seed_field.on_submit = on_seed_submit

        def toggle_seed_lock(_e):
            scene.seed_locked = not getattr(scene, "seed_locked", False)
            _save()
            rebuild()

        def confirm_delete(_e):
            def close_dlg(_e):
                confirm_dlg.open = False
                page.update()

            def delete_confirmed(_e):
                confirm_dlg.open = False
                page.update()

                found_chapter = None
                if project:
                    for ch in project.chapters:
                        if scene in ch.scenes:
                            ch.scenes.remove(scene)
                            found_chapter = ch
                            break

                if found_chapter:
                    _save()
                    project_scenes = []
                    for ch in project.chapters:
                        project_scenes.extend(ch.scenes)

                    new_sel = project_scenes[0].id if project_scenes else None
                    on_select(new_sel)

            confirm_dlg = ft.AlertDialog(
                title=ft.Text(f"Delete Scene?"),
                content=ft.Text(f"Are you sure you want to delete '{scene.title}'?"),
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
            tooltip="Delete Scene",
            on_click=confirm_delete
        )

        def rollback_history(index: int):
            if not scene or not scene.image_path:
                return
            img_history = getattr(scene, 'image_path_history', [])
            ref_history = getattr(scene, 'refinement_history', [])
            try:
                if index + 1 < len(img_history):
                    target_path = img_history[index + 1]
                elif index == len(ref_history) - 1:
                    target_path = scene.image_path
                    return  # Already at latest
                else:
                    return
                if target_path and Path(target_path).is_file():
                    scene.image_path = target_path
                    _save()
                    rebuild()
            except Exception as exc:
                _show_error(f"Rollback failed: {exc}")

        def delete_history_entry(index: int):
            if not scene:
                return
            ref_history = getattr(scene, 'refinement_history', [])
            img_history = getattr(scene, 'image_path_history', [])
            if index < 0 or index >= len(ref_history):
                return
            ref_history.pop(index)
            if index < len(img_history):
                img_history.pop(index)
            _save()
            rebuild()

        history_items = []
        if hasattr(scene, 'refinement_history') and scene.refinement_history:
            history_items.append(ft.Container(height=4))
            history_items.append(ft.Text("REFINEMENT HISTORY", size=11, color="#666666", weight=ft.FontWeight.W_600))
            for idx, text in enumerate(scene.refinement_history):
                img_history = getattr(scene, 'image_path_history', [])
                if idx + 1 < len(img_history):
                    thumb_path = img_history[idx + 1]
                elif idx == len(scene.refinement_history) - 1:
                    thumb_path = scene.image_path
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
                ft.dropdown.Option("9:16", "9:16 (Portrait)"),
                ft.dropdown.Option("16:9", "16:9 (Landscape)"),
            ],
            value=getattr(scene, 'aspect_ratio', "9:16"),
            text_size=11, color="#bbbbbb",
            bgcolor="#242424", border_color="#333333", focused_border_color=ACCENT,
            border_radius=4, dense=True,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

        def on_aspect_select(e):
            new_val = e.control.value
            if new_val:
                scene.aspect_ratio = new_val
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
                                    ft.Text("SCENE INSIGHT", size=11, color=ACCENT, weight=ft.FontWeight.W_700),
                                ], spacing=6),
                                delete_btn
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Text(scene.title, size=22, weight=ft.FontWeight.BOLD, color="#ffffff"),
                            ft.Container(height=16),
                            ft.Row(controls=[
                                ft.Container(width=85, height=40, alignment=ft.Alignment(-1, 0), content=ft.Text("ASPECT RATIO:", size=11, color="#666666", weight=ft.FontWeight.W_600)),
                                ft.Container(
                                    width=185, height=40,
                                    content=aspect_dropdown
                                ),
                            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                            ft.Container(height=16),
                            build_composition_section(scene),
                            ft.Container(height=8),
                            ft.Container(
                                content=ft.Column(controls=[
                                    ft.Row(controls=[
                                        ft.Icon(ft.Icons.MENU_BOOK_OUTLINED, size=14, color=ACCENT),
                                        ft.Text("SCENE DESCRIPTION", size=11, color="#888888", weight=ft.FontWeight.W_600),
                                    ], spacing=6),
                                    desc_field,
                                ], spacing=8),
                                bgcolor="#1e1e1e", border_radius=8, padding=ft.Padding.all(14), border=ft.Border.all(1, "#2e2e2e"),
                            ),
                            ft.Container(height=8),
                            ft.Row(controls=[
                                ft.Container(width=85, content=ft.Text("SEED:", size=11, color="#666666", weight=ft.FontWeight.W_600)),
                                ft.Container(content=seed_field, width=120),
                                ft.Container(width=4),
                                ft.IconButton(
                                    icon=ft.Icons.LOCK if getattr(scene, "seed_locked", False) else ft.Icons.LOCK_OPEN,
                                    icon_size=16,
                                    icon_color=ACCENT if getattr(scene, "seed_locked", False) else "#888888",
                                    on_click=toggle_seed_lock,
                                    tooltip="Seed locked (same seed each generation)" if getattr(scene, "seed_locked", False) else "Seed unlocked (new random seed each generation)",
                                    width=32, height=32,
                                ),
                            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                            ft.Container(height=24),
                            ft.Divider(height=1, color="#2e2e2e"),
                            ft.Container(height=16),
                            ft.Row(controls=[
                                ft.Container(
                                    content=ft.Row(controls=[ft.Icon(ft.Icons.BOLT, size=16, color="#aaaaaa"), ft.Text("GENERATE NEW", size=12, color="#aaaaaa", weight=ft.FontWeight.W_600)], spacing=6, tight=True, alignment=ft.MainAxisAlignment.CENTER),
                                    bgcolor="#1e1e1e", border_radius=8, border=ft.Border.all(1, "#333333"),
                                    height=40, on_click=on_generate if scene.id not in generating_ids else None, ink=True, expand=True,
                                    padding=ft.Padding.symmetric(horizontal=12), alignment=ft.Alignment.CENTER,
                                    opacity=1.0 if scene.id not in generating_ids else 0.5,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.UNDO, icon_size=16, icon_color="#aaaaaa",
                                    on_click=on_undo, tooltip="Undo last generation",
                                    width=32, height=32,
                                    visible=bool(getattr(scene, 'image_path_history', None)) if scene else False
                                ),
                            ], spacing=8),
                            *history_items,
                            ft.Row(expand=True),
                        ], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True,
                    ),
                    padding=ft.Padding.all(16), expand=True,
                ),
                ft.Container(
                    content=ft.Column(controls=[
                        ft.Text("REFINE CURRENT:", size=11, color="#aaaaaa", weight=ft.FontWeight.W_700),
                        build_chat_input(
                            hint="Add rain effect, zoom out...",
                            on_submit=on_chat_submit,
                            on_cancel=cancel_refinement,
                            is_generating=(scene.id in generating_ids if getattr(scene, 'id', None) else False),
                            generating_message=gen_status.get(scene.id, f"Generating image of {(scene.title or 'Scene').strip() or 'Scene'}...") if scene else "Generating image..."
                        ),
                    ], spacing=6),
                    padding=ft.Padding.only(left=12, right=12, bottom=12),
                    bgcolor="#1a1a1a",
                ),
            ],
            spacing=0, expand=True,
        )

    def build_view_content() -> ft.Row:
        scene = get_scene(selected_ref["value"])
        return ft.Row(
            controls=[
                build_sidebar(),
                build_center(scene),
                ft.Container(
                    content=build_right(scene),
                    width=340, bgcolor="#1a1a1a",
                    border=ft.Border.only(left=ft.BorderSide(1, "#2e2e2e")),
                ),
            ],
            spacing=0, expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    from components.top_nav import build_top_nav

    nav = build_top_nav("Scenes", on_tab_change, on_home=on_home, on_save=on_save, on_save_as=on_save_as, project_store=project_store)

    wrapper = ft.Container(content=build_view_content(), expand=True)
    wrapper_ref["container"] = wrapper

    def rebuild():
        try:
            if _is_attached(wrapper_ref.get("container")):
                wrapper_ref["container"].content = build_view_content()
                wrapper_ref["container"].update()
                page.update()
        except Exception:
            pass

    return ft.Column(
        controls=[nav, wrapper, build_footer_bar()],
        spacing=0, expand=True,
    )
