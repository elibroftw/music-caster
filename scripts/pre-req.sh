#!/usr/bin/env bash
# Define script locations (change paths if needed)
DEBIAN_INSTALL="./scripts/debian-install.sh"
ARCH_INSTALL="./scripts/arch-install.sh"
FEDORA_INSTALL="./scripts/fedora-install.sh"
SUSE_INSTALL="./scripts/suse-install.sh"
# Check for /etc/os-release (preferred method)
if [ -f /etc/os-release ]; then
  . /etc/os-release
  case "$ID" in
    debian|ubuntu|mint|linuxmint)
      if [ -f "$DEBIAN_INSTALL" ]; then
        "$DEBIAN_INSTALL" "$1"
        exit 0
      fi
      echo "Error: $DEBIAN_INSTALL not found!"
      exit 1
      ;;
    arch)
      if [ -f "$ARCH_INSTALL" ]; then
        "$ARCH_INSTALL" "$1"
        exit 0
      fi
      echo "Error: $ARCH_INSTALL not found!"
      exit 1
      ;;
    fedora)
      if [ -f "$FEDORA_INSTALL" ]; then
        "$FEDORA_INSTALL" "$1"
        exit 0
      fi
      echo "Error: $FEDORA_INSTALL not found!"
      exit 1
      ;;
    opensuse|sles)
      if [ -f "$SUSE_INSTALL" ]; then
        "$SUSE_INSTALL" "$1"
        exit 0
      fi
      echo "Error: $SUSE_INSTALL not found!"
      exit 1
      ;;
  esac
fi

# No match, display error
echo "Error: Unsupported distribution. Only Debian, Arch, Fedora, and SUSE are supported."
exit 1
