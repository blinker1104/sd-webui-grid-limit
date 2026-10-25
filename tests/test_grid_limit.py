"""Stub-based tests: no webui / gradio / torch needed.

Run from the extension root:  python3 -m unittest discover -s tests -v
"""

import importlib.util
import math
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from lib_grid_limit import core  # noqa: E402


# ---------------------------------------------------------------- stubs ----
class _Ctx:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Comp:
    def __init__(self, *a, **k):
        self.kwargs = k


gradio = types.ModuleType("gradio")
gradio.Accordion = gradio.Row = _Ctx
gradio.Checkbox = gradio.Radio = _Comp
sys.modules["gradio"] = gradio


class ImageGridLoopParams:  # copy of modules/script_callbacks.py
    def __init__(self, imgs, cols, rows):
        self.imgs = imgs
        self.cols = cols
        self.rows = rows


_callbacks = {"image_grid": [], "ui_settings": []}
script_callbacks = types.ModuleType("modules.script_callbacks")
script_callbacks.ImageGridLoopParams = ImageGridLoopParams
script_callbacks.on_image_grid = lambda cb, name=None: _callbacks["image_grid"].append(cb)
script_callbacks.on_ui_settings = lambda cb, name=None: _callbacks["ui_settings"].append(cb)


def image_grid_callback(params):
    for cb in _callbacks["image_grid"]:
        try:
            cb(params)
        except Exception as e:  # webui swallows and reports
            raise AssertionError(f"callback raised: {e!r}")


script_callbacks.image_grid_callback = image_grid_callback


class _Opts:
    def __init__(self):
        self.data = {}
        self.n_rows = -1
        self.grid_prevent_empty_spots = False
        self.added = {}

    def add_option(self, key, info):
        self.added[key] = info


class OptionInfo:
    def __init__(self, default=None, label="", component=None, component_args=None, section=None, category_id=None, **k):
        self.default, self.label, self.section, self.category_id = default, label, section, category_id
        self.component_args = component_args

    def info(self, *_):
        return self

    def needs_reload_ui(self):
        return self


shared = types.ModuleType("modules.shared")
shared.opts = _Opts()
shared.OptionInfo = OptionInfo

scripts_mod = types.ModuleType("modules.scripts")
scripts_mod.AlwaysVisible = object()
scripts_mod.Script = type("Script", (), {})

modules = types.ModuleType("modules")
modules.scripts, modules.script_callbacks, modules.shared = scripts_mod, script_callbacks, shared
sys.modules.update({"modules": modules, "modules.scripts": scripts_mod,
                    "modules.script_callbacks": script_callbacks, "modules.shared": shared})

spec = importlib.util.spec_from_file_location("grid_limit_script", os.path.join(ROOT, "scripts", "grid_limit.py"))
gl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gl)


# ------------------------------- mirror of upstream image_grid row logic ---
def image_grid(imgs, batch_size=1, rows=None):
    opts = shared.opts
    if rows is None:
        if opts.n_rows > 0:
            rows = opts.n_rows
        elif opts.n_rows == 0:
            rows = batch_size
        elif opts.grid_prevent_empty_spots:
            rows = math.floor(math.sqrt(len(imgs)))
            while len(imgs) % rows != 0:
                rows -= 1
        else:
            rows = round(math.sqrt(len(imgs)))
    if rows > len(imgs):
        rows = len(imgs)
    cols = math.ceil(len(imgs) / rows)
    params = script_callbacks.ImageGridLoopParams(imgs, cols, rows)
    script_callbacks.image_grid_callback(params)
    return params  # stand-in for the PIL grid


class P:
    def __init__(self, n_iter=1, batch_size=1, script_index=0):
        self.n_iter, self.batch_size = n_iter, batch_size
        self.script_args = (script_index, True, "4")
        self.extra_generation_params = {}


def process_images_inner(p):
    """Same call shape as modules/processing.py: grid of output_images."""
    output_images = [f"img{i}" for i in range(p.n_iter * p.batch_size)]
    grid = image_grid(output_images, p.batch_size)
    return output_images, grid


