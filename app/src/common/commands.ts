import { invoke } from '@tauri-apps/api/core';

export type PlaybackStatus = 'NOT_PLAYING' | 'PLAYING' | 'PAUSED' | 'NOT_RUNNING';
/** repeat cycles off -> all -> one */
export type RepeatMode = 'off' | 'all' | 'one';
export interface PlayerState {
	status: PlaybackStatus;
	volume: number;
	lang: string;
	title: string;
	artist: string;
	album: string;
	track_position: number;
	track_length: number;
	queue_length: number;
	/** [uri, formatted title, length in seconds (null if unknown), tagged track number (null if untagged), album track total (null if untagged)] */
	queue: [string, string, number | null, string | null, string | null][];
	queue_position: number;
	file_name: string;
	shuffle: boolean;
	repeat: RepeatMode;
}

interface ActionResponse {
	message: string;
}

export interface WebUrl {
	url: string;
	ip: string;
	port: number;
}

interface PlayUrisOptions {
	uris?: string[];
	uri?: string;
	queue?: boolean;
	playNext?: boolean;
	device?: string;
}

export enum PlayAction {
	PLAY = 'play',
	PLAY_NEXT = 'playNext',
	QUEUE = 'queue'
}

export type ModifyQueueAction = 'next_up' | 'remove' | 'clear';

/** daemon settings that are plain on/off toggles; see TOGGLEABLE_SETTINGS in src/meta.py */
export type BooleanSetting =
	| 'populate_queue_startup'
	| 'smart_queue'
	| 'reversed_play_next'
	| 'show_queue_index'
	| 'queue_library'
	| 'persistent_queue';

/**
 * the daemon's settings.json. Only the settings the UI reads are typed; the rest
 * come through untyped so new settings need no change here
 */
export type DaemonSettings = Partial<Record<BooleanSetting, boolean>> & Record<string, unknown>;

/** keep in sync with AUDIO_FILE_TYPES in src/meta.py */
export const AUDIO_EXTENSIONS = [
	'mp3', 'mp4', 'mpeg', 'm4a', 'flac', 'aac', 'ogg', 'opus', 'wma', 'wav', 'aiff', 'm3u', 'm3u8'
];

export interface Track {
	file_path: string;
	title?: string;
	artist?: string;
	album?: string;
	genre?: string | null;
	length: number;
	explicit: boolean;
	track_number: number;
	sort_key: string;
	time_modified: number;
	bpm?: number;
	bitrate?: number;
}

/** tag values served by the daemon's GET/POST /metadata/ endpoints */
export interface TrackMetadata {
	title: string;
	artist: string;
	album: string;
	genre: string;
	track_number: string | null;
	track_total: string | null;
	explicit: boolean;
	length: number | null;
	/** embedded artwork as base64, null when the file has none */
	art: string | null;
	mime: string | null;
}

/** keys are snake_case to match the Rust command's SetMetadataOptions struct */
export interface SetMetadataOptions {
	title: string;
	artist: string;
	album: string;
	genre: string;
	/** 'X' or 'X/Y' where Y is the album's track total */
	track_number: string;
	explicit: boolean;
	art?: string;
	mime?: string;
	remove_art?: boolean;
}

export interface Artwork {
	art: string;
	mime: string;
}

class MusicCasterAPI {
	private apiKey?: string;

	constructor(apiKey?: string) {
		this.apiKey = apiKey;
	}

	async isRunning(): Promise<boolean> {
		return invoke<boolean>('api_is_running');
	}

	async activate(): Promise<ActionResponse> {
		return invoke<ActionResponse>('api_activate');
	}

	async getDevices(friendly: boolean = false): Promise<Record<string, string> | string[]> {
		return invoke('api_get_devices', { friendly });
	}

	async changeDevice(deviceId: string): Promise<string> {
		return invoke<string>('api_change_device', { deviceId });
	}

	async play(): Promise<ActionResponse> {
		return invoke<ActionResponse>('api_play');
	}

	async pause(): Promise<ActionResponse> {
		return invoke<ActionResponse>('api_pause');
	}

	async next(times: number = 1, ignoreTimestamps: boolean = false): Promise<ActionResponse> {
		return invoke<ActionResponse>('api_next', { times, ignoreTimestamps });
	}

