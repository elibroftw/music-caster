#!/usr/bin/env bash
PYTHON=$1

echo "Installing Fedora system dependencies"
sudo dnf install -y "$PYTHON" python-pip "$PYTHON-devel" "$PYTHON-virtualenv" "$PYTHON-tkinter" python3-pyaudio
