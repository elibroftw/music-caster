#!/usr/bin/env bash
echo "fedora-based distro detected"
PYTHON=$1

# Check for $PYTHON
if ! dnf list installed "$PYTHON" &> /dev/null; then
  echo "$PYTHON not found. Installing..."
  sudo dnf install -y "$PYTHON" "$PYTHON-devel" "$PYTHON-virtualenv"
fi

# Check for pip
if ! $PYTHON -m pip --version &> /dev/null; then
  echo "pip not found. Installing..."
  sudo dnf install -y python-pip
fi

# Check for tkinter
if ! "$PYTHON" -c "import tkinter" &> /dev/null; then
  echo "tkinter not found. Installing..."
  sudo dnf install -y "$PYTHON-tkinter"
fi

echo "Ensuring $PYTHON-virtualenv is insalled"
sudo dnf install -y "$PYTHON-virtualenv"
