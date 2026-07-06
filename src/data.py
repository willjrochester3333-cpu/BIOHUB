"""Zarr access helpers.

The exact on-disk layout of the competition's .zarr volumes isn't pinned
down here (inspect one in the Kaggle notebook and adjust `open_dataset` if
needed). Two conventions are handled out of the box:

1. A single array of shape (T, Z, Y, X) at the zarr root.
2. A zarr group with one (Z, Y, X) array per timepoint, keyed by the
   stringified integer index ("0", "1", "2", ...).
"""
from __future__ import annotations

import zarr


class ZarrTimeSeries:
    def __init__(self, path: str):
        self._store = zarr.open(path, mode="r")
        if hasattr(self._store, "ndim") and self._store.ndim == 4:
            self._mode = "array"
            self._n_frames = self._store.shape[0]
        else:
            self._mode = "group"
            self._n_frames = len(list(self._store.array_keys()))

    def __len__(self) -> int:
        return self._n_frames

    def get_frame(self, t: int):
        if self._mode == "array":
            return self._store[t]
        return self._store[str(t)][:]


def open_dataset(path: str) -> ZarrTimeSeries:
    return ZarrTimeSeries(path)
