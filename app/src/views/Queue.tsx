import { Button, Flex, Menu, Paper, ScrollArea, Skeleton, Stack, Text } from '@mantine/core';
import { useWindowEvent } from '@mantine/hooks';
import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { MusicCasterAPIContext, PlayerStateContext } from '../common/contexts';
import TrackContextMenu from '../components/TrackContextMenu';
import { ContextMenu, useContextMenu } from '../components/ContextMenu';
import classes from './Queue.module.css';

export default function Queue() {
	const playerState = useContext(PlayerStateContext);
	const [contextMenuTrigger, setContextMenuTrigger] = useContextMenu<number>();

	const viewportRef = useRef<HTMLDivElement>(null);
	const targetRef = useRef<HTMLDivElement>(null);

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
						setContextMenuTrigger({
							item: index,
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
					<ContextMenu trigger={contextMenuTrigger} offsetLeft={70} offsetTop={-75}>
						<TrackContextMenu
							onEditMetadata={handleEditMetadata}
							onPlayNext={handlePlayNext}
							onAddToQueue={handleAddToQueue}
							onShowFile={handleShowFile}
							onCopyUris={handleCopyUris}
						/>
					</ContextMenu>
					{queueRendered}
				</Stack>
			</Paper>
		</ScrollArea>
	);
}
