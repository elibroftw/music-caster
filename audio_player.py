from contextlib import suppress
import math
import numpy as np
import pyaudio
from pydub import AudioSegment
from pydub.utils import make_chunks
import soundfile as sf
import threading
import time
from helpers import timing


class AudioPlayerError(Exception): pass


class NoDeviceFoundError(AudioPlayerError): pass


class PlayingThreadExistsError(AudioPlayerError): pass


class FileNotSupportedError(AudioPlayerError): pass


class AudioPlayer:
    # FUTURE: get_output_devices()
    # FUTURE: select_output_device(new_device)
    # FUTURE: play_url(url)
    # TODO: multiprocessing
    __slots__ = ['__audio_data', '__current_pos', '__db_change', '__device_index', '__length', '__loads',
                 '__loading_threads', '__player', '__playing_thread', '__playing', '__sample_rate', '__sound',
                 '__stream', '__volume']
    __CHUNK_SIZE = 0.025  # 25 milliseconds is 0.05 seconds
    __SAMPLE_FORMATS = {8: pyaudio.paInt8}

    @staticmethod
    def percent_to_db(percent):
        with suppress(ValueError): return round(20 * math.log(percent, 10), 3)
        return -100

    def __init__(self):
        self.__player = pyaudio.PyAudio()
        default_index = -1
        for i in range(self.__player.get_device_count()):
            device = self.__player.get_device_info_by_index(i)
            # get any output device, preferably Microsoft Sound Mapper
            if device['maxOutputChannels']:
                if device['name'] == 'Microsoft Sound Mapper - Ouput' or default_index == -1:
                    default_index = i
                if device['name'] == 'Microsoft Sound Mapper - Output':
                    break
        if default_index == -1:
            raise NoDeviceFoundError('No output device found')
        self.__audio_data = None
        self.__current_pos = 0.0
        self.__db_change = 0.0
        self.__device_index = default_index
        self.__length = None
        self.__playing_thread = None
        self.__playing = False
        self.__sample_rate = None
        self.__sound = None
        self.__stream = None
        self.__volume = 1.0
        self.__loading_threads = []
        self.__loads = 0

    def __play(self, start_from=0.0):
        seconds_left = self.__length - start_from
        self.__current_pos = start_from
        self.__playing = True
        self.__stream.start_stream()
        if self.__sound is not None:
            multiplier = round(len(self.__sound) / self.__length)
            start_chunk = round(start_from * multiplier)
            end_chunk = round((start_from + self.__length) * multiplier)
            valid_chunks = self.__sound[start_chunk:end_chunk]
            if seconds_left > 0.01:  # 0.01 is the threshold
                for chunks in make_chunks(valid_chunks, round(self.__CHUNK_SIZE * len(valid_chunks) / seconds_left)):
                    if not self.__playing: break
                    try:
                        chunks -= self.__db_change
                        # start = time.time()
                        self.__stream.write(chunks.raw_data)
                        # print(time.time() - start)
                        self.__current_pos += self.__CHUNK_SIZE  # update audio position
                    except AttributeError: break
        else:
            start_chunk = round(start_from * self.__sample_rate)
            end_chunk = round((start_from + self.__length) * self.__sample_rate)
            valid_chunks = self.__audio_data[start_chunk:end_chunk]
            if seconds_left > 0.01:
                for chunks in make_chunks(valid_chunks, round(self.__CHUNK_SIZE * len(valid_chunks) / seconds_left)):
                    if not self.__playing: break
                    try:
                        chunks = np.fromstring(chunks, np.float32) * self.__volume
                        self.__stream.write(chunks.tostring())
                        self.__current_pos += self.__CHUNK_SIZE
                    except AttributeError: break
        with suppress(AttributeError):
            if self.__current_pos >= self.__length:  # finished playing audio
                self.__playing = False
                self.__stream.close()
                self.__stream = None
                self.__current_pos = self.__length
        self.__playing_thread = None

    def __start_play_thread(self, start_from):
        # DO NOT CALL WITHOUT MAKING SURE THE OLD THREAD IS DEAD
        if self.__playing_thread is None:
            self.__playing_thread = threading.Thread(target=self.__play, kwargs={'start_from': start_from}, daemon=True)
        else:
            raise PlayingThreadExistsError()
        self.__playing_thread.start()

    def set_volume(self, volume=1.0):
        """
        Sets the output volume and not the program volume
        :param volume: float[0, 1]
        Capped at 1 to prevent distortion
        """
        assert 0 <= volume <= 1.1
        self.__volume = volume
        self.__db_change = (1 - self.__volume) * 55 if self.__volume else 100

    def get_volume(self):
        """ get the volume of the output """
        return self.__volume

    @timing
    def __load(self, filename, start_playing=True, start_from=0.0, volume: float = None):
        """
                :param filename:
                :param start_playing:
                :param volume:
                :param start_from: (float) seconds ahead of start
                """
        self.stop()
        start = time.time()
        try:
            sound_file = sf.SoundFile(filename)
            if sound_file.format == 'WAV': raise RuntimeError
            audio_array = sound_file.read()
            self.__sound = None
            self.__sample_rate = sound_file.samplerate
            self.__length = len(sound_file) / self.__sample_rate
            sample_format = pyaudio.paFloat32
            self.__audio_data = audio_array.astype(np.float32)
        except RuntimeError:
            self.__sound = AudioSegment.from_file(filename)
            self.__sample_rate = self.__sound.frame_rate
            self.__length = self.__sound.duration_seconds
            self.__sound = self.__sound.set_sample_width(2)
            bits = self.__sound.sample_width * self.__sound.channels * self.__sound.frame_width
            sample_format = self.__SAMPLE_FORMATS.get(bits, pyaudio.paInt16)
            print(time.time() - start)
        try:
            self.__stream = self.__player.open(format=sample_format,
                                               channels=2,
                                               rate=self.__sample_rate,
                                               frames_per_buffer=1024,
                                               output=True,
                                               output_device_index=self.__device_index)
        except NameError:
            raise FileNotSupportedError('Audio Format not supported (yet) / AudioData is None')
        with suppress(IndexError):
            # IndexError means that call to __load was made
            self.__loading_threads.pop(0)
            if self.__loading_threads:
                latest_thread = self.__loading_threads.pop()
                self.__loading_threads = [latest_thread]
                latest_thread.start()
            else:
                if start_playing:
                    self.__start_play_thread(start_from)
                # else:
                #     self.__stream.stop_stream()
                if volume is not None: self.set_volume(volume)

    def play(self, filename, start_playing=True, start_from=0.0, volume: float = None):
        self.__current_pos = start_from
        loading_thread = threading.Thread(target=self.__load, args=[filename], kwargs={'start_playing': start_playing,
                                          'start_from': start_from, 'volume': volume})
        self.__loads += 1
        self.__loading_threads.append(loading_thread)
        if self.__loading_threads[0] == loading_thread: loading_thread.start()

    def stop(self):
        """ Stop the playback of any audio """
        if self.__stream is not None:
            self.__playing = False  # tells _play_data thread to stop
            with suppress(AttributeError): self.__playing_thread.join()
            self.__stream.close()
            self.__stream = None
            return self.__current_pos
        return None

    def pause(self):
        self.__playing = False
        with suppress(AttributeError): self.__playing_thread.join()

    def resume(self):
        """
        resumes playback
        Is also used to start playing after load was called
        """
        if self.is_paused(): self.__start_play_thread(self.__current_pos)

    def set_pos(self, position):
        """position is in seconds from start"""
        if self.__playing:
            self.__playing = False
            with suppress(AttributeError): self.__playing_thread.join()
            self.__start_play_thread(position)
        else:
            self.__current_pos = position

    def get_pos(self):
        """
        returns the position of the audio playing
        position meaning the time in seconds from the start of the audio data/file
        """
        return self.__current_pos

    def get_length(self):
        return self.__length

    def get_sample_rate(self):
        return self.__sample_rate

    def is_playing(self):
        return self.__playing

    def is_paused(self):
        return not self.__playing and self.__stream is not None

    def is_idle(self):
        """ Whether audio player is in stopped state: audio was never loaded, finished/stopped playing """
        return not self.__playing and self.__stream is None


