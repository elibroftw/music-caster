"""
AudioPlayer v2.3.7
Author: Elijah Lopez
Ensure VLC shared library files (*.dll, *.so) are located in "vlc_lib/"
"""
import math
import os
import platform
import sys
import time
from enum import IntEnum
from pathlib import Path

IS_FROZEN = getattr(sys, 'frozen', False)  # pyinstaller generated executable
app_path = os.path.dirname(sys.executable if IS_FROZEN else  __file__)
vlc_ext = 'dll' if platform.system() == 'Windows' else 'so'
if platform.system() != 'Windows':
    os.environ['PYTHON_VLC_MODULE_PATH'] = f'{app_path}/vlc_lib/plugins'
vlc_lib_path = Path(f'{app_path}/vlc_lib/libvlc.{vlc_ext}')
os.environ['PYTHON_VLC_LIB_PATH'] = str(vlc_lib_path)
cwd = os.getcwd()
if platform.system() == 'Linux':
    os.chdir(f'{app_path}/vlc_lib')
import vlc

os.chdir(cwd)


class AudioPlayerUnit(IntEnum):
    MILLI_SECOND = 1
    SECOND = 1000


class AudioPlayer:
    __slots__ = 'vlc_instance', 'player', 'is_url'

    def __init__(self, skip_vlc=False):
        if not skip_vlc:
            self.vlc_instance = vlc.Instance()
            self.player: vlc.MediaPlayer = self.vlc_instance.media_player_new()
        self.is_url = False

    def has_media(self):
        return self.player.get_media() is not None

    def is_busy(self):
        """ Returns whether player is playing or is paused """
        return self.has_media()

    def play(self, media_path, start_playing=True, volume=None, start_from=0):
        """
        :param media_path: str
        :param start_playing: bool
        :param volume: float[0, 1]
        :param start_from: time to start from in seconds
        """
        self.is_url = media_path.startswith('http')
        self.player.set_mrl(media_path)
        self.player.play()
        if volume is not None: self.set_volume(volume)
        block_until = time.time() + 1
        while not self.player.is_playing() and time.time() < block_until: pass
        self.set_pos(start_from)
        if not start_playing: self.pause()

    def load(self, file_path):
        self.play(file_path, start_playing=False)

    def pause(self):
        if self.is_playing():
            self.player.pause()
            block_until = time.time() + 1
            while self.player.is_playing() and time.time() < block_until: pass
            return True
        return False

    def resume(self):
        """
        Resumes playback if paused and has media
        Also used to start playing audio after load was used
        """
        if not self.is_playing() and self.has_media():
            if self.player.get_length() - self.player.get_time() > 0.5:
                self.player.audio_set_volume(self.player.audio_get_volume())
                self.player.pause()
                block_until = time.time() + 1
                while not self.player.is_playing() and time.time() < block_until: pass
                return True
        return False

    def stop(self):
        """ Stop the playback of any audio and return the current position in seconds """
        if self.is_busy():
            position = self.player.get_time() / 1000
            self.player.stop()
            self.player.set_media(None)
            return position
        return 0

    @staticmethod
    def percent_to_db_percent(percent: float):
        """
        :param percent: float [0, 1]
        """
        try: return round(20 * math.log(percent * 100, 10), 3) / 40
        except ValueError: return 0

    @staticmethod
    def db_percent_to_percent(db: float):
        """ :param db: float [0, 40]"""
        return 0 if db == 0 else round((10 ** (2 * db)) / 120, 2)

    def set_volume(self, volume):
        """
        Sets the output volume and not the program volume
        :param volume: float[0, 1]
        """
        self.player.audio_set_volume(int(volume * 100))

    def get_volume(self):
        """
        get the volume of the output
        :return float [0, 1]
        """
        return self.player.audio_get_volume() / 100

    def set_pos(self, position, unit=AudioPlayerUnit.SECOND):
        """position is in seconds from start"""
        self.player.set_time(int(position * unit))

    def get_pos(self, unit=AudioPlayerUnit.SECOND):
        """
        returns the position of the audio playing
        position meaning the time in seconds from the start of the audio data/file
        """
        return self.player.get_time() / unit

    def is_playing(self):
        """ returns strictly whether the player is playing audio """
        return self.player.is_playing()

    def is_paused(self):
        return not self.is_playing() and self.has_media()

    def is_idle(self):
        """ Whether audio player is in stopped state: audio was never loaded, finished/stopped playing """
        return not self.is_busy()

    def toggle_mute(self):
        self.player.audio_toggle_mute()

    def mute(self):
        self.player.audio_set_mute(True)

    def unmute(self):
        self.player.audio_set_mute(False)

    def get_length(self, unit=AudioPlayerUnit.SECOND):
        return self.player.get_length() / unit

    def get_sample_rate(self):
        return self.player.get_rate()
