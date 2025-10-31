import { Box, Button, Group, Menu, Modal, Paper, Radio, ScrollArea, Skeleton, Stack, Table, Text, TextInput } from '@mantine/core';
import { useWindowEvent } from '@mantine/hooks';
import Database from '@tauri-apps/plugin-sql';
import { Track } from 'common/commands';
import { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PlayerStateContext } from '../common/contexts';
import { formatTime } from '../common/utils';
import TrackContextMenu from '../components/TrackContextMenu';

interface MenuOpen {
	track: Track;
	x: number;
	y: number;
};

export default function MusicLibrary() {
	const { t } = useTranslation();
	const playerState = useContext(PlayerStateContext);
	const [menuOpen, setMenuOpen] = useState<MenuOpen | null>(null);
	const [loading, setLoading] = useState(true);
	const [tracks, setTracks] = useState<Track[]>([]);
	const [sortColumn, setSortColumn] = useState<keyof Track>('artist');
	const [streamUrl, setStreamUrl] = useState('');
	const [streamAction, setStreamAction] = useState('play');
	const [metadataModalOpened, setMetadataModalOpened] = useState(false);
	const [editingTrack, setEditingTrack] = useState<Track | null>(null);
	const [metadataForm, setMetadataForm] = useState({ artist: '', album: '', title: '' });

	useEffect(() => {
		const handler = () => setMenuOpen(null);
		window.addEventListener('scroll', handler, true);
		return () => {
			window.removeEventListener('scroll', handler);
		}
	}, []);
	useWindowEvent('click', () => setMenuOpen(null));

	const columns: Array<{ key: keyof Track; label: string }> = [
		{ key: 'artist', label: 'ARTIST' },
		{ key: 'album', label: 'ALBUM' },
		{ key: 'title', label: 'TITLE' },
		{ key: 'track_number', label: 'TRACK' },
		{ key: 'length', label: 'LENGTH' },
		// { key: 'bpm', label: 'BPM' },
		// { key: 'bitrate', label: 'BITRATE' }
	];

	useEffect(() => {
		(async () => {
			setLoading(true);
			const db = await Database.load('sqlite:music_caster.db');
			const result = await db.select('SELECT * FROM file_metadata');
			setTracks(result as Track[]);
			setLoading(false);
		})();
	}, []);

	const handleSort = (column: keyof Track) => {
		setSortColumn(column);
	};

	const handleSubmitStream = () => {
		console.log('Stream URL:', streamUrl, 'Action:', streamAction);
	};

	const handleEditMetadata = (track: Track) => {
		setEditingTrack(track);
		setMetadataForm({
			artist: track.artist ?? '',
			album: track.album ?? '',
			title: track.title ?? ','
		});
		setMetadataModalOpened(true);
	};

	const handleSaveMetadata = () => {
		console.log('Saving metadata:', metadataForm);
		setMetadataModalOpened(false);
	};

	const handlePlayNext = () => {
	};

	const handleAddToQueue = () => {
	};

	const handleShowFile = () => {
	};

	const handleDuplicate = () => {
	};

	const handleCopyUris = () => {
	};

	if (loading && tracks.length === 0) {
		return (
			<Paper shadow='sm' p='md' style={{ height: 'calc(100vh - 140px)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
				<ScrollArea style={{ flex: 1 }}>
					<Stack gap='xs'>
						{[...Array(15)].map((_, index) => (
							<Skeleton key={index} height={40} />
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
			<Modal
				opened={metadataModalOpened}
				onClose={() => setMetadataModalOpened(false)}
				title='Edit Metadata'
				centered
			>
				<Stack gap='md'>
					<TextInput
						label='Artist'
						value={metadataForm.artist}
						onChange={(e) => setMetadataForm({ ...metadataForm, artist: e.currentTarget.value })}
					/>
					<TextInput
						label='Album'
						value={metadataForm.album}
						onChange={(e) => setMetadataForm({ ...metadataForm, album: e.currentTarget.value })}
					/>
					<TextInput
						label='Title'
						value={metadataForm.title}
						onChange={(e) => setMetadataForm({ ...metadataForm, title: e.currentTarget.value })}
					/>
					<Group justify='flex-end'>
						<Button variant='default' onClick={() => setMetadataModalOpened(false)}>
							Cancel
						</Button>
						<Button onClick={handleSaveMetadata}>Save</Button>
					</Group>
				</Stack>
			</Modal>

			<Menu opened={menuOpen !== null} key={menuOpen?.track.file_path}>
				<Menu.Target>
					<Button unstyled
						style={{
							position: 'absolute',
							width: 0,
							height: 0,
							padding: 0,
							border: 0,
							left: (menuOpen?.x ?? 0) + 70,
							top: (menuOpen?.y ?? 0) - 25,
						}} />
				</Menu.Target>
				<TrackContextMenu
					onEditMetadata={() => handleEditMetadata(menuOpen!.track)}
					onPlayNext={handlePlayNext}
					onAddToQueue={handleAddToQueue}
					onShowFile={handleShowFile}
					onCopyUris={handleCopyUris}
					onDuplicate={handleDuplicate}
				/>
			</Menu>

			<Paper shadow='sm' p='md' style={{ height: 'calc(100vh - 140px)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>

				<ScrollArea style={{ flex: 1 }}>
					<Table highlightOnHover>
						<Table.Thead>
							<Table.Tr>
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
									style={{ cursor: 'pointer' }}
									onContextMenu={e => {
										e.preventDefault();
										setMenuOpen({
											track,
											x: e.clientX,
											y: e.clientY,
										});
									}}
									onClick={e => {
										e.preventDefault();
										setMenuOpen({
											track,
											x: e.clientX,
											y: e.clientY,
										});
									}}
								>
									{columns.map((column) =>
										<TableCell key={column.key} track={track} columnKey={column.key} />
									)}
								</Table.Tr>

							))}
						</Table.Tbody>
					</Table>
				</ScrollArea>

				<Box px='md' py='xs' style={{ borderTop: '1px solid #e0e0e0' }}>
					<Group align='center' gap='sm'>
						<Text size='sm' fw={500} style={{ whiteSpace: 'nowrap' }}>STREAM FROM URL:</Text>
						<TextInput
							value={streamUrl}
							onChange={(e) => setStreamUrl(e.currentTarget.value)}
							placeholder='Enter stream URL'
							style={{ flex: 1 }}
						/>
						<Radio.Group value={streamAction} onChange={setStreamAction}>
							<Group gap='md'>
								<Radio value='play' label='PLAY NOW' />
								<Radio value='queue' label='ADD TO QUEUE' />
							</Group>
						</Radio.Group>
						<Button onClick={handleSubmitStream}>SUBMIT</Button>
					</Group>
				</Box>
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
