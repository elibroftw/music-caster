"""
AudioPlayer v2.2.2
Author: Elijah Lopez
Make sure VLC .dll files are located in ./vlc/
"""

import os
import sys
starting_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.environ['PYTHON_VLC_LIB_PATH'] = f'{starting_dir}\\vlc\\libvlc.dll'
import vlc
import math


class AudioPlayer:
    __slots__ = 'vlc_instance', 'player'

    @staticmethod
    def percent_to_db_percent(percent: float):
        """
        :param percent: float [0, 1]
        """
        try:
            return round(20 * math.log(percent * 100, 10), 3) / 40
        except ValueError:
            return 0

    @staticmethod
    def db_percent_to_percent(db: float):
        """ :param db: float [0, 40]"""
        if db == 0: return 0
        return round((10 ** (2 * db)) / 100, 2)

    def __init__(self):
        self.vlc_instance = vlc.Instance()
        self.player: vlc.MediaPlayer = self.vlc_instance.media_player_new()

    def has_media(self):
        return self.player.get_media() is not None

    def is_busy(self):
        """ Returns whether player is playing or is paused """
        return self.has_media()

    def play(self, file_path, start_playing=True, volume=None, start_from=0):
        """
        :param file_path: str
        :param start_playing: bool
        :param volume: float[0, 1]
        :param start_from: time to start from in seconds
        """
        m = self.vlc_instance.media_new(file_path)  # Path
        self.player.set_media(m)
        self.player.play()
        if not start_playing: self.player.pause()
        self.set_pos(start_from)
        if volume is not None: self.set_volume(volume)

    def load(self, file_path):
        self.play(file_path, start_playing=False)

    def pause(self):
        if self.is_playing():
            self.player.pause()
            while self.player.is_playing(): pass
            return True
        return False

    def resume(self):
        """
        Resumes playback if paused and has media
        Also used to start playing audio after load was used
        """
        if not self.is_playing() and self.has_media():
            self.player.audio_set_volume(self.player.audio_get_volume())
            self.player.pause()
            while not self.player.is_playing(): pass
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

    def set_volume(self, volume):
        """
        Sets the output volume and not the program volume
        :param volume: float[0, 1]
        Capped at 1 to prevent distortion
        """
        self.player.audio_set_volume(int(self.percent_to_db_percent(volume) * 100))

    def get_volume(self):
        """
        get the volume of the output
        :return float [0, 1]
        """
        return self.db_percent_to_percent(self.player.audio_get_volume() / 5 * 2)

    def set_pos(self, position, units='seconds'):
        """position is in seconds from start"""
        units = units.lower()
        assert units in {'seconds', 'milliseconds'}
        if units == 'seconds': position *= 1000
        self.player.set_time(int(position))

    def get_pos(self, units='seconds'):
        """
        returns the position of the audio playing
        position meaning the time in seconds from the start of the audio data/file
        """
        units = units.lower()
        assert units in {'seconds', 'milliseconds'}
        return self.player.get_time() / (1000 if units == 'seconds' else 1)

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

    def get_length(self):
        return self.player.get_length()

    def get_sample_rate(self):
        return self.player.get_rate()
