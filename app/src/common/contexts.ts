import { createContext } from 'react';

export type PlaybackStatus = 'NOT_PLAYING' | 'PLAYING' | 'PAUSED' | 'NOT_RUNNING';

export interface PlayerState {
  status: PlaybackStatus;
  volume: number;
  lang: string;
  title: string;
  artist: string;
  album: string;
  gui_open: boolean;
  track_position: number;
  track_length: number;
  queue_length: number;
  queue: string[];
	queue_position: number;
  file_name: string;
}

export const PlayerStateContext = createContext<PlayerState | null>(null);
