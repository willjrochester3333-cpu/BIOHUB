"""End-to-end driver: zarr volumes -> detections -> tracks -> submission.csv.

Adjust INPUT_DIR / OUTPUT_PATH for the Kaggle notebook environment
(typically something under /kaggle/input/<competition-slug>/test and
/kaggle/working/submission.csv).
"""
from __future__ import annotations

import glob
import os

import pandas as pd

from src.data import open_dataset
from src.detection import DetectionParams, PhysicalScale, detect_cells
from src.submission import build_submission, dataset_rows, write_submission
from src.tracking import DatasetTracker, TrackingParams

SCALE = PhysicalScale(z=1.625, y=0.40625, x=0.40625)
DETECTION_PARAMS = DetectionParams()
TRACKING_PARAMS = TrackingParams()


def track_dataset(zarr_path: str, dataset_name: str) -> pd.DataFrame:
    series = open_dataset(zarr_path)
    print(f"[{dataset_name}] {len(series)} timepoint(s) detected "
          f"(mode={series._mode}, shape={getattr(series._payload[0], 'shape', None)})")
    tracker = DatasetTracker(scale=SCALE, params=TRACKING_PARAMS)

    for t in range(len(series)):
        volume = series.get_frame(t)
        detections = detect_cells(volume, SCALE, DETECTION_PARAMS)
        tracker.add_frame(t, detections)

    return dataset_rows(dataset_name, tracker.nodes, tracker.edges)


def discover_test_datasets(test_dir: str) -> list[tuple[str, str]]:
    paths = sorted(glob.glob(os.path.join(test_dir, "*.zarr")))
    return [(p, os.path.splitext(os.path.basename(p))[0]) for p in paths]


def discover_test_dir(root: str = "/kaggle/input") -> str:
    """Find a folder under `root` containing *.zarr subfolders.

    Kaggle mounts competition data at /kaggle/input/<competition-slug>/...
    and the slug isn't known ahead of time, so this walks the tree looking
    for a directory that directly contains .zarr datasets, preferring one
    literally named "test". Doesn't descend into .zarr stores themselves
    (they're directories full of chunk files) to keep the walk fast.
    """
    if not os.path.isdir(root):
        raise FileNotFoundError(f"{root} does not exist")

    candidates = []
    for dirpath, dirnames, _filenames in os.walk(root):
        if any(d.endswith(".zarr") for d in dirnames):
            candidates.append(dirpath)
        dirnames[:] = [d for d in dirnames if not d.endswith(".zarr")]

    if not candidates:
        raise FileNotFoundError(
            f"No folder containing *.zarr subfolders found under {root}. "
            "Pass test_dir explicitly."
        )

    preferred = [c for c in candidates if os.path.basename(c).lower() == "test"]
    return preferred[0] if preferred else candidates[0]


def run(test_dir: str | None = None, output_path: str = "/kaggle/working/submission.csv") -> pd.DataFrame:
    if test_dir is None:
        test_dir = discover_test_dir()
        print(f"Auto-detected test_dir: {test_dir}")

    datasets = discover_test_datasets(test_dir)
    if not datasets:
        raise FileNotFoundError(f"No .zarr datasets found under {test_dir}")

    per_dataset = []
    for zarr_path, name in datasets:
        print(f"[{name}] tracking...")
        rows = track_dataset(zarr_path, name)
        n_nodes = (rows["row_type"] == "node").sum()
        n_edges = (rows["row_type"] == "edge").sum()
        print(f"[{name}] {n_nodes} nodes, {n_edges} edges")
        per_dataset.append(rows)

    submission = build_submission(per_dataset)
    write_submission(submission, output_path)
    print(f"Wrote {output_path} ({len(submission)} rows)")
    return submission


if __name__ == "__main__":
    run(test_dir=None, output_path="/kaggle/working/submission.csv")
