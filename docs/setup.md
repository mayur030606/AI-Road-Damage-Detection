# Setup and Execution Guide

This document provides instructions for setting up the environment and executing the SIH26124 modules.

---

## 1. Prerequisites & Environment Setup

### Python Perception Engine (Python 3.10+)
```bash
# Install required Python packages
pip install ultralytics torch opencv-python numpy Pillow pytest requests
```

### Node.js / React Frontend (Node 18+)
```bash
cd frontend
npm install
```

### Java Backend (JDK 21)
```bash
cd backend
./mvnw clean install
```

---

## 2. Running AI Perception Pipeline

### Run Unit Tests (64 Passing Tests)
```bash
python -m unittest discover -s ai/tests -p "test_*.py"
```

### Run Unified Road Intelligence CLI
- **Process Video**:
  ```bash
  python -m ai.cli --source sample_video.mp4 --output-dir ai_output --max-frames 15
  ```
- **Process Image**:
  ```bash
  python -m ai.cli --source sample_pothole_road.jpg --output-dir ai_output
  ```

---

## 3. Environment Variables Configuration

Copy `.env.example` to `.env` before running components:
```bash
cp frontend/.env.example frontend/.env
```
Ensure no secret keys or database passwords are hardcoded in source code files.
