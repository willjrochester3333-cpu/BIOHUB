"""Smoke test on a synthetic 3D+t volume with a moving cell and a division.

No real microscopy data is available in this environment, so this exercises
detection -> linking -> division recovery -> submission formatting on data
with a known-correct answer, to catch integration bugs before the pipeline
ever touches the real dataset.
"""
import numpy as np

from src.detection import DetectionParams, PhysicalScale, detect_cells
from src.submission import build_submission, dataset_rows
from src.tracking import DatasetTracker, TrackingParams


def make_blob(shape, center, sigma=2.5, amplitude=1000.0):
    zz, yy, xx = np.indices(shape)
    cz, cy, cx = center
    d2 = (zz - cz) ** 2 + (yy - cy) ** 2 + (xx - cx) ** 2
    return amplitude * np.exp(-d2 / (2 * sigma ** 2))


def build_synthetic_series():
    shape = (20, 60, 60)
    n_frames = 5
    volumes = []

    # Cell A drifts steadily.
    a_path = [(10, 15 + 2 * t, 15) for t in range(n_frames)]
    # Cell B divides at t=2 into two daughters that separate afterwards.
    b_path_pre = [(10, 40, 15), (10, 40, 16)]
    b_daughters = {
        2: [(10, 40, 17)],
        3: [(10, 37, 15), (10, 43, 20)],
        4: [(10, 34, 12), (10, 46, 24)],
    }

    for t in range(n_frames):
        vol = np.zeros(shape, dtype=np.float32)
        vol += make_blob(shape, a_path[t])
        if t < 2:
            vol += make_blob(shape, b_path_pre[t])
        else:
            for center in b_daughters[t]:
                vol += make_blob(shape, center)
        noise = np.random.default_rng(t).normal(0, 5, size=shape).astype(np.float32)
        volumes.append(np.clip(vol + noise, 0, None))

    return volumes


def test_detection_finds_expected_cell_counts():
    volumes = build_synthetic_series()
    scale = PhysicalScale()
    params = DetectionParams(min_peak_separation_um=2.0)

    counts = [detect_cells(v, scale, params).shape[0] for v in volumes]
    assert counts[0] == 2  # A + B (pre-division)
    assert counts[1] == 2
    assert counts[-1] == 3  # A + 2 daughters


def test_full_pipeline_produces_a_division_and_valid_submission():
    volumes = build_synthetic_series()
    scale = PhysicalScale()
    det_params = DetectionParams(min_peak_separation_um=2.0)
    track_params = TrackingParams(max_link_dist_um=8.0, max_division_dist_um=10.0)

    tracker = DatasetTracker(scale=scale, params=track_params)
    for t, vol in enumerate(volumes):
        detections = detect_cells(vol, scale, det_params)
        tracker.add_frame(t, detections)

    assert len(tracker.nodes) > 0
    assert len(tracker.edges) > 0

    out_degree = {}
    for src, dst in tracker.edges:
        out_degree[src] = out_degree.get(src, 0) + 1
    assert max(out_degree.values()) >= 2, "expected at least one division (out-degree >= 2)"

    node_ids = {n[0] for n in tracker.nodes}
    for src, dst in tracker.edges:
        assert src in node_ids
        assert dst in node_ids

    rows = dataset_rows("synthetic", tracker.nodes, tracker.edges)
    submission = build_submission([rows])

    assert list(submission.columns) == [
        "id", "dataset", "row_type", "node_id", "t", "z", "y", "x", "source_id", "target_id",
    ]
    assert (submission["id"] == range(len(submission))).all()

    node_rows = submission[submission["row_type"] == "node"]
    edge_rows = submission[submission["row_type"] == "edge"]
    assert (node_rows["source_id"] == -1).all()
    assert (node_rows["target_id"] == -1).all()
    assert (edge_rows[["node_id", "t", "z", "y", "x"]] == -1).all().all()
    assert set(edge_rows["source_id"]) <= set(node_rows["node_id"])
    assert set(edge_rows["target_id"]) <= set(node_rows["node_id"])
