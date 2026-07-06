"""Assemble the competition submission.csv from per-dataset nodes/edges."""
from __future__ import annotations

import pandas as pd

COLUMNS = ["id", "dataset", "row_type", "node_id", "t", "z", "y", "x", "source_id", "target_id"]


def dataset_rows(dataset: str, nodes: list[tuple[int, int, int, int, int]], edges: list[tuple[int, int]]) -> pd.DataFrame:
    node_rows = [
        {
            "dataset": dataset,
            "row_type": "node",
            "node_id": nid,
            "t": t,
            "z": z,
            "y": y,
            "x": x,
            "source_id": -1,
            "target_id": -1,
        }
        for nid, t, z, y, x in nodes
    ]
    edge_rows = [
        {
            "dataset": dataset,
            "row_type": "edge",
            "node_id": -1,
            "t": -1,
            "z": -1,
            "y": -1,
            "x": -1,
            "source_id": src,
            "target_id": dst,
        }
        for src, dst in edges
    ]
    return pd.DataFrame(node_rows + edge_rows)


def build_submission(per_dataset_rows: list[pd.DataFrame]) -> pd.DataFrame:
    if not per_dataset_rows:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.concat(per_dataset_rows, ignore_index=True)
    df.insert(0, "id", range(len(df)))
    return df[COLUMNS]


def write_submission(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False)
