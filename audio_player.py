from contextlib import suppress
import os
import sys
starting_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.environ['PYTHON_VLC_LIB_PATH'] = f'{starting_dir}\\vlc\\libvlc.dll'
import vlc
import math


class AudioPlayer:
    __slots__ = '__is_paused', 'vlc_instance', 'player'

    @staticmethod
    def percent_to_db(percent):
        with suppress(ValueError): return round(20 * math.log(percent, 10), 3)
        return -100

    def __init__(self):
        self.vlc_instance = vlc.Instance()
        self.player: vlc.MediaPlayer = self.vlc_instance.media_player_new()
        self.__is_paused = False

    def play(self, file_path, start_playing=True, volume=None, start_from=0):
        """
        :param file_path: str
        :param start_playing: bool
        :param volume: float[0, 1]
        :param start_from: time to start from in seconds
        """
        m = self.vlc_instance.media_new(file_path)  # Path
        self.player.set_media(m)
        self.set_pos(start_from)
        self.player.play()
        if not start_playing: self.player.pause()
        # self.set_pos(start_from)
        if volume is not None: self.set_volume(volume)

    def load(self, file_path):
        self.play(file_path, start_playing=False)

    def pause(self):
        if not self.__is_paused and self.is_playing():
            self.__is_paused = True
            self.player.pause()
            while self.player.is_playing(): pass

    def resume(self):
        """
        resumes playback
        Also used to start playing audio after load was used
        """
        if self.__is_paused:
            self.__is_paused = False
            self.player.audio_set_volume(self.player.audio_get_volume())
            self.player.pause()
            while not self.player.is_playing(): pass

    def stop(self):
        """ Stop the playback of any audio """
        if self.player.is_playing() or self.__is_paused:
            position = self.player.get_time()
            self.player.stop()
            self.__is_paused = False
            return position
        return None

    def set_volume(self, volume=1.0):
        """
        Sets the output volume and not the program volume
        :param volume: float[0, 1]
        Capped at 1 to prevent distortion
        """
        assert 0 <= volume <= 1
        db_change = (1 - volume) * 55 if volume else 100
        self.player.audio_set_volume(int(volume * 100))

    def get_volume(self):
        """
        get the volume of the output
        :return float [0, 1]
        """
        return self.player.audio_get_volume() / 100

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

    def get_length(self):
        return self.player.get_length()

    def is_playing(self):
        return self.player.is_playing() or self.is_paused

    def is_paused(self):
        return self.__is_paused

    def is_idle(self):
        """ Whether audio player is in stopped state: audio was never loaded, finished/stopped playing """
        return not self.is_busy()

    def is_busy(self):
        """ Returns whether player is playing or is paused """
        return self.__is_paused or self.player.is_playing()

    def toggle_mute(self):
        self.player.audio_toggle_mute()

    def mute(self):
        self.player.audio_set_mute(True)

    def unmute(self):
        self.player.audio_set_mute(False)
