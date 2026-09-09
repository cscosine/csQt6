PACKAGES = """
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
libopenjp2-7
libxss-dev
libudev-dev
libwayland-dev
libnss3-dev
gperf
doxygen
python3-html5lib
"""


def get_apt_packages_list() -> list[str]:
    return PACKAGES.split()
