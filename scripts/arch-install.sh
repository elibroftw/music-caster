#!/usr/bin/env bash
echo "arch-based distro detected"
PYTHON=$1

# Check for python3.12
if ! pacman -Q "$PYTHON" &> /dev/null; then
  echo "$PYTHON not found. Installing..."
  sudo pacman -Sy --noconfirm "$PYTHON" "$PYTHON-dev" "$PYTHON-virtualenv" "$PYTHON-tk"
fi

# Check for pip
if ! $PYTHON -m pip --version &> /dev/null; then
  echo "pip not found. Installing..."
  sudo pacman -Sy --noconfirm python-pip
fi

# Check for tkinter
if ! $PYTHON -c "import tkinter" &> /dev/null; then
  echo "tkinter not found. Installing..."
  sudo pacman -Sy --noconfirm $PYTHON-tk
fi

# Check for python3-venv
echo "Ensuring $PYTHON-virtualenv is insalled"
sudo pacman -Sy --noconfirm "$PYTHON-virtualenv"
