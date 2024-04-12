#!/usr/bin/env bash
echo "debian-based distro detected"
PYTHON=$1
# sudo apt install -y software-properties-common
# Check for python3.12
if ! $PYTHON --version &> /dev/null; then
  echo "Python 3.12 not found. Installing..."
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt update
  sudo apt install -y python3.12
fi

echo "Installing system dependencies"
sudo apt update
sudo apt install -y python3-pip "${PYTHON}-venv" "${PYTHON}-tk" python3-pyaudio "${PYTHON}-venv"
