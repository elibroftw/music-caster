# WIP: Build an image capable of producing music-caster App Images# WIP: Build an image capable of producing music-caster App Images
# Base image: Fedora 37
FROM fedora:37

# Install required tools
RUN dnf update -y && \
    dnf install -y python3.12 python3.12-devel python3.12-virtualenv dnf-plugins-core libappindicator-gtk3 && \
    dnf config-manager --set-enabled powertools && \
    dnf install -y python3-tkinter

# Install pip for Python 3.12 (as it's not included by default)
RUN curl https://bootstrap.pypa.io/get-pip.py | python3.12

CMD cd /var/music-caster && \
    python3.12 -m pip install --upgrade -r requirements.txt -r requirements-dev.txt && \
    python3.12 -O -m PyInstaller --onefile build_files/onedir.spec