def test_set_pos(ap: AudioPlayer):
    for pos in (0, 8):
        ap.set_pos(pos)
        print(f'SET POSITION TO {pos} seconds')
        time.sleep(3)
    for pos in (0, 10):
        ap.pause()
        print('PAUSED')
        ap.set_pos(pos)
        print(f'SET POSITION TO {pos} seconds')
        time.sleep(1)
        ap.resume()
        print('RESUMED')
        time.sleep(3)


def test_set_volume(ap: AudioPlayer):
    for vol in (0.5, 0.1, 0.8):
        ap.set_volume(vol)
        print(f'SET VOLUME TO {vol * 100}%')
        time.sleep(3)


def test_interrupt_plays(ap: AudioPlayer, files):
    for _format in ('FLAC', 'MP4', 'WAV', 'OPUS'):
        ap.play(files[_format], start_from=5)
        print(f'INTERRUPT PLAY {_format} @ 5')
        time.sleep(2)


def test_no_effects(ap: AudioPlayer, file):
    print('DOING TASKS THAT SHOULD NOT DO ANYTHING')
    ap.resume()  # do nothing
    time.sleep(1)
    ap.__load(file)  # do nothing
    time.sleep(1)
    ap.stop()
    ap.set_pos(0)
    time.sleep(1)
    ap.resume()  # do nothing
    time.sleep(1)


