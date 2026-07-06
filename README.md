# Biohub — Cell Tracking During Development

Baseline solution for the Kaggle "Biohub - Cell Tracking During Development"
competition: detect zebrafish cells in 3D+time microscopy volumes, link them
across frames, recover cell divisions, and reconstruct lineages.

## Approach

No trained model or ground truth is required — this is a classical
computer-vision baseline meant to run standalone in a Kaggle Notebook with
internet access disabled, and to serve as a starting point to improve on.

1. **Detection** (`src/detection.py`): anisotropic Gaussian smoothing (voxel
   sigma derived from the physical scale, since z spacing is ~4x coarser
   than xy) → Otsu/relative intensity threshold → local maxima spaced by a
   physical radius (not voxel count) → marker-controlled watershed →
   intensity-weighted centroid per region.
2. **Linking** (`src/tracking.py`): frame-to-frame 1-1 assignment via the
   Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) on
   physically-scaled centroid distance. The cost matrix is padded with
   dummy rows/columns (cost = distance threshold) so cells can appear,
   disappear, or go unmatched instead of being forced into a bad pairing.
3. **Division recovery**: any cell left unmatched by the 1-1 step is
   attached to its nearest neighbor in the previous frame (within a looser
   distance gate). If that parent already has an edge, it now has two —
   a division.
4. **Submission** (`src/submission.py`): formats nodes and edges into the
   required `submission.csv` schema.

## Layout

```
main.py          single-file version: everything inlined into one main()
notebook/kaggle_submission.ipynb   same thing, split across notebook cells
src/
  detection.py   3D blob detection for one timepoint volume
  tracking.py    frame-to-frame linking + division recovery
  data.py        zarr access (single 4D array, or per-timepoint group)
  submission.py  submission.csv formatting
  pipeline.py    end-to-end driver (discovers test datasets, writes submission.csv)
notebook/
  kaggle_submission.ipynb   self-contained notebook to upload directly to Kaggle
tests/
  test_synthetic.py         smoke test on a synthetic moving+dividing cell
```

## Running

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v          # synthetic smoke test (no real data needed)
python3 -m src.pipeline              # edit TEST_DIR/OUTPUT_PATH at the bottom of pipeline.py

# or the single-file version:
python3 main.py --test-dir /kaggle/input/biohub-cell-tracking/test \
                 --output /kaggle/working/submission.csv
```

For the actual Kaggle submission, upload `notebook/kaggle_submission.ipynb`
as a Code Competition notebook, or paste the contents of `main.py` into a
single notebook cell and call `main(test_dir=..., output_path=...)`. Both
are fully self-contained (no dependency on this repo's `src/` package) and
produce byte-identical output — `main.py` is the same detect/link/divide/
submit logic as `src/`, just inlined into one `main()` function for people
who'd rather copy-paste one block than manage multiple files.

**Before relying on this for a leaderboard score**, inspect a real test
`.zarr` volume's layout (`ZarrTimeSeries` in `src/data.py` / the notebook's
data-access cell currently handles a single `(T, Z, Y, X)` array or a group
keyed by per-timepoint index — adjust if the real layout differs), and tune
`DetectionParams` / `TrackingParams` against a few training volumes with
known ground truth — thresholds and distance gates are density- and
noise-dependent.

## Where to improve

- Swap the classical watershed detector for a learned 3D segmentation model
  (e.g. StarDist3D or a U-Net), especially for dense/irregular cell
  populations where intensity-based watershed under- or over-segments.
- Add appearance features (intensity, size) to the linking cost, not just
  distance.
- Bridge missed detections with skip-frame linking (link t → t+2 when a
  cell has no match at t+1).
- Tighten division heuristics (`recover_divisions`) to cut false positives
  from detection noise — e.g. require daughter size/intensity symmetry.
