#!/usr/bin/env bash
# ==============================================================================
# SIH26124 - Automated LabelImg Setup for Raspberry Pi (Bookworm 64-bit)
# Hostname: raspberrypi.local | User: shivraj | Pass: raspberry
# ==============================================================================

set -e

echo "===================================================================="
echo "🏷️  INSTALLING LABELIMG ANNOTATION TOOL ON RASPBERRY PI"
echo "===================================================================="

# 1. Install System Dependencies via apt (bypasses PEP 668 restrictions)
sudo apt update
sudo apt install -y pyqt5-dev-tools python3-pyqt5 python3-lxml git python3-pip

# 2. Clone and build official LabelImg source (compatible with Python 3.11+ / Bookworm)
cd /home/shivraj
if [ ! -d "labelImg" ]; then
    echo "Cloning LabelImg repository..."
    git clone https://github.com/HumanSignal/labelImg.git
fi

cd labelImg
echo "Compiling PyQt5 resource file..."
pyrcc5 -o libs/resources.py resources.qrc

# 3. Create Desktop Launcher and wrapper script
WRAPPER_SCRIPT="/home/shivraj/run_labelimg.sh"
cat << 'EOF' > "$WRAPPER_SCRIPT"
#!/usr/bin/env bash
# Set Qt display platform for Raspberry Pi Wayland / X11
export QT_QPA_PLATFORM=xcb
cd /home/shivraj/labelImg
python3 labelImg.py "$@"
EOF

chmod +x "$WRAPPER_SCRIPT"
sudo ln -sf "$WRAPPER_SCRIPT" /usr/local/bin/labelimg

echo "===================================================================="
echo "✅ LabelImg successfully installed on Raspberry Pi!"
echo "To run LabelImg:"
echo "  - In VNC / Desktop Terminal: type 'labelimg'"
echo "  - Over SSH with X11: ssh -X shivraj@raspberrypi.local then 'labelimg'"
echo "===================================================================="
