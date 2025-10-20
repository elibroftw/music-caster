import { Box, Paper, ScrollArea, Table, Text } from '@mantine/core';
import { useState } from 'react';

interface QueueTrack {
	artist: string;
	album: string;
	title: string;
	track: string;
	length: string;
	bpm: string;
	bitrate: string;
}

export default function Queue() {
	const [queueTracks] = useState<QueueTrack[]>([]);
	const [selectedTrack, setSelectedTrack] = useState<QueueTrack | null>(null);

	return (
		<Box style={{ height: 'calc(100vh - 150px)' }}>
			<Paper shadow="sm" p="md" style={{ height: '100%', overflow: 'hidden' }}>
				<ScrollArea style={{ height: '100%' }}>
					<Table highlightOnHover>
						<Table.Thead>
							<Table.Tr>
								<Table.Th>ARTIST</Table.Th>
								<Table.Th>ALBUM</Table.Th>
								<Table.Th>TITLE</Table.Th>
								<Table.Th>TRACK</Table.Th>
								<Table.Th>LENGTH</Table.Th>
								<Table.Th>BPM</Table.Th>
								<Table.Th>BITRATE</Table.Th>
							</Table.Tr>
						</Table.Thead>
						<Table.Tbody>
							{queueTracks.length === 0 ? (
								<Table.Tr>
									<Table.Td colSpan={7}>
										<Text ta="center" c="dimmed">Queue is empty</Text>
									</Table.Td>
								</Table.Tr>
							) : (
								queueTracks.map((track, index) => (
									<Table.Tr
										key={index}
										onClick={() => setSelectedTrack(track)}
										style={{ cursor: 'pointer' }}
									>
										<Table.Td>{track.artist}</Table.Td>
										<Table.Td>{track.album}</Table.Td>
										<Table.Td>{track.title}</Table.Td>
										<Table.Td>{track.track}</Table.Td>
										<Table.Td>{track.length}</Table.Td>
										<Table.Td>{track.bpm}</Table.Td>
										<Table.Td>{track.bitrate}</Table.Td>
									</Table.Tr>
								))
							)}
						</Table.Tbody>
					</Table>
				</ScrollArea>
			</Paper>
		</Box>
	);
}
