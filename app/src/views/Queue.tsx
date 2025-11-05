import { Button, Flex, Menu, Paper, ScrollArea, Skeleton, Stack, Text } from '@mantine/core';
import { useWindowEvent } from '@mantine/hooks';
import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { MusicCasterAPIContext, PlayerStateContext } from '../common/contexts';
import TrackContextMenu from '../components/TrackContextMenu';
import classes from './Queue.module.css';

interface MenuOpen {
	index: number;
	x: number;
	y: number;
};

export default function Queue() {
	const playerState = useContext(PlayerStateContext);
	const [menuOpen, setMenuOpen] = useState<MenuOpen | null>(null);

	const viewportRef = useRef<HTMLDivElement>(null);
	const targetRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const handler = () => setMenuOpen(null);
		window.addEventListener('scroll', handler, true);
		return () => {
			window.removeEventListener('scroll', handler);
		}
	}, []);
	useWindowEvent('click', () => setMenuOpen(null));
	useWindowEvent('contextmenu', event => {
		if (event.clientX !== menuOpen?.x || event.clientY !== menuOpen.y) {
			setMenuOpen(null);
		}
	});

	const api = useContext(MusicCasterAPIContext)!;

	const queuePosition = playerState?.queue_position ?? 0;

	const queueRendered = useMemo(
		() => {
			if (playerState === null || playerState.status === 'NOT_RUNNING') return (
				[...Array(100)].map((_, index) => (
					<Skeleton key={index} height={40} />
				))
			);

			if (playerState.queue.length === 0) return (
				<Text ta='center' c='dimmed' mt='xl'>Queue is empty</Text>
			);

			return playerState.queue.map((track, index) => (
				<Paper
					key={index}
					ref={index === queuePosition ? targetRef : null}
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
						backgroundColor: index === queuePosition ? 'var(--mantine-color-blue-light)' : undefined
					}}
					onClick={() => onTrackClick(index - queuePosition)}
				>
					<Flex gap='md' align='center'>
						<Text size='sm' c='dimmed' style={{ minWidth: '2em', textAlign: 'right' }}>
							{index - queuePosition}
						</Text>
						<Text size='sm' fw={500}>{track}</Text>
					</Flex>
				</Paper>));
		}, [JSON.stringify(playerState?.queue), queuePosition]);

	useEffect(() => {
		if (targetRef.current !== null) {
			viewportRef.current?.scroll({ top: targetRef.current.offsetTop - 10, behavior: 'smooth' });
		}
	}, [JSON.stringify(playerState?.queue), playerState?.queue_position]);

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

	const handlePlayNext = () => {
	};

	const handleAddToQueue = () => {
	};

	const handleShowFile = () => {
	};

	const handleCopyUris = () => {
	};

	return (
		<ScrollArea className={classes.tab} viewportRef={viewportRef}>
			<Paper shadow='sm' p='md' >
				<Stack gap='xs'>
					<Menu opened={menuOpen !== null} key={JSON.stringify(menuOpen)}>
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
						/>
					</Menu>
					{queueRendered}
				</Stack>
			</Paper>
		</ScrollArea>
	);
}
