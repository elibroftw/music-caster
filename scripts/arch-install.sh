#!/usr/bin/env bash
PYTHON=$1

echo "Installing Arch system dependencies"
sudo pacman -Sy --noconfirm python-pip $PYTHON "$PYTHON-dev" "$PYTHON-virtualenv" "$PYTHON-tk" python3-pyaudio
