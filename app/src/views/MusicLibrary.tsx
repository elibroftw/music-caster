import { Box, Button, Group, Menu, Modal, Paper, Radio, ScrollArea, Skeleton, Stack, Table, Text, TextInput } from '@mantine/core';
import { useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';
import TrackContextMenu from '../components/TrackContextMenu';
import { PlayerStateContext } from '../common/contexts';

interface Track {
	artist: string;
	album: string;
	title: string;
	track: string;
	length: string;
	bpm: string;
	bitrate: string;
}

export default function MusicLibrary() {
	const { t } = useTranslation();
	const playerState = useContext(PlayerStateContext);
	const [tracks] = useState<Track[]>([]);
	const [selectedTrack, setSelectedTrack] = useState<Track | null>(null);
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
		{ key: 'track', label: 'TRACK' },
		{ key: 'length', label: 'LENGTH' },
		{ key: 'bpm', label: 'BPM' },
		{ key: 'bitrate', label: 'BITRATE' }
	];

	const handleSort = (column: keyof Track) => {
		setSortColumn(column);
	};

	const handleSubmitStream = () => {
		console.log('Stream URL:', streamUrl, 'Action:', streamAction);
	};

	const handleEditMetadata = (track: Track) => {
		setEditingTrack(track);
		setMetadataForm({
			artist: track.artist,
			album: track.album,
			title: track.title
		});
		setMetadataModalOpened(true);
	};

	const handleSaveMetadata = () => {
		console.log('Saving metadata:', metadataForm);
		setMetadataModalOpened(false);
	};

	const handlePlayNext = (track: Track) => {
		console.log('Play next:', track);
	};

	const handleAddToQueue = (track: Track) => {
		console.log('Add to queue:', track);
	};

	const handleRemove = (track: Track) => {
		console.log('Remove track:', track);
	};

	const handleShowFile = (track: Track) => {
		console.log('Show file:', track);
	};

	const handleDuplicate = (track: Track) => {
		console.log('Duplicate track:', track);
	};

	const handleCopyUris = (track: Track) => {
		console.log('Copy URIs:', track);
	};

	if (playerState?.status === 'NOT_RUNNING') {
		return (
			<Paper shadow="sm" p="md" style={{ height: 'calc(100vh - 150px)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
				<ScrollArea style={{ flex: 1 }}>
					<Stack gap="xs">
						{[...Array(15)].map((_, index) => (
							<Skeleton key={index} height={40} />
						))}
					</Stack>
				</ScrollArea>
				<Box px="md" py="xs" style={{ borderTop: '1px solid #e0e0e0' }}>
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
				title="Edit Metadata"
				centered
			>
				<Stack gap="md">
					<TextInput
						label="Artist"
						value={metadataForm.artist}
						onChange={(e) => setMetadataForm({ ...metadataForm, artist: e.currentTarget.value })}
					/>
					<TextInput
						label="Album"
						value={metadataForm.album}
						onChange={(e) => setMetadataForm({ ...metadataForm, album: e.currentTarget.value })}
					/>
					<TextInput
						label="Title"
						value={metadataForm.title}
						onChange={(e) => setMetadataForm({ ...metadataForm, title: e.currentTarget.value })}
					/>
					<Group justify="flex-end">
						<Button variant="default" onClick={() => setMetadataModalOpened(false)}>
							Cancel
						</Button>
						<Button onClick={handleSaveMetadata}>Save</Button>
					</Group>
				</Stack>
			</Modal>

			<Paper shadow="sm" p="md" style={{ height: 'calc(100vh - 150px)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
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
									<Menu key={index} trigger="hover" openDelay={100} closeDelay={400}>
										<Menu.Target>
											<Table.Tr
												onClick={() => setSelectedTrack(track)}
												style={{ cursor: 'pointer' }}
											>
												{columns.map((column) => (
													<Table.Td key={column.key}>{track[column.key]}</Table.Td>
												))}
											</Table.Tr>
										</Menu.Target>
										<TrackContextMenu
											track={track}
											onEditMetadata={handleEditMetadata}
											onPlayNext={handlePlayNext}
											onAddToQueue={handleAddToQueue}
											onRemove={handleRemove}
											onShowFile={handleShowFile}
											onCopyUris={handleCopyUris}
											onDuplicate={handleDuplicate}
										/>
									</Menu>
								))}
							</Table.Tbody>
						</Table>
					</ScrollArea>

					<Box px="md" py="xs" style={{ borderTop: '1px solid #e0e0e0' }}>
						<Group align='center' gap='sm'>
							<Text size='sm' fw={500} style={{ whiteSpace: 'nowrap' }}>STREAM FROM URL:</Text>
							<TextInput
								value={streamUrl}
								onChange={(e) => setStreamUrl(e.currentTarget.value)}
								placeholder="Enter stream URL"
								style={{ flex: 1 }}
							/>
							<Radio.Group value={streamAction} onChange={setStreamAction}>
								<Group gap='md'>
									<Radio value="play" label="PLAY NOW" />
									<Radio value="queue" label="ADD TO QUEUE" />
								</Group>
							</Radio.Group>
							<Button onClick={handleSubmitStream}>SUBMIT</Button>
						</Group>
					</Box>
			</Paper>
		</>
	);
}
