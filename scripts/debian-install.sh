#!/usr/bin/env bash
echo "debian-based distro detected"
PYTHON=$1
# sudo apt install -y software-properties-common
# Check for python3.12
if ! $PYTHON --version &> /dev/null; then
  echo "Python 3.12 not found. Installing..."
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt update
  sudo apt install -y python3.12 "${PYTHON}-venv" "${PYTHON}-tk"
fi

# Check for pip
if ! $PYTHON -m pip --version &> /dev/null; then
  echo "pip not found. Installing..."
  sudo apt update
  sudo apt install -y python3-pip
fi

# Check for tkinter
if ! $PYTHON -c "import tkinter" &> /dev/null; then
  echo "tkinter not found. Installing..."
  sudo apt update
  sudo apt install -y "${PYTHON}-tk"
fi

echo "Ensuring $PYTHON-venv is insalled"
sudo apt update
sudo apt install -y "${PYTHON}-venv"