	async prev(times: number = 1, ignoreTimestamps: boolean = false): Promise<ActionResponse> {
		return invoke<ActionResponse>('api_prev', { times, ignoreTimestamps });
	}

	async seek(position: number): Promise<ActionResponse> {
		return invoke<ActionResponse>('api_seek', { position });
	}

	async toggleRepeat(): Promise<ActionResponse> {
		return invoke<ActionResponse>('api_toggle_repeat');
	}

	async toggleShuffle(): Promise<ActionResponse> {
		return invoke<ActionResponse>('api_toggle_shuffle');
	}

	async getState(): Promise<PlayerState> {
		return invoke<PlayerState>('api_get_state');
	}

	async invokePlayUris(options: PlayUrisOptions): Promise<PlayerState> {
		return invoke<PlayerState>('api_play_uris', { options });
	}

	async playUri(uri: string, action: PlayAction): Promise<PlayerState> {
		return await this.invokePlayUris({
			uri, playNext: action === PlayAction.PLAY_NEXT, queue: action === PlayAction.QUEUE,
		})
	}

	async modifyQueue(indices: number[], action: ModifyQueueAction): Promise<void> {
		return invoke<void>('api_modify_queue', { indices, action });
	}

	/** empties the queue and stops playback */
	async clearQueue(): Promise<void> {
		return this.modifyQueue([], 'clear');
	}

	/** tag values for one file, read by the daemon with mutagen */
	async getMetadata(filePath: string): Promise<TrackMetadata> {
		return invoke<TrackMetadata>('api_get_metadata', { filePath });
	}

	async setMetadata(filePath: string, options: SetMetadataOptions): Promise<TrackMetadata> {
		// the Rust SetMetadataOptions struct carries the file path as `path`
		return invoke<TrackMetadata>('api_set_metadata', { options: { path: filePath, ...options } });
	}

	/** Spotify artwork search for the given title/artist */
	async searchArtwork(title: string, artist: string): Promise<Artwork> {
		return invoke<Artwork>('api_search_artwork', { title, artist });
	}

	/** read a locally picked image file as base64 artwork */
	async readArtwork(filePath: string): Promise<Artwork> {
		return invoke<Artwork>('api_read_artwork', { filePath });
	}

	async exit(): Promise<PlayerState> {
		return invoke<PlayerState>('api_exit');
	}

	async changeSetting(settingName: string, value: any): Promise<string> {
		return invoke<string>('api_change_setting', { settingName, value });
	}

	/** current daemon settings, read from settings.json (secrets stripped) */
	async getSettings(): Promise<DaemonSettings> {
		return invoke<DaemonSettings>('api_get_settings');
	}

	async setVolume(volume: number): Promise<string> {
		return invoke<string>('api_set_volume', { volume });
	}

	async refreshDevices(): Promise<string> {
		return invoke<string>('api_refresh_devices');
	}

	async rescanLibrary(): Promise<string> {
		return invoke<string>('api_rescan_library');
	}

	async setTimer(value: string): Promise<string> {
		return invoke<string>('api_set_timer', { value });
	}

	async getTimer(): Promise<string> {
		return invoke<string>('api_get_timer');
	}

	async cancelTimer(): Promise<string> {
		return invoke<string>('api_cancel_timer');
	}

	getFileUrl(filePath: string, thumbnailOnly: boolean = false): string {
		return invoke<string>('api_get_file_url', {
			filePath,
			thumbnailOnly,
			apiKey: this.apiKey || null
		}) as any;
	}

	getStreamUrl(filePath: string): string {
		return invoke<string>('api_get_stream_url', {
			filePath,
			apiKey: this.apiKey || null
		}) as any;
	}

	async getAlbumArtUrl(): Promise<string> {
		return invoke<string>('api_get_album_art_url');
	}

	/** LAN URL of the daemon's web GUI; rejects when no LAN address is available */
	async getWebUrl(): Promise<WebUrl> {
		return invoke<WebUrl>('api_get_web_url');
	}
}

export default MusicCasterAPI;
export type { ActionResponse, PlayUrisOptions };
