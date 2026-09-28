#!/bin/bash
# One-time Raspberry Pi setup for SIH26124 pothole detection.
# Run on Pi:  bash scripts/setup_pi.sh

set -e

APP_DIR="${HOME}/projects/my_app"
cd "$APP_DIR" || { echo "ERROR: $APP_DIR not found. Copy project from PC first."; exit 1; }

echo "=== SIH26124 Raspberry Pi Setup ==="
echo "Project: $APP_DIR"

echo "[1/6] Installing system packages..."
sudo apt update
sudo apt install -y \
  python3-venv python3-pip python3-dev \
  python3-picamera2 python3-opencv \
  libopenblas0 \
  git curl rpicam-apps

echo "[2/6] Creating Python virtual environment..."
python3 -m venv venv

echo "[3/6] Enabling system picamera2 inside venv..."
if ! grep -q "include-system-site-packages = true" venv/pyvenv.cfg; then
  echo "include-system-site-packages = true" >> venv/pyvenv.cfg
fi

echo "[4/6] Installing Python packages (ONNX — no PyTorch needed on Pi)..."
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements-pi.txt

echo "[5/6] Checking AI model files..."
MISSING=0
if [ ! -f "ai/models/pothole_model.onnx" ]; then
  echo "  MISSING: ai/models/pothole_model.onnx"
  echo "  Copy from PC: scp ai/models/pothole_model.onnx shivraj@10.54.12.49:~/projects/my_app/ai/models/"
  MISSING=1
fi
if [ ! -f "ai/models/pothole_model.pt" ]; then
  echo "  WARN: ai/models/pothole_model.pt not found (ONNX is enough for Pi)"
fi
if [ "$MISSING" -eq 1 ]; then
  echo "Setup paused — copy pothole_model.onnx from your PC, then re-run this script."
  exit 1
fi

echo "[6/6] Verifying detector import..."
python -c "
from ai.detector import PotholeDetector
import os
path = 'ai/models/pothole_model.onnx'
if not os.path.exists(path):
    path = 'ai/models/pothole_model.pt'
d = PotholeDetector(pothole_model_path=path, pothole_conf=0.50)
print('Detector OK — backend:', 'onnx' if d.is_onnx else ('tflite' if d.is_tflite else 'yolo'))
"

cat <<'EOF'

=== SETUP COMPLETE ===

Every time you open a new terminal on the Pi, run:

  cd ~/projects/my_app
  source venv/bin/activate

Then test:

  python -m ai.cli status --backend-url http://YOUR_PC_IP:8000/api/v1/incidents

Live camera (backend must run on PC first):

  python -m ai.cli live --source 0 --conf 0.50 \
    --backend-url http://YOUR_PC_IP:8000/api/v1/incidents --token sih_admin

EOF
