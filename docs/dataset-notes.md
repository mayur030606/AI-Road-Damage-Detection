# Dataset Preparation & Cleaning Notes

This document describes the dataset cleaning, deduplication, and pre-processing methodology applied to the SIH26124 ML datasets.

---

## 1. Pothole Dataset (`pothole_combined`)

- **Raw Sources**: `pothole_dataset_1` and `pothole_dataset_2`.
- **Deduplication Methodology**: Images were hashed using MD5 digests to detect and remove identical image duplicates across training, validation, and test splits.
- **Combined Yield**:
  - Total Unique Images: **4,129 images**
  - Training Split: 3,392 images
  - Validation Split: 491 images
  - Test Split: 246 images

---

## 2. Zebra Crossing Dataset (`zebra_crossing_clean`)

- **Raw Source**: Roboflow Road Marking Detection dataset (18 original classes).
- **Filtering & Target Classes**:
  - Filtered to retain only images containing zebra crossing annotations.
  - Remapped to 2 target classes:
    - `0` = `FADED_ZEBRA_CROSSING` (from old ID 1)
    - `1` = `GOOD_ZEBRA_CROSSING` (from old ID 6)
- **Leakage & Deduplication**:
  - Resolved all cross-split duplicates (`train` ↔ `val`, `train` ↔ `test`, `val` ↔ `test`).
  - Total Unique Hashes: **2,180 images**
  - Split Counts: `train`: 1,677 | `val`: 293 | `test`: 210
  - Cross-Split Leakage: **0**
