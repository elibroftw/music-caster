# running this image will build the music-caster source into an App Image
FROM fedora:latest
ENV PY=python3.12

# install required tools
RUN dnf update -y
RUN dnf install -y $PY $PY-devel $PY-virtualenv dnf-plugins-core libappindicator-gtk3 python3-devel python3-tkinter python3-pyaudio
# install some dependencies here to reduce the dependencies installed at run time
RUN $PY -m pip install --upgrade pip
RUN $PY -m pip install pyaudio
COPY . music-caster
RUN cd music-caster && $PY -m pip install --upgrade -r requirements.txt
RUN rm -rf ./music-caster
# when running this image, need to mount the work directory to /var/music-caster
CMD if [ ! -d /var/music-caster ] ; then git clone https://github.com/elibroftw/music-caster/ /var/music-caster ; fi && cd /var/music-caster && \
    $PY -m pip install --upgrade pip && \
    $PY -m pip install --upgrade -r requirements.txt -r requirements-dev.txt && \
    $PY -O -m PyInstaller --onefile build_files/onedir.spec
