import flet as ft

ACCENT = "#7c3aed"
TABS = ["Characters", "Environments", "Scenes", "Export"]

_view_models = {t: None for t in TABS}


def get_active_model(view_name: str | None = None) -> str:
    """Return the currently selected image model for the given view tab.

    Falls back to the default model from config if no per-view model is set.
    """
    import config as _config
    if view_name and view_name in _view_models and _view_models[view_name]:
        all_models = getattr(_config, 'IMAGE_MODELS', [])
        if all_models and _view_models[view_name] not in all_models:
            _view_models[view_name] = all_models[0]
        return _view_models[view_name]
    default = getattr(_config, "IMAGE_MODEL", None)
    if not default:
        models = getattr(_config, 'IMAGE_MODELS', [])
        default = models[0] if models else "gemini-2.5-flash-image"
    return default


def build_top_nav(
    active_tab: str,
    on_tab_change,
    on_home=None,
    on_save=None,
    on_save_as=None,
    project_store=None,
) -> ft.Container:
    """Build the top navigation bar with tab buttons, model selector and style selector.

    ``active_tab`` is highlighted and its model/style settings are shown.
    ``on_tab_change(tab_name)`` is called when a tab is clicked.
    """

    def tab_button(label: str) -> ft.Container:
        is_active = label == active_tab

        def clicked(_e, lbl=label):
            on_tab_change(lbl)

        return ft.Container(
            content=ft.Text(
                label,
                color=ACCENT if is_active else "#aaaaaa",
                size=14,
                weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400,
            ),
            on_click=clicked,
            ink=True,
            padding=ft.Padding.symmetric(horizontal=20, vertical=14),
            border=ft.Border.only(
                bottom=ft.BorderSide(2, ACCENT) if is_active else ft.BorderSide(2, "transparent")
            ),
        )

    brand = ft.Row(
        controls=[
            ft.Image(
                src="assets/icon.png",
                width=24,
                height=24,
            ),
            ft.Text(
                "Aillustrate",
                size=13,
                weight=ft.FontWeight.BOLD,
                color="#ffffff",
            ),
        ],
        spacing=6,
    )

    def save_as_clicked(_e):
        def on_ok(e):
            new_name = name_field.value.strip()
            if new_name and on_save_as:
                on_save_as(new_name)
            dialog.open = False

        name_field = ft.TextField(label="New project name", autofocus=True)
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Save Project As..."),
            content=name_field,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: (setattr(dialog, 'open', False), dialog.update())),
                ft.TextButton("OK", on_click=on_ok),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        _e.page.show_dialog(dialog)

    save_as_button = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.SAVE_AS_OUTLINED, size=16, color="#cccccc"),
            ft.Text("Save as", size=13, color="#cccccc"),
        ], spacing=4),
        on_click=save_as_clicked,
        ink=True,
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=6,
    )

    import config

    project_vm = {}
    if project_store and getattr(project_store, 'current_project', None):
        project_vm = getattr(project_store.current_project, 'view_models', {}) or {}
    _default_model = getattr(config, 'IMAGE_MODEL', None) or (config.IMAGE_MODELS[0] if getattr(config, 'IMAGE_MODELS', []) else None)
    current_model = project_vm.get(active_tab) or _view_models.get(active_tab) or _default_model
    if current_model:
        _view_models[active_tab] = current_model

    def _set_model(m, e=None):
        _view_models[active_tab] = m
        if project_store and getattr(project_store, 'current_project', None):
            project_store.current_project.view_models[active_tab] = m
            try:
                from services.project_service import save_project
                if getattr(project_store, 'project_dir', None):
                    save_project(project_store.current_project, project_store.project_dir)
            except Exception:
                pass
        try:
            model_text.value = m
            model_text.update()
        except Exception:
            pass
        try:
            if e is not None and getattr(e, 'page', None) is not None:
                p = e.page
                if getattr(p, 'snack_bar', None) is None:
                    p.snack_bar = ft.SnackBar(content=ft.Text(f"Model set for {active_tab}: {m}"))
                else:
                    p.snack_bar.content = ft.Text(f"Model set for {active_tab}: {m}")
                p.snack_bar.open = True
                p.update()
        except Exception:
            pass

    model_text = ft.Text(current_model, size=12, color="#cccccc")

    all_models = getattr(config, 'IMAGE_MODELS', [])
    if not all_models:
        fallback = getattr(config, 'IMAGE_MODEL', None)
        all_models = [fallback] if fallback else []

    popup_items = [
        ft.PopupMenuItem(content=ft.Text(m), on_click=lambda e, m=m: _set_model(m, e))
        for m in all_models
    ]

    model_menu = ft.PopupMenuButton(
        icon=ft.Icons.ARROW_DROP_DOWN,
        items=popup_items,
        tooltip="Select image model",
        style=ft.ButtonStyle(
            bgcolor={"": "#242424"},
            padding={"": ft.Padding.symmetric(horizontal=8, vertical=6)},
            shape={"": ft.RoundedRectangleBorder(radius=6)},
        ),
    )

    model_selector = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.IMAGE_OUTLINED, size=14, color="#aaaaaa"),
                model_text,
                model_menu,
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#242424",
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
    )

    from components.art_style_selector import ART_STYLES
    STYLE_OPTIONS = {s["id"]: s["label"] for s in ART_STYLES}

    def _set_style(s_id, e=None):
        if project_store and getattr(project_store, 'current_project', None):
            project_store.current_project.art_style = s_id
            try:
                from services.project_service import save_project
                save_project(project_store.current_project, project_store.project_dir)
            except Exception:
                pass
        try:
            short_label = STYLE_OPTIONS.get(s_id, "Custom Style")
            style_text.tooltip = None if short_label != "Custom Style" else s_id
            style_text.value = short_label
            style_text.update()
        except Exception:
            pass

    current_style_id = getattr(project_store.current_project, 'art_style', "None") if project_store and getattr(project_store, 'current_project', None) else "None"

    display_label = STYLE_OPTIONS.get(current_style_id, "Custom Style")
    style_text = ft.Text(display_label, size=12, color="#cccccc", tooltip=current_style_id if display_label == "Custom Style" else None)

    style_popup_items = [
        ft.PopupMenuItem(content=ft.Text(s["label"]), on_click=lambda e, s_id=s["id"]: _set_style(s_id, e))
        for s in ART_STYLES
    ]

    style_menu = ft.PopupMenuButton(
        icon=ft.Icons.ARROW_DROP_DOWN,
        items=style_popup_items,
        tooltip="Select generation style",
        style=ft.ButtonStyle(
            bgcolor={"": "#242424"},
            padding={"": ft.Padding.symmetric(horizontal=8, vertical=6)},
            shape={"": ft.RoundedRectangleBorder(radius=6)},
        ),
    )

    style_selector = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.COLOR_LENS_OUTLINED, size=14, color="#aaaaaa"),
                ft.Text("Style:", size=12, color="#aaaaaa"),
                style_text,
                style_menu,
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#242424",
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
    )

    right_controls = [style_selector, model_selector]
    if on_home:
        home_btn = ft.IconButton(
            icon=ft.Icons.HOME_OUTLINED,
            icon_color="#cccccc",
            tooltip="Back to Home",
            on_click=lambda _e: on_home(),
        )
        right_controls.append(home_btn)

    right_row = ft.Row(controls=right_controls, spacing=8)

    tabs_row = ft.Row(
        controls=[tab_button(t) for t in TABS],
        spacing=0,
    )

    return ft.Container(
        content=ft.Row(
            controls=[
                brand,
                ft.Container(expand=True, content=tabs_row, alignment=ft.Alignment(0, 0)),
                ft.Row([save_as_button, right_row], spacing=8),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#1a1a1a",
        padding=ft.Padding.symmetric(horizontal=16, vertical=0),
        border=ft.Border.only(bottom=ft.BorderSide(1, "#2a2a2a")),
    )
