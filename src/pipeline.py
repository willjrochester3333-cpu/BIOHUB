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
    tracker = DatasetTracker(scale=SCALE, params=TRACKING_PARAMS)

    for t in range(len(series)):
        volume = series.get_frame(t)
        detections = detect_cells(volume, SCALE, DETECTION_PARAMS)
        tracker.add_frame(t, detections)

    return dataset_rows(dataset_name, tracker.nodes, tracker.edges)


def discover_test_datasets(test_dir: str) -> list[tuple[str, str]]:
    paths = sorted(glob.glob(os.path.join(test_dir, "*.zarr")))
    return [(p, os.path.splitext(os.path.basename(p))[0]) for p in paths]


def run(test_dir: str, output_path: str) -> pd.DataFrame:
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
    TEST_DIR = "/kaggle/input/biohub-cell-tracking/test"
    OUTPUT_PATH = "/kaggle/working/submission.csv"
    run(TEST_DIR, OUTPUT_PATH)
