#!/usr/bin/env bash
PYTHON=$1

echo "Installing SUSE system dependencies"
sudo zypper install -y "$PYTHON" "$PYTHON-devel" "$PYTHON-tk" "$PYTHON-virtualenv" python3-pyaudio
