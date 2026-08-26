import { Box, Paper, ScrollArea, Skeleton, Stack, Table, TextInput } from '@mantine/core';
import { revealItemInDir } from '@tauri-apps/plugin-opener';
import Database from '@tauri-apps/plugin-sql';
import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { TbSearch } from 'react-icons/tb';
import { useTranslation } from 'react-i18next';
import { PlayAction, Track } from '../common/commands';
import { MusicCasterAPIContext, PlayerStateContext } from '../common/contexts';
import { formatTime } from '../common/format';
import { ContextMenu, useContextMenu } from '../components/ContextMenu';
import MetadataEditorModal from '../components/MetadataEditorModal';
import TrackContextMenu from '../components/TrackContextMenu';
import classes from './MusicLibrary.module.css';

// fixed row height; cell text is clamped (see .cellText) so no row can outgrow it
const ROW_HEIGHT = 78;
const SEARCHABLE_TRACK_KEYS: Array<keyof Track> = [
	'album', 'artist', 'title', 'genre', 'length', 'track_number', 'file_path'
];

export default function MusicLibrary() {
	const { t } = useTranslation();
	const playerState = useContext(PlayerStateContext);
	const api = useContext(MusicCasterAPIContext)!;
	const [contextMenu, setMenuItem] = useContextMenu<Track>({ showOnClick: true });
	const [loading, setLoading] = useState(true);
	const [tracks, setTracks] = useState<Track[]>([]);
	const [sortColumn, setSortColumn] = useState<keyof Track | null>(null);
	const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
	const [search, setSearch] = useState('');
	const [editingTrack, setEditingTrack] = useState<Track | null>(null);
	// bumped after a metadata save so the daemon-served thumbnails (sent with a
	// long max-age) aren't served from the browser cache
	const [artVersion, setArtVersion] = useState(0);

	// width is a min-width on the header cell: a plain width on a th is only a hint in auto
	// table layout and gets squeezed by the text-heavy columns. maxWidth goes on the cell's
	// text div since table cells ignore max-width; it caps the column via its content
	const columns: Array<{ key: keyof Track; label: string; width?: number; maxWidth?: number }> = [
		{ key: 'album', label: 'ALBUM', width: 100 },
		{ key: 'title', label: 'TITLE', width: 100 },
		{ key: 'artist', label: 'ARTIST', width: 100 },
		{ key: 'genre', label: 'GENRE', maxWidth: 200, width: 80 },
		{ key: 'length', label: 'LENGTH' },
		{ key: 'track_number', label: '#', width: 40 },
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
		if (sortColumn === column) {
			setSortDirection(direction => direction === 'asc' ? 'desc' : 'asc');
		} else {
			setSortColumn(column);
			setSortDirection('asc');
		}
	};

	const filteredTracks = useMemo(() => {
		// Commas separate alternatives, while spaces combine terms. For example,
		// "trance, techno" finds either genre and "techno remix, trance" finds
		// Techno tracks with "remix" metadata or any Trance track. Matching is
		// case-insensitive and partial: "electro" finds "Electronic".
		const alternatives = search.toLocaleLowerCase()
			.split(',')
			.map(query => query.trim().split(/\s+/).filter(Boolean))
			.filter(terms => terms.length > 0);
		if (alternatives.length === 0) return tracks;

		return tracks.filter(track => {
			const searchableText = SEARCHABLE_TRACK_KEYS
				.map(key => String(track[key] ?? ''))
				.join(' ')
				.toLocaleLowerCase();
			return alternatives.some(terms => terms.every(term => searchableText.includes(term)));
		});
	}, [tracks, search]);

	const sortedTracks = useMemo(() => {
		if (sortColumn === null) return filteredTracks;

		return [...filteredTracks].sort((a, b) => {
			const first = a[sortColumn];
			const second = b[sortColumn];
			let comparison: number;

			if (first == null && second == null) comparison = 0;
			else if (first == null) comparison = -1;
			else if (second == null) comparison = 1;
			else if (typeof first === 'number' && typeof second === 'number') comparison = first - second;
			else comparison = String(first).localeCompare(String(second), undefined, { numeric: true, sensitivity: 'base' });

			return sortDirection === 'asc' ? comparison : -comparison;
		});
	}, [filteredTracks, sortColumn, sortDirection]);

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

			<Paper className={classes.tab} shadow='sm' px='md' pb='xs' pt='xs' display='flex'>
				<TextInput
					label={t('Search')}
					styles={{ label: { marginTop: 0 } }}
					aria-label={t('Search')}
					value={search}
					onChange={event => setSearch(event.currentTarget.value)}
					placeholder={t('Search music library')}
					leftSection={<TbSearch size={16} />}
					mb='sm'
				/>
				<ScrollArea>
					<Table highlightOnHover>
						<Table.Thead>
							<Table.Tr>
								<Table.Th aria-label='Album art' />
								{columns.map((column) => (
									<Table.Th
										key={column.key}
										onClick={() => handleSort(column.key)}
										style={{ cursor: 'pointer', minWidth: column.width, whiteSpace: 'nowrap' }}
									>
										{column.label} {sortColumn === column.key && (sortDirection === 'asc' ? '▲' : '▼')}
									</Table.Th>
								))}
							</Table.Tr>
						</Table.Thead>
						<Table.Tbody>
							{
								loading && tracks.length === 0 && (
									[...Array(15)].map((_, index) => (
										<Table.Tr key={index} style={{ height: ROW_HEIGHT }}>
											{/* +1 accounts for artwork */}
											<Table.Td colSpan={columns.length + 1}>
												<Skeleton height={ROW_HEIGHT} />
											</Table.Td>
										</Table.Tr>
									))
								)
							}
							{sortedTracks.length > 0 && sortedTracks.map((track, index) => (
								<Table.Tr
									key={index}
									// onClick={() => setSelectedTrack(track)}
									className={classes.row}
									style={{ height: ROW_HEIGHT }}
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
										<TableCell key={column.key} track={track} columnKey={column.key} maxWidth={column.maxWidth} />
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

function TableCell({ track, columnKey, maxWidth }: { track: Track, columnKey: keyof Track, maxWidth?: number }) {
	if (columnKey === 'length') {
		return (
			<Table.Td key={columnKey}>
				<div className={classes.cellText} style={{ maxWidth }}>{formatTime(track[columnKey])}</div>
			</Table.Td>
		);
	}
	return (
		<Table.Td key={columnKey}>
			<div className={classes.cellText} style={{ maxWidth }}>{track[columnKey]}</div>
		</Table.Td>
	);
}