def run(p, enabled=True, limit="4"):
    s = gl.GridLimitScript()
    s.process(p, enabled, limit)
    try:
        return process_images_inner(p)
    finally:
        s.postprocess(p, None, enabled, limit)


# ------------------------------------------------------------------ tests --
class CoreTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(core.normalize_limit("9"), 9)
        self.assertEqual(core.normalize_limit(16), 16)
        self.assertEqual(core.normalize_limit("16.0"), 16)
        self.assertEqual(core.normalize_limit("7"), 4)
        self.assertEqual(core.normalize_limit(None), 4)

    def test_no_change_when_within_limit(self):
        for lim in (4, 9, 16):
            for n in range(0, lim + 1):
                self.assertIsNone(core.compute_layout(n, lim))

    def test_square_layouts(self):
        self.assertEqual(core.compute_layout(5, 4), (4, 2, 2))
        self.assertEqual(core.compute_layout(10, 9), (9, 3, 3))
        self.assertEqual(core.compute_layout(100, 16), (16, 4, 4))

    def test_non_square_follows_row_logic(self):
        self.assertEqual(core.compute_layout(8, 4, batch_size=4, n_rows=0, force_square=False), (4, 4, 1))
        self.assertEqual(core.compute_layout(20, 16, n_rows=2, force_square=False), (16, 2, 8))
        self.assertEqual(core.compute_layout(20, 9, n_rows=-1, force_square=False), (9, 3, 3))


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        shared.opts.n_rows = -1
        shared.opts.data = {}

    def test_truncates_batch_grid_keeps_all_images(self):
        p = P(n_iter=3, batch_size=4)  # 12 images
        out, grid = run(p, True, "4")
        self.assertEqual(len(out), 12)                      # individual images untouched
        self.assertEqual(grid.imgs, ["img0", "img1", "img2", "img3"])
        self.assertEqual((grid.rows, grid.cols), (2, 2))
        self.assertEqual(p.extra_generation_params.get("Grid limit"), 4)
        self.assertFalse(hasattr(p, core.ATTR))             # cleaned up

    def test_9_and_16(self):
        _, g = run(P(n_iter=2, batch_size=8), True, "9")
        self.assertEqual((len(g.imgs), g.rows, g.cols), (9, 3, 3))
        _, g = run(P(n_iter=5, batch_size=4), True, "16")
        self.assertEqual((len(g.imgs), g.rows, g.cols), (16, 4, 4))

    def test_unchanged_when_not_more_than_limit(self):
        p = P(n_iter=1, batch_size=3)
        _, g = run(p, True, "4")
        self.assertEqual(len(g.imgs), 3)
        self.assertNotIn("Grid limit", p.extra_generation_params)

    def test_disabled(self):
        _, g = run(P(n_iter=2, batch_size=4), False, "4")
        self.assertEqual(len(g.imgs), 8)

    def test_selectable_script_is_skipped(self):
        _, g = run(P(n_iter=2, batch_size=4, script_index=3), True, "4")
        self.assertEqual(len(g.imgs), 8)

    def test_other_callers_untouched(self):
        """e.g. xyz_grid.draw_xyz_grid -> images.image_grid(...) while p is armed."""
        p = P(n_iter=2, batch_size=4)
        gl.GridLimitScript().process(p, True, "4")

        def draw_xyz_grid():
            return image_grid([f"c{i}" for i in range(12)], rows=3)

        g = draw_xyz_grid()
        self.assertEqual((len(g.imgs), g.rows, g.cols), (12, 3, 4))

    def test_copy_of_p_does_not_inherit(self):
        import copy
        p = P(n_iter=2, batch_size=4)
        gl.GridLimitScript().process(p, True, "4")
        pc = copy.copy(p)
        _, g = process_images_inner(pc)
        self.assertEqual(len(g.imgs), 8)

    def test_settings_registered(self):
        for cb in _callbacks["ui_settings"]:
            cb()
        self.assertEqual(shared.opts.added["grid_limit_default"].component_args, {"choices": ["4", "9", "16"]})
        self.assertEqual(shared.opts.added["grid_limit_default"].section, ("grid_limit", "Grid Limit"))


if __name__ == "__main__":
    unittest.main()
