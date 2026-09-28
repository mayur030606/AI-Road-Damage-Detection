# Machine Learning Baseline Evaluation Results

This document records the baseline evaluation metrics of trained computer vision models on held-out test dataset splits.

---

## 1. Pothole Detection Model

- **Architecture**: YOLOv8 Nano (`yolov8n`)
- **Evaluation Dataset**: Held-out test split (246 test images)
- **Baseline Metrics**:
  - **Precision**: 86.5%
  - **Recall**: 75.8%
  - **mAP@0.5**: 81.5%
  - **mAP@0.5-0.95**: 51.6%

### Per-Class Performance:
| Class Name | Test Images | Instances | Precision | Recall | mAP@0.5 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Drain Hole** | 9 | 9 | 86.8% | 73.4% | 75.2% |
| **Pothole** | 222 | 473 | 88.0% | 71.2% | 82.1% |
| **Sewer Cover** | 17 | 23 | 84.7% | 82.6% | 87.2% |

---

## 2. Zebra Crossing Condition Model

- **Architecture**: YOLOv8 Nano (`yolov8n`)
- **Training Setup**: 20 epochs on deduplicated 2-class dataset (`datasets/zebra_crossing_clean`)
- **Evaluation Dataset**: Held-out test split (210 test images)
- **Baseline Metrics**:
  - **Overall mAP@0.5**: 50.3%

### Per-Class Performance:
| Class Name | Class ID | mAP@0.5 | Recall | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **GOOD_ZEBRA_CROSSING** | 1 | **86.4%** | - | Strong baseline performance |
| **FADED_ZEBRA_CROSSING** | 0 | **14.2%** | **13.3%** | Minority class baseline |

---

## Current Observations & Next Steps

1. **Class Imbalance**: Faded zebra crossing detection requires further dataset expansion and targeted data augmentations due to class imbalance in training samples.
2. **Missing Crossing Detection**: Missing zebra crossing identification should rely on GIS spatial baseline comparisons rather than assuming absence of detection implies a missing crossing.
