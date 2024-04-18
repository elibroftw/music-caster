# https://learn.microsoft.com/en-us/windows/uwp/audio-video-camera/system-media-transport-controls
import enum
import platform
from datetime import timedelta
from typing import cast


class SystemMediaTransportControlsButton(enum.IntEnum):
    PLAY = 0
    PAUSE = 1
    STOP = 2
    RECORD = 3
    FAST_FORWARD = 4
    REWIND = 5
    NEXT = 6
    PREVIOUS = 7
    CHANNEL_UP = 8
    CHANNEL_DOWN = 9


class SystemMediaControls:
    def __init__(self, on_event):
        if platform.system() != 'Windows':
            return
        import winrt.windows.media as media
        import winrt.windows.media.playback as playback

        self.media_player = playback.MediaPlayer()
        self.system_media_transport_controls = cast(media.SystemMediaTransportControls, self.media_player.system_media_transport_controls)
        assert self.system_media_transport_controls is not None
        assert self.media_player.command_manager is not None
        self.media_player.command_manager.is_enabled = False
        self.system_media_transport_controls.is_play_enabled = True
        self.system_media_transport_controls.is_pause_enabled = True
        self.system_media_transport_controls.is_next_enabled = True
        self.system_media_transport_controls.is_previous_enabled = True
        self.on_event = on_event
        self.system_media_transport_controls.add_button_pressed(self._on_btn_press)
        # from winrt.windows.media.control import \
        #     GlobalSystemMediaTransportControlsSessionManager as MediaManager
        #  = media.SystemMediaTransportControls.get_for_current_view()
        # media.

    if platform.system() == 'Windows':
        import winrt.windows.media as media
        def _on_btn_press(self, sender, args: media.SystemMediaTransportControlsButtonPressedEventArgs):
            self.on_event(args.button)

    def set_playing(self):
        if platform.system() == 'Windows':
            import winrt.windows.media as media
            self.system_media_transport_controls.playback_status = media.MediaPlaybackStatus.PLAYING

    def set_paused(self):
        if platform.system() == 'Windows':
            import winrt.windows.media as media
            self.system_media_transport_controls.playback_status = media.MediaPlaybackStatus.PAUSED

    def set_stopped(self):
        self.set_closed()

    def set_closed(self):
        if platform.system() == 'Windows':
            import winrt.windows.media as media
            self.system_media_transport_controls.playback_status = media.MediaPlaybackStatus.CLOSED

    def set_metadata(self, title, artist, album, thumb_uri: str):
        if platform.system() == 'Windows':
            import winrt.windows.media as media
            from winrt.windows.foundation import Uri
            _updater = cast(media.SystemMediaTransportControlsDisplayUpdater, self.system_media_transport_controls.display_updater)
            _updater.type = media.MediaPlaybackType.MUSIC
            _updater.music_properties.artist = artist
            _updater.music_properties.title = title
            if album is not None:
                _updater.music_properties.album_title = album
            import winrt.windows.storage.streams as streams
            assert isinstance(thumb_uri, str)
            assert thumb_uri.count('://', 1)
            uri = Uri(thumb_uri)
            _updater.thumbnail = streams.RandomAccessStreamReference.create_from_uri(uri)
            _updater.update()

    def update_time(self):
        # TODO: add arguments
        if platform.system() == 'windows':
            import winrt.windows.media as media
            timeline_properties = media.SystemMediaTransportControlsTimelineProperties()
            timeline_properties.start_time = timedelta(0)
            timeline_properties.min_seek_time = timedelta(0)
            timeline_properties.position = timedelta(0)
            timeline_properties.max_seek_time = timedelta(0)
            timeline_properties.end_time = timedelta(100)
            self.system_media_transport_controls.update_timeline_properties(timeline_properties)

        pass
    #     self.dll.ITaskbarList4_SetProgressState(self.session, 0x0)
    #     self.dll.ITaskbarList4_SetProgressValue(self.session, 0, 100)
    #     self.dll.ITaskbarList4_SetThumbnailClip(self.session, thumbnail_path)
    #     self.dll.ITaskbarList4_SetThumbnailTooltip(self.session, title)
    #     self.dll.ITaskbarList4_SetTitle(self.session, title)
    #     self.dll.ITaskbarList4_SetDescription(self.session, f"{artist} - {album}")


if __name__ == '__main__':
    # Example usage
    session = SystemMediaControls(lambda event: print(event))
    # session.play()
    # session.set_metadata("My Song", "My Artist", "My Album", "path/to/thumbnail.jpg")
