# this images allows building music caster into a folder that can be run
#
FROM fedora:latest
ENV PY=python3.12
ENV PIP_ROOT_USER_ACTION=ignore
# install required packages
RUN dnf upgrade -y && dnf install -y \
    $PY $PY-devel $PY-virtualenv python3-devel python3-tkinter python3-pyaudio \
    dnf-plugins-core libappindicator-gtk3 binutils
# install some dependencies here to reduce the dependencies installed at run time
COPY requirements.txt build_files/ music-caster/
RUN $PY -m pip install --upgrade pip && $PY -m pip install pyaudio
RUN cd music-caster && $PY -m pip install -i https://PySimpleGUI.net/install --upgrade -r requirements.txt
RUN rm -rf ./music-caster
# when running this image, need to mount the work directory to /var/music-caster
CMD if [ ! -d /var/music-caster ] ; then git clone https://github.com/elibroftw/music-caster/ /var/music-caster ; fi && cd /var/music-caster && \
    $PY -m pip install --upgrade pip && \
    $PY -m pip install -i https://PySimpleGUI.net/install --upgrade -r requirements.txt && \
    $PY -m pip install -i https://PySimpleGUI.net/install -r requirements-dev.txt && \
    $PY -O -m PyInstaller build_files/onedir.spec && \
    echo "done! check your dist folder"
    # TODO: create AppImage from dist/Music Caster OneDir
