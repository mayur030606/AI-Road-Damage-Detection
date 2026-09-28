"""
Download Roboflow Datasets for SIH Project
Downloads Dataset 1, Dataset 2, and Dataset 3 into separate directories.
Uses ROBOFLOW_API_KEY environment variable without exposing keys in code.
"""

import os
import sys
import shutil
from pathlib import Path
from roboflow import Roboflow

# Standardize output encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASETS_DIR = ROOT_DIR / "datasets"

DATASETS = [
    {
        "name": "pothole_dataset_1",
        "workspace": "intel-unnati-training-program",
        "project": "pothole-detection-bqu6s",
        "version": 7,
        "location": DATASETS_DIR / "pothole_dataset_1"
    },
    {
        "name": "pothole_dataset_2",
        "workspace": "intel-unnati-training-program",
        "project": "pothole-detection-bqu6s",
        "version": 9,
        "location": DATASETS_DIR / "pothole_dataset_2"
    },
    {
        "name": "zebra_crossing_dataset",
        "workspace": "co-099-mayur-rasal",
        "project": "road-marking-detection-qj8ey-bqgi6",
        "version": 1,
        "location": DATASETS_DIR / "zebra_crossing_dataset"
    }
]

def download_all():
    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        print("[ERROR] ROBOFLOW_API_KEY environment variable is not set.")
        print("Please set ROBOFLOW_API_KEY before running this script.")
        sys.exit(1)

    rf = Roboflow(api_key=api_key)

    for ds in DATASETS:
        target_dir = ds["location"]
        print(f"\n[+] Processing {ds['name']} (Workspace: {ds['workspace']}, Project: {ds['project']}, Version: {ds['version']})...")
        
        # Change current directory so Roboflow downloads directly into location or move after download
        original_cwd = os.getcwd()
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            os.chdir(str(target_dir))
            
            project_obj = rf.workspace(ds["workspace"]).project(ds["project"])
            version_obj = project_obj.version(ds["version"])
            downloaded_dataset = version_obj.download("yolov8")
            print(f"[SUCCESS] Downloaded {ds['name']} successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to download {ds['name']}: {e}")
        finally:
            os.chdir(original_cwd)

if __name__ == "__main__":
    download_all()
