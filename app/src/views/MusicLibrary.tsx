import { Box, Button, Group, Modal, Paper, Radio, ScrollArea, Skeleton, Stack, Table, Text, TextInput } from '@mantine/core';
import Database from '@tauri-apps/plugin-sql';
import { Track } from 'common/commands';
import { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PlayerStateContext } from '../common/contexts';
import { ContextMenu, useContextMenu } from '../components/ContextMenu';
import { formatTime } from '../common/utils';
import TrackContextMenu from '../components/TrackContextMenu';
import classes from './MusicLibrary.module.css';

export default function MusicLibrary() {
	const { t } = useTranslation();
	const playerState = useContext(PlayerStateContext);
	const [contextMenu, setMenuItem] = useContextMenu<Track>();
	const [loading, setLoading] = useState(true);
	const [tracks, setTracks] = useState<Track[]>([]);
	const [sortColumn, setSortColumn] = useState<keyof Track>('artist');
	const [streamUrl, setStreamUrl] = useState('');
	const [streamAction, setStreamAction] = useState('play');
	const [metadataModalOpened, setMetadataModalOpened] = useState(false);
	const [editingTrack, setEditingTrack] = useState<Track | null>(null);
	const [metadataForm, setMetadataForm] = useState({ artist: '', album: '', title: '' });

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

			<ContextMenu trigger={contextMenu} offsetLeft={88} offsetTop={-10}>
				<TrackContextMenu
					onEditMetadata={contextMenu ? () => handleEditMetadata(contextMenu.item) : undefined}
					onPlayNext={handlePlayNext}
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
