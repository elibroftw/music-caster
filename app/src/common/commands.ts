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
	queue: [string, string][];
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

/** keep in sync with AUDIO_FILE_TYPES in src/meta.py */
export const AUDIO_EXTENSIONS = [
	'mp3', 'mp4', 'mpeg', 'm4a', 'flac', 'aac', 'ogg', 'opus', 'wma', 'wav', 'aiff', 'm3u', 'm3u8'
];

export interface Track {
	file_path: string;
	title?: string;
	artist?: string;
	album?: string;
	length: number;
	explicit: boolean;
	track_number: number;
	sort_key: string;
	time_modified: number;
	bpm?: number;
	bitrate?: number;
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

	async exit(): Promise<PlayerState> {
		return invoke<PlayerState>('api_exit');
	}

	async changeSetting(settingName: string, value: any): Promise<string> {
		return invoke<string>('api_change_setting', { settingName, value });
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
