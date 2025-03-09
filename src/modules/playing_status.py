import time


class PlayingStatus:
    __slots__ = (
        'NOT_PLAYING',
        'PLAYING',
        'PAUSED',
        'BUSY',
        'state',
        'timer',
        'track_position',
        'track_start',
        'track_end',
        'track_length',
        'device_is_local',
    )

    def __init__(self):
        self.NOT_PLAYING = 0
        self.PLAYING = 1
        self.PAUSED = 2
        self.BUSY = {self.PLAYING, self.PAUSED}
        self.state = self.NOT_PLAYING

    # @property
    def busy(self):
        return self.state in self.BUSY

    # @property
    def stopped(self):
        return self.state == self.NOT_PLAYING

    # @property
    def playing(self):
        return self.state == self.PLAYING

    # @property
    def paused(self):
        return self.state == self.PAUSED

    def stop(self):
        self.state = self.NOT_PLAYING

    def play(self, device_is_local: bool = True):
        self.state = self.PLAYING

    def play_uri(self, position, track_length, device_is_local: bool):
        self.track_position = position
        self.track_length = track_length
        self.device_is_local = device_is_local
        self.track_start = (time.monotonic() if device_is_local else time.time()) - position
        if self.track_length is not None:
            self.track_end = self.track_start + self.track_length

    def pause(self):
        self.state = self.PAUSED

    def play_system_audio(self):
        self.track_length = None
        self.track_position = 0
        self.track_start = time.monotonic()

    def __repr__(self):
        return ['NOT PLAYING', 'PLAYING', 'PAUSED'][self.state]

    def __eq__(self, other):
        if isinstance(other, int):
            return self.state == other
        if not isinstance(other, PlayingStatus):
            return str(other) == str(self)
        return other.state == self.state
