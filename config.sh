#!/usr/bin/env bash
set -e

echo "=== 🚀 FLEET Auto Setup Script ==="

confirm_step () {
    echo
    read -p "[*] $1 (press Enter to continue, Ctrl+C to abort)"
}

echo "=== 🔍 Checking dependencies ==="

if command -v python3 >/dev/null 2>&1; then
    PY_VERSION=$(python3 -V 2>&1 | awk '{print $2}')
    if [[ "$(printf '%s\n' "3.10" "$PY_VERSION" | sort -V | head -n1)" != "3.10" ]]; then
        echo "[!] Python >= 3.10 required, found $PY_VERSION"
        exit 1
    fi
else
    echo "[!] Python3.10+ is required but not found."
    exit 1
fi

# Check venv
python3 -m venv --help >/dev/null 2>&1 || { echo "[!] Python venv module not available."; exit 1; }

# Check Docker
command -v docker >/dev/null 2>&1 || { echo "[!] Docker is required but not installed."; exit 1; }

# Check OVS
command -v ovs-vsctl >/dev/null 2>&1 || { echo "[!] Open vSwitch is required but not installed"; exit 1; }

echo "✅ All required dependencies are installed."

# -------------------------------
# 2. Create virtual environment
# -------------------------------
confirm_step "Creating Python virtual environment"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
else
    echo "[*] Virtual environment already exists, skipping creation."
fi
source .venv/bin/activate

# -------------------------------
# 3. Install Python dependencies (except torch)
# -------------------------------
confirm_step "Installing Python dependencies (excluding torch)"
if [ -f "requirements.txt" ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "[!] requirements.txt not found, Aborting."
    exit 1
fi

# -------------------------------
# 4. Install Torch (GPU or CPU)
# -------------------------------
confirm_step "Installing PyTorch (GPU if available, otherwise CPU)"
if command -v nvidia-smi >/dev/null 2>&1; then
    echo "[+] NVIDIA GPU detected, installing CUDA-enabled torch"
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    TORCH_BASE="--index-url https://download.pytorch.org/whl/cu118"
else
    echo "[*] No GPU detected, installing CPU-only torch"
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    TORCH_BASE="--index-url https://download.pytorch.org/whl/cpu"
fi

# -------------------------------
# 5. Install Containernet
# -------------------------------
confirm_step "Cloning and installing Containernet"
git clone https://github.com/containernet/containernet.git /tmp/containernet
cd /tmp/containernet
pip install .
cd -
rm -rf /tmp/containernet

# -------------------------------
# 6. Build Docker images
# -------------------------------
confirm_step "Building Docker images for FL and BG nodes"
# Pass GPU/CPU info to Docker build as an ARG
docker build \
    --build-arg TORCH_BASE="$TORCH_BASE" \
    -t fleet-fl -f static/docker/Dockerfile-FL .

docker build \
    --build-arg TORCH_BASE="$TORCH_BASE" \
    -t fleet-bg -f static/docker/Dockerfile-BG .

# -------------------------------
# 7. Done
# -------------------------------
echo
echo "✅ FLEET setup completed successfully!"
echo "To start using FLEET run:"
echo "sudo .venv/bin/python3 main.py"
