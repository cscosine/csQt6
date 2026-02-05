#!/bin/bash

# Install required packages for Linux (Debian/Ubuntu)


set -euo pipefail # enable strict mode

if [ -t 0 ]; then
    # if running in interactive terminal, ask for password if needed
    SUDO="sudo"
else
    # if running in a non-interactive terminal (e.g. in CI workflows), use sudo without password prompt (fail if password is needed)
    SUDO="sudo -n"
fi

packages=(
  libfontconfig1-dev
  libfreetype-dev
  libgtk-3-dev
  libx11-dev
  libx11-xcb-dev
  libxcb-cursor-dev
  libxcb-glx0-dev
  libxcb-icccm4-dev
  libxcb-image0-dev
  libxcb-keysyms1-dev
  libxcb-randr0-dev
  libxcb-render-util0-dev
  libxcb-shape0-dev
  libxcb-shm0-dev
  libxcb-sync-dev
  libxcb-util-dev
  libxcb-xfixes0-dev
  libxcb-xkb-dev
  libxcb1-dev
  libxext-dev
  libxfixes-dev
  libxi-dev
  libxkbcommon-dev
  libxkbcommon-x11-dev
  libxrender-dev
)

missing=()

for pkg in "${packages[@]}"; do
  dpkg -s "$pkg" &>/dev/null || missing+=("$pkg")
done

if [ ${#missing[@]} -ne 0 ]; then
  # clean apt cache to avoid issues with outdated package lists
  sudo rm -f /etc/apt/apt-mirrors.txt
  sudo apt clean
  sudo rm -rf /var/lib/apt/lists/*
  sudo apt update

  echo "Need to install missing packages: ${missing[*]}"
  sudo apt install -y "${missing[@]}"
else
  echo "All packages already installed."
fi