def test_pause_resume_stop(ap: AudioPlayer):
    ap.pause()
    assert ap.is_paused()
    print('PAUSED')
    time.sleep(2)
    ap.resume()
    assert ap.is_playing()
    print('RESUMED')
    time.sleep(3)
    ap.stop()
    assert ap.is_idle()
    print('STOPPED')
    time.sleep(1)


def test_audio_player():
    music_player = AudioPlayer()
    tests = ((1, 0), (.5, -6), (.2, -14), (.1, -20))
    THRESHOLD = 0.05  # not a percentage
    for sample_input, expected_result in tests:
        result = music_player.percent_to_db(sample_input)
        try:
            assert expected_result - THRESHOLD <= result <= expected_result + THRESHOLD
        except AssertionError:
            print(
                f'TEST FAILED for percent_to_db({sample_input}): {result} != {expected_result}')
    music_player.set_volume(0.9)
    files = {
        'MP3':  'test_files/Adam Szabo, Johan Vilborg, Johnny Norberg - Knock Me Out.mp3',
        'FLAC': 'test_files/Sample_BeeMoved_96kHz24bit.flac',
        'WAV':  'test_files/Kevin MacLeod - Impact Moderator.wav',
        'M4A':  'test_files/Sample_BeeMoved_48kHz16bit.m4a',
        'AAC':  'test_files/ff-16b-2c-44100hz.aac',
        'AIFF': 'test_files/ff-16b-2c-44100hz.aiff',
        'MP4':  'test_files/ff-16b-2c-44100hz.mp4',
        'OGG':  'test_files/ff-16b-2c-44100hz.ogg',
        'OPUS': 'test_files/ff-16b-2c-44100hz.opus',
        'WMA':  'test_files/ff-16b-2c-44100hz.wma'
    }
    for file in files.values():
        print(f'TESTING {file}')
        music_player.play(file, start_from=20)
        print('STARTED PLAYING @ 20 seconds')
        time.sleep(5)
        test_pause_resume_stop(music_player)
        test_no_effects(music_player, file)
        music_player.play(file)
        print('STARTED PLAYING @ 0')
        time.sleep(3)
        test_set_volume(music_player)
        test_set_pos(music_player)
        test_interrupt_plays(music_player, files)
        music_player.stop()
        print('STOPPED')


if __name__ == '__main__': test_audio_player()
