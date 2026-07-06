"""Zarr access helpers.

Handles, in order of preference:

1. OME-NGFF multiscale groups (".zattrs" -> "multiscales") -- picks the
   finest resolution level and uses its "axes" metadata (or the t/c-first
   convention) to index out one (Z, Y, X) volume per timepoint.
2. A bare array of shape (T, Z, Y, X) or (T, C, Z, Y, X) at the root.
3. The legacy convention of one 3D (Z, Y, X) array per timepoint, keyed
   "0", "1", ... directly under a plain group.

Call `inspect_zarr(path)` on a real dataset if a layout doesn't fit any of
these and the resulting error doesn't make the actual structure obvious.
"""
from __future__ import annotations

import numpy as np
import zarr


def _zarr_attrs(node) -> dict:
    try:
        return dict(node.attrs)
    except Exception:
        return {}


def _is_zarr_array(node) -> bool:
    return hasattr(node, "shape") and hasattr(node, "dtype")


def _sorted_keys(keys) -> list:
    try:
        return sorted(keys, key=int)
    except ValueError:
        return sorted(keys)


def _axis_names_from_attrs(attrs: dict) -> list | None:
    axes = attrs.get("axes") or attrs.get("_ARRAY_DIMENSIONS")
    if not axes:
        return None
    return [a["name"] if isinstance(a, dict) else str(a) for a in axes]


def _infer_time_channel_axes(ndim: int, axis_names: list | None):
    """Return (t_axis, c_axis) for an array of `ndim` dims.

    Uses OME-NGFF-style axis names ("t", "c", "z", "y", "x") when available;
    otherwise falls back to the near-universal convention that time (and
    channel, if present) are the leading axes.
    """
    if axis_names and len(axis_names) == ndim:
        t_axis = axis_names.index("t") if "t" in axis_names else None
        c_axis = axis_names.index("c") if "c" in axis_names else None
        return t_axis, c_axis
    if ndim == 5:
        return 0, 1
    if ndim == 4:
        return 0, None
    if ndim == 3:
        return None, None
    raise ValueError(f"Don't know how to interpret a {ndim}-D array without axis metadata")


class ZarrTimeSeries:
    def __init__(self, path: str):
        root = zarr.open(path, mode="r")
        self._mode, self._payload = self._resolve(root)

    @classmethod
    def _resolve(cls, node, axis_names=None):
        if _is_zarr_array(node):
            names = axis_names or _axis_names_from_attrs(_zarr_attrs(node))
            t_axis, c_axis = _infer_time_channel_axes(node.ndim, names)
            return "array", (node, t_axis, c_axis)

        attrs = _zarr_attrs(node)
        multiscales = attrs.get("multiscales")
        if multiscales:
            ms = multiscales[0]
            dataset_path = ms["datasets"][0]["path"]
            axes = ms.get("axes")
            names = [a["name"] if isinstance(a, dict) else str(a) for a in axes] if axes else axis_names
            return cls._resolve(node[dataset_path], names)

        array_keys = _sorted_keys(node.array_keys())
        if array_keys:
            first = node[array_keys[0]]
            if len(array_keys) > 1 and first.ndim == 3:
                return "per_frame_group", (node, array_keys)
            return cls._resolve(first, axis_names)

        group_keys = _sorted_keys(node.group_keys())
        if len(group_keys) == 1:
            return cls._resolve(node[group_keys[0]], axis_names)

        raise ValueError(
            f"Could not find a data array in this zarr (keys={list(node.keys())}). "
            "Run inspect_zarr(path) on it and adjust ZarrTimeSeries._resolve."
        )

    def __len__(self) -> int:
        if self._mode == "array":
            array, t_axis, _ = self._payload
            return array.shape[t_axis] if t_axis is not None else 1
        _, keys = self._payload
        return len(keys)

    def get_frame(self, t: int):
        if self._mode == "per_frame_group":
            node, keys = self._payload
            return node[keys[t]][:]

        array, t_axis, c_axis = self._payload
        if t_axis is None:
            frame = array[:]
        else:
            index = [slice(None)] * array.ndim
            index[t_axis] = t
            frame = array[tuple(index)]

        if c_axis is not None:
            shifted_c_axis = c_axis if t_axis is None or c_axis < t_axis else c_axis - 1
            frame = np.take(frame, 0, axis=shifted_c_axis)

        frame = np.asarray(frame)
        while frame.ndim > 3:
            frame = frame[0]
        return frame


def inspect_zarr(path: str, max_depth: int = 4) -> None:
    """Print a zarr dataset's group/array structure, shapes, and attrs."""
    def walk(node, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        attrs = _zarr_attrs(node)
        if _is_zarr_array(node):
            print(f"{prefix}[array] shape={node.shape} dtype={node.dtype} attrs={list(attrs.keys())}")
            return
        print(f"{prefix}[group] attrs={list(attrs.keys())}")
        for key in _sorted_keys(node.array_keys()):
            walk(node[key], prefix + f"  {key}/", depth + 1)
        for key in _sorted_keys(node.group_keys()):
            walk(node[key], prefix + f"  {key}/", depth + 1)

    walk(zarr.open(path, mode="r"), prefix="", depth=0)


def open_dataset(path: str) -> ZarrTimeSeries:
    return ZarrTimeSeries(path)
