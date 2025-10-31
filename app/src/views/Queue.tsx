import { Box, Button, Flex, Menu, Paper, ScrollArea, Skeleton, Stack, Text } from '@mantine/core';
import { useWindowEvent } from '@mantine/hooks';
import { useContext, useEffect, useRef, useState } from 'react';
import { MusicCasterAPIContext, PlayerStateContext } from '../common/contexts';
import TrackContextMenu from '../components/TrackContextMenu';

interface MenuOpen {
	index: number;
	x: number;
	y: number;
};

export default function Queue() {
	const playerState = useContext(PlayerStateContext);
	const api = useContext(MusicCasterAPIContext)!;
	const currentTrackRef = useRef<HTMLDivElement>(null);
	const [menuOpen, setMenuOpen] = useState<MenuOpen | null>(null);

	useEffect(() => {
		const handler = () => setMenuOpen(null);
		window.addEventListener('scroll', handler, true);
		return () => {
			window.removeEventListener('scroll', handler);
		}
	}, []);
	useWindowEvent('click', () => setMenuOpen(null));

	useEffect(() => {
		// TODO: scroll down till the playing track is at the 'top' of the queue
		// adapt from https://stackoverflow.com/a/45411081/7732434
	}, [playerState]);

	if (playerState === null || playerState?.status === 'NOT_RUNNING') {
		return (
			<Box style={{ height: 'calc(100vh - 140px)' }}>
				<ScrollArea style={{ height: '100%' }}>
					<Paper shadow='sm' p='md' style={{ height: '100%', overflow: 'hidden' }}>
						<Stack gap='xs'>
							{[...Array(100)].map((_, index) => (
								<Skeleton key={index} height={40} />
							))}
						</Stack>
					</Paper>
				</ScrollArea>
			</Box>
		);
	}

	const onTrackClick = (index: number) => {
		if (index < 0) {
			api.prev(-index);
		}
		else if (index > 0) {
			api.next(index);
		}
	}

	const handleEditMetadata = () => {
	};

	const handleSaveMetadata = () => {
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

	return (
		<Box style={{ height: 'calc(100vh - 140px)' }}>
			<ScrollArea style={{ height: '100%' }}>
				<Paper shadow='sm' p='md' style={{ height: '100%', overflow: 'hidden' }}>
					{!playerState || playerState.queue.length === 0 ? (
						<Text ta='center' c='dimmed' mt='xl'>Queue is empty</Text>
					) : (
						<Stack gap='xs'>
							<Menu opened={menuOpen !== null} key={menuOpen?.index}>
								<Menu.Target>
									<Button unstyled
										style={{
											position: 'absolute',
											width: 0,
											height: 0,
											padding: 0,
											border: 0,
											left: (menuOpen?.x ?? 0) + 70,
											top: (menuOpen?.y ?? 0) - 75,
										}} />
								</Menu.Target>
								<TrackContextMenu
									onEditMetadata={handleEditMetadata}
									onPlayNext={handlePlayNext}
									onAddToQueue={handleAddToQueue}
									onShowFile={handleShowFile}
									onCopyUris={handleCopyUris}
									onDuplicate={handleDuplicate}
								/>
							</Menu>
							{playerState.queue.map((track, index) => (
								<Paper
									key={index}
									ref={index === playerState.queue_position ? currentTrackRef : null}
									onContextMenu={e => {
										e.preventDefault();
										setMenuOpen({
											index,
											x: e.clientX,
											y: e.clientY,
										});
									}}
									p='sm'
									withBorder
									style={{
										cursor: 'pointer',
										backgroundColor: index === playerState.queue_position ? 'var(--mantine-color-blue-light)' : undefined
									}}
									onClick={() => onTrackClick(index - playerState.queue_position)}
								>
									<Flex gap='md' align='center'>

										<Text size='sm' c='dimmed' style={{ minWidth: '2em', textAlign: 'right' }}>
											{index - playerState.queue_position}
										</Text>
										<Text size='sm' fw={500}>{track}</Text>

									</Flex>
								</Paper>
							))}
						</Stack>
					)}
				</Paper>
			</ScrollArea>
		</Box >
	);
}
