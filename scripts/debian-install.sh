#!/usr/bin/env bash
echo "debian-based distro detected"
PYTHON=$1
# sudo apt install -y software-properties-common
# Check for python3.14
if ! $PYTHON --version &> /dev/null; then
  echo "Python 3.14 not found. Installing..."
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt update
  sudo apt install -y python3.14
fi

echo "Installing system dependencies"
sudo apt update
sudo apt install -y python3-pip "${PYTHON}-venv" "${PYTHON}-tk" python3-pyaudio "${PYTHON}-venv"
