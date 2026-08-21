import { Box, Paper, ScrollArea, Skeleton, Stack, Table } from '@mantine/core';
import { revealItemInDir } from '@tauri-apps/plugin-opener';
import Database from '@tauri-apps/plugin-sql';
import { useCallback, useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PlayAction, Track } from '../common/commands';
import { MusicCasterAPIContext, PlayerStateContext } from '../common/contexts';
import { formatTime } from '../common/utils';
import { ContextMenu, useContextMenu } from '../components/ContextMenu';
import MetadataEditorModal from '../components/MetadataEditorModal';
import TrackContextMenu from '../components/TrackContextMenu';
import classes from './MusicLibrary.module.css';

export default function MusicLibrary() {
	const { t } = useTranslation();
	const playerState = useContext(PlayerStateContext);
	const api = useContext(MusicCasterAPIContext)!;
	const [contextMenu, setMenuItem] = useContextMenu<Track>({ showOnClick: true });
	const [loading, setLoading] = useState(true);
	const [tracks, setTracks] = useState<Track[]>([]);
	const [sortColumn, setSortColumn] = useState<keyof Track>('artist');
	const [editingTrack, setEditingTrack] = useState<Track | null>(null);
	// bumped after a metadata save so the daemon-served thumbnails (sent with a
	// long max-age) aren't served from the browser cache
	const [artVersion, setArtVersion] = useState(0);

	const columns: Array<{ key: keyof Track; label: string }> = [
		{ key: 'artist', label: 'ARTIST' },
		{ key: 'album', label: 'ALBUM' },
		{ key: 'genre', label: 'GENRE' },
		{ key: 'title', label: 'TITLE' },
		{ key: 'track_number', label: 'TRACK' },
		{ key: 'length', label: 'LENGTH' },
		// { key: 'bpm', label: 'BPM' },
		// { key: 'bitrate', label: 'BITRATE' }
	];

	const loadTracks = useCallback(async () => {
		const db = await Database.load('sqlite:music_caster.db');
		const result = await db.select('SELECT * FROM file_metadata');
		setTracks(result as Track[]);
	}, []);

	useEffect(() => {
		(async () => {
			setLoading(true);
			await loadTracks();
			setLoading(false);
		})();
	}, [loadTracks]);

	// the daemon serves per-file cover thumbnails at /file/?path=...&thumbnail_only=true.
	// resolve one URL to learn the daemon's base (and api key suffix), then build every
	// row's URL from it locally instead of one IPC round-trip per track
	const [artUrlTemplate, setArtUrlTemplate] = useState<string | null>(null);
	useEffect(() => {
		(async () => {
			try {
				setArtUrlTemplate(await api.getFileUrl('DEFAULT_ART', true));
			} catch {
				// daemon not up yet: rows simply render without art
			}
		})();
	}, []);
	const artUrl = (filePath: string) => artUrlTemplate === null
		? undefined
		: `${artUrlTemplate.replace('path=DEFAULT_ART', `path=${encodeURIComponent(filePath)}`)}&v=${artVersion}`;

	const handleSort = (column: keyof Track) => {
		setSortColumn(column);
	};

	const handleEditMetadata = () => {
		if (contextMenu?.item) {
			setEditingTrack(contextMenu.item);
		}
	};

	const handleMetadataSaved = () => {
		loadTracks();
		setArtVersion(version => version + 1);
	};

	const handlePlay = () => {
		if (contextMenu?.item) {
			api.playUri(contextMenu.item.file_path, PlayAction.PLAY);
		}
	};

	const handlePlayNext = () => {
		if (contextMenu?.item) {
			api.playUri(contextMenu.item.file_path, PlayAction.PLAY_NEXT);
		}
	};

	const handleAddToQueue = () => {
		if (contextMenu?.item) {
			api.playUri(contextMenu.item.file_path, PlayAction.QUEUE);
		}
	};

	const handleShowFile = async () => {
		if (contextMenu?.item) {
			await revealItemInDir(contextMenu.item.file_path);
		}
	};

	const handleCopyUris = () => {
		if (contextMenu?.item) {
			navigator.clipboard.writeText(contextMenu.item.file_path);
		}
	};

	// file_name is the currently playing track's URI; normalize separators since
	// queue URIs may use backslashes while the library stores posix paths
	const normalizePath = (path: string) => path.replaceAll('\\', '/');
	const isPlayingTrack = !!contextMenu?.item && !!playerState?.file_name
		&& normalizePath(contextMenu.item.file_path) === normalizePath(playerState.file_name);

	if (loading && tracks.length === 0) {
		return (
			<Paper shadow='sm' p='md' style={{ height: 'calc(100vh - 140px)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
				<ScrollArea style={{ flex: 1 }}>
					<Stack gap='xs'>
						{[...Array(15)].map((_, index) => (
							<Skeleton key={index} height={80} />
						))}
					</Stack>
				</ScrollArea>
				<Box px='md' py='xs' style={{ borderTop: '1px solid #e0e0e0' }}>
					<Skeleton height={40} />
				</Box>
			</Paper>
		);
	}

	return (
		<>
			<MetadataEditorModal
				filePath={editingTrack?.file_path ?? null}
				onClose={() => setEditingTrack(null)}
				onSaved={handleMetadataSaved}
			/>

			<ContextMenu trigger={contextMenu} offsetLeft={88} offsetTop={-10}>
				<TrackContextMenu
					onEditMetadata={handleEditMetadata}
					onPlay={handlePlay}
					onPlayNext={isPlayingTrack ? undefined : handlePlayNext}
					onAddToQueue={handleAddToQueue}
					onShowFile={handleShowFile}
					onCopyUris={handleCopyUris}
				/>
			</ContextMenu>

			<Paper className={classes.tab} shadow='sm' p='md' display='flex'>
				<ScrollArea>
					<Table highlightOnHover>
						<Table.Thead>
							<Table.Tr>
								<Table.Th aria-label='Album art' />
								{columns.map((column) => (
									<Table.Th
										key={column.key}
										onClick={() => handleSort(column.key)}
										style={{ cursor: 'pointer' }}
									>
										{column.label} {sortColumn === column.key && '▼'}
									</Table.Th>
								))}
							</Table.Tr>
						</Table.Thead>
						<Table.Tbody>
							{tracks.map((track, index) => (
								<Table.Tr
									key={index}
									// onClick={() => setSelectedTrack(track)}
									// height on a tr behaves as a min-height: cells can still grow
									style={{ cursor: 'pointer', height: 80 }}
									onContextMenu={e => {
										e.preventDefault();
										setMenuItem({
											item: track,
											x: e.clientX,
											y: e.clientY,
										});
									}}
									onClick={e => {
										e.preventDefault();
										setMenuItem({
											item: track,
											x: e.clientX,
											y: e.clientY,
										});
									}}
								>
									<Table.Td style={{ width: 72 }}>
										{artUrl(track.file_path) && (
											// lazy so only the covers scrolled into view are fetched
											<img
												src={artUrl(track.file_path)}
												alt=''
												width={64}
												height={64}
												loading='lazy'
												style={{ objectFit: 'cover', borderRadius: 'var(--mantine-radius-sm)', display: 'block' }}
											/>
										)}
									</Table.Td>
									{columns.map((column) =>
										<TableCell key={column.key} track={track} columnKey={column.key} />
									)}
								</Table.Tr>

							))}
						</Table.Tbody>
					</Table>
				</ScrollArea>

			</Paper >
		</>
	);
}

function TableCell({ track, columnKey }: { track: Track, columnKey: keyof Track }) {
	if (columnKey === 'length') {
		return (
			<Table.Td key={columnKey}>
				{formatTime(track[columnKey])}
			</Table.Td>
		);
	}
	return (
		<Table.Td key={columnKey}>
			{track[columnKey]}
		</Table.Td>
	);
}
