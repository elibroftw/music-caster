import { invoke } from '@tauri-apps/api/core';
import Queue from './../views/Queue';

export type PlaybackStatus = 'NOT_PLAYING' | 'PLAYING' | 'PAUSED' | 'NOT_RUNNING';
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
	queue: string[];
	queue_position: number;
	file_name: string;
}

interface ActionResponse {
	message: string;
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

	async exit(): Promise<PlayerState> {
		return invoke<PlayerState>('api_exit');
	}

	async changeSetting(settingName: string, value: any): Promise<string> {
		return invoke<string>('api_change_setting', { settingName, value });
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
}

export default MusicCasterAPI;
export type { ActionResponse, PlayUrisOptions };
