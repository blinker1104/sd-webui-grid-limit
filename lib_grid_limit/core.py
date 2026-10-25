"""Pure helper logic for sd-webui-grid-limit.

This module intentionally has no dependency on the webui so it can be unit
tested in isolation.
"""

import math

ALLOWED_LIMITS = (4, 9, 16)
DEFAULT_LIMIT = 4


def normalize_limit(value, fallback=DEFAULT_LIMIT):
    """Convert a UI/API/settings value ("4", 9, "16.0", ...) to one of ALLOWED_LIMITS."""
    try:
        limit = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return fallback
    return limit if limit in ALLOWED_LIMITS else fallback


def default_rows(count, batch_size, n_rows, prevent_empty_spots):
    """Mirror of the row logic in modules/images.py::image_grid (A1111 1.10 / Forge)."""
    if count <= 0:
        return 1
    if n_rows > 0:
        rows = n_rows
    elif n_rows == 0:
        rows = batch_size
    elif prevent_empty_spots:
        rows = math.floor(math.sqrt(count))
        while count % rows != 0:
            rows -= 1
    else:
        rows = round(math.sqrt(count))
    rows = max(1, int(rows))
    return min(rows, count)


def compute_layout(total, limit, batch_size=1, n_rows=-1, prevent_empty_spots=False, force_square=True):
    """Return (count, rows, cols) for a truncated grid, or None if no change is needed.

    - total <= limit  -> None (original behaviour untouched)
    - total >  limit  -> only the first ``limit`` images are used.
      With force_square and a square limit (4/9/16) the grid becomes 2x2/3x3/4x4,
      otherwise the normal webui row logic is applied to the truncated list.
    """
    if limit is None or limit <= 0 or total <= limit:
        return None

    count = limit
    side = math.isqrt(count)
    if force_square and side * side == count:
        rows = side
    else:
        rows = default_rows(count, batch_size, n_rows, prevent_empty_spots)

    cols = math.ceil(count / rows)
    return count, rows, cols


ATTR = "_grid_limit_cfg"
BATCH_GRID_CALLER = "process_images_inner"
GRID_FUNCTION = "image_grid"


def make_config(p, limit, force_square):
    """Config stored on the processing object itself (no global state)."""
    return {
        "owner": id(p),
        "limit": normalize_limit(limit),
        "batch_size": max(1, int(getattr(p, "batch_size", 1) or 1)),
        "force_square": bool(force_square),
    }


def find_batch_grid_processing(frame, max_depth=12):
    """Walk up the call stack from the on_image_grid callback.

    Returns the ``p`` local of processing.process_images_inner() if (and only
    if) the grid currently being built is the normal batch grid, i.e. the
    direct caller of images.image_grid() is process_images_inner(). Grids
    built by anything else (X/Y/Z plot, Prompt matrix, other extensions)
    return None and are left untouched.
    """
    depth = 0
    f = frame
    while f is not None and depth < max_depth:
        if f.f_code.co_name == GRID_FUNCTION:
            caller = f.f_back
            if caller is not None and caller.f_code.co_name == BATCH_GRID_CALLER:
                return caller.f_locals.get("p")
            return None
        f = f.f_back
        depth += 1
    return None


def config_for(p):
    cfg = getattr(p, ATTR, None) if p is not None else None
    if not cfg or cfg.get("owner") != id(p):
        # missing, or inherited by a copy(p) made by another script
        return None
    return cfg


def apply_to_grid_params(params, cfg, n_rows=-1, prevent_empty_spots=False):
    """Modify an ImageGridLoopParams-like object (imgs/rows/cols) in place.

    Returns True if the grid was truncated.
    """
    if not cfg:
        return False

    imgs = params.imgs
    layout = compute_layout(len(imgs), cfg["limit"], cfg["batch_size"], n_rows, prevent_empty_spots, cfg["force_square"])
    if layout is None:
        return False

    count, rows, cols = layout
    # assign a NEW list: params.imgs is the caller's output_images list,
    # which must keep every individual image.
    params.imgs = list(imgs[:count])
    params.rows = rows
    params.cols = cols
    return True
