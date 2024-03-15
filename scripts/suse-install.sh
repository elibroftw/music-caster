#!/usr/bin/env bash
echo "suse-based distro detected"
PYTHON=$1

# Check for $PYTHON
if ! zypper info "$PYTHON" &> /dev/null; then
  echo "$PYTHON not found. Installing..."
  sudo zypper install -y "$PYTHON" "$PYTHON-devel" "$PYTHON-virtualenv"
fi

# Check for pip
if ! $PYTHON -m pip --version &> /dev/null; then
  echo "pip not found. Installing..."
  sudo zypper install -y "$PYTHON-pip"
fi

# Check for tkinter
if ! "$PYTHON" -c "import tkinter" &> /dev/null; then
  echo "tkinter not found. Installing..."
  sudo zypper install -y "$PYTHON-tk"
fi

echo "Ensuring $PYTHON-virtualenv is insalled"
sudo zypper install -y "$PYTHON-virtualenv"
