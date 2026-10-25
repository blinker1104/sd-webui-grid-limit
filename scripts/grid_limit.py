"""sd-webui-grid-limit

Limit the batch grid of txt2img / img2img to the first 4, 9 or 16 images.
Individual images are saved and shown exactly as before.

Mechanism (no core file is modified, nothing is monkey-patched):
- process()      : the AlwaysVisible script stores a small config dict on the
                   processing object ``p`` (only when enabled and no selectable
                   script such as X/Y/Z plot is chosen).
- on_image_grid  : official callback from modules/images.py::image_grid().
                   It only acts when image_grid() was called directly by
                   processing.process_images_inner() for that same ``p``,
                   and then truncates params.imgs to the first N images and
                   sets params.rows / params.cols.
- postprocess()  : removes the config from ``p`` again.
State lives on ``p`` (one object per request), so concurrent API/UI requests
cannot leak into each other.
"""

import inspect

import gradio as gr

from modules import scripts, script_callbacks, shared

from lib_grid_limit.core import (
    ALLOWED_LIMITS,
    ATTR,
    DEFAULT_LIMIT,
    apply_to_grid_params,
    config_for,
    find_batch_grid_processing,
    make_config,
    normalize_limit,
)

SECTION = ("grid_limit", "Grid Limit")
OPT_ENABLED = "grid_limit_enabled_default"
OPT_LIMIT = "grid_limit_default"
OPT_SQUARE = "grid_limit_force_square"
OPT_INFOTEXT = "grid_limit_write_infotext"

CHOICES = [str(x) for x in ALLOWED_LIMITS]
INFOTEXT_KEY = "Grid limit"


def _opt(key, default):
    data = getattr(shared.opts, "data", None) or {}
    return data.get(key, default)


def _selectable_script_active(p):
    """True if a script is picked in the 'Script' dropdown (X/Y/Z plot, Prompt matrix, ...)."""
    args = getattr(p, "script_args", None)
    if not args:
        return False
    try:
        return int(args[0] or 0) > 0
    except (TypeError, ValueError):
        return False


def _clear(p):
    if p is not None and hasattr(p, ATTR):
        try:
            delattr(p, ATTR)
        except AttributeError:
            pass


class GridLimitScript(scripts.Script):
    sorting_priority = 100

    def title(self):
        return "Grid Limit"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        tab = "img2img" if is_img2img else "txt2img"
        default_enabled = bool(_opt(OPT_ENABLED, True))
        default_limit = str(normalize_limit(_opt(OPT_LIMIT, str(DEFAULT_LIMIT))))

        with gr.Accordion("Grid Limit", open=False, elem_id=f"{tab}_grid_limit_accordion"):
            with gr.Row():
                enabled = gr.Checkbox(
                    label="Limit grid images",
                    value=default_enabled,
                    elem_id=f"{tab}_grid_limit_enabled",
                )
                limit = gr.Radio(
                    label="Max images in grid",
                    choices=CHOICES,
                    value=default_limit,
                    elem_id=f"{tab}_grid_limit_value",
                )

        # Only the limit value is pasted back from infotext; the checkbox is left
        # alone so that pasting an old infotext never silently turns the feature off.
        self.infotext_fields = [(limit, INFOTEXT_KEY)]
        return [enabled, limit]

    def process(self, p, enabled=False, limit=DEFAULT_LIMIT, *args):
        _clear(p)
        if not enabled or _selectable_script_active(p):
            return

        cfg = make_config(p, limit, _opt(OPT_SQUARE, True))
        setattr(p, ATTR, cfg)

        total = int(getattr(p, "n_iter", 1) or 1) * int(getattr(p, "batch_size", 1) or 1)
        if total > cfg["limit"] and bool(_opt(OPT_INFOTEXT, True)):
            p.extra_generation_params[INFOTEXT_KEY] = cfg["limit"]

    def postprocess(self, p, processed, *args):
        _clear(p)


def on_image_grid(params):
    frame = inspect.currentframe()
    try:
        p = find_batch_grid_processing(frame)
        cfg = config_for(p)
        if cfg is None:
            return
        apply_to_grid_params(
            params,
            cfg,
            n_rows=int(getattr(shared.opts, "n_rows", -1)),
            prevent_empty_spots=bool(getattr(shared.opts, "grid_prevent_empty_spots", False)),
        )
    finally:
        del frame  # avoid reference cycles


def on_ui_settings():
    shared.opts.add_option(OPT_ENABLED, shared.OptionInfo(
        True, "Enable grid limit by default", gr.Checkbox, section=SECTION, category_id="saving",
    ).info("default for the checkbox in the txt2img/img2img 'Grid Limit' panel").needs_reload_ui())

    shared.opts.add_option(OPT_LIMIT, shared.OptionInfo(
        str(DEFAULT_LIMIT), "Default max images in grid", gr.Radio, {"choices": CHOICES},
        section=SECTION, category_id="saving",
    ).info("4 = 2x2, 9 = 3x3, 16 = 4x4").needs_reload_ui())

    shared.opts.add_option(OPT_SQUARE, shared.OptionInfo(
        True, "Use a square layout (2x2 / 3x3 / 4x4) for limited grids", gr.Checkbox,
        section=SECTION, category_id="saving",
    ).info("off = use the normal 'Grid row count' setting on the first N images"))

    shared.opts.add_option(OPT_INFOTEXT, shared.OptionInfo(
        True, "Write 'Grid limit' to generation parameters when it applies", gr.Checkbox,
        section=SECTION, category_id="saving",
    ))


script_callbacks.on_image_grid(on_image_grid, name="grid_limit")
script_callbacks.on_ui_settings(on_ui_settings, name="grid_limit")
