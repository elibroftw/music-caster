import { createContext } from 'react';
import MusicCasterAPI, { PlayerState } from './commands';

export const PlayerStateContext = createContext<PlayerState | null>(null);
export const MusicCasterAPIContext = createContext<MusicCasterAPI | null>(null);
