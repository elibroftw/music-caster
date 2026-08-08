import { ActionIcon, Flex, Group, Paper, ScrollArea, Skeleton, Stack, Text } from '@mantine/core';
import { revealItemInDir } from '@tauri-apps/plugin-opener';
import { useContext, useEffect, useMemo, useRef } from 'react';
import { TbClearAll } from 'react-icons/tb';
import { PlayAction } from '../common/commands';
import { MusicCasterAPIContext, PlayerStateContext } from '../common/contexts';
import { ContextMenu, useContextMenu } from '../components/ContextMenu';
import TrackContextMenu from '../components/TrackContextMenu';
import classes from './Queue.module.css';

export default function Queue() {
	const playerState = useContext(PlayerStateContext);
	const [contextMenuTrigger, setContextMenuTrigger] = useContextMenu<number>();

	const viewportRef = useRef<HTMLDivElement>(null);
	const targetRef = useRef<HTMLDivElement>(null);

	const api = useContext(MusicCasterAPIContext)!;

	const queuePosition = playerState?.queue_position ?? 0;
	// tracked as a boolean so the queue only re-renders when the daemon comes up
	// or goes away, not on every play/pause status change
	const daemonDown = playerState === null || playerState.status === 'NOT_RUNNING';

	const queueRendered = useMemo(
		() => {
			// no state yet, or the daemon is down: genuinely still loading
			if (playerState === null || playerState.status === 'NOT_RUNNING') return (
				[...Array(100)].map((_, index) => (
					<Skeleton key={index} height={40} />
				))
			);

			if (playerState.queue.length === 0) return (
				<>
					{[...Array(10)].map((_, index) => (
						<Skeleton key={index} height={40} animate={false} />
					))}
				</>
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
						<Text size='sm' fw={500}>{track[1]}</Text>
					</Flex>
				</Paper>));
		}, [JSON.stringify(playerState?.queue), queuePosition, daemonDown]);

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

	const handlePlayNext = () => {
		if (contextMenuTrigger?.item !== undefined) {
			api.modifyQueue([contextMenuTrigger.item], 'next_up');
		}
	};

	const handleAddToQueue = () => {
		const uri = playerState!.queue[contextMenuTrigger!.item]![0];
		api.playUri(uri, PlayAction.QUEUE);
	};

	const handleShowFile = async () => {
		if (contextMenuTrigger?.item !== undefined) {
			const uri = playerState!.queue[contextMenuTrigger.item]![0];
			await revealItemInDir(uri);
		}
	};

	const handleCopyUris = () => {
		const uri = playerState!.queue[contextMenuTrigger!.item]![0];
		navigator.clipboard.writeText(uri);
	};

	const handleRemove = () => {
		if (contextMenuTrigger?.item !== undefined) {
			api.modifyQueue([contextMenuTrigger.item], 'remove');
		}
	};

	const queueEmpty = daemonDown || playerState!.queue.length === 0;

	return (
		// the toolbar sits outside the ScrollArea so it stays put while the
		// queue auto-scrolls to the current track
		<Stack className={classes.tab} gap='xs'>
			<ScrollArea style={{ flex: 1, minHeight: 0 }} viewportRef={viewportRef}>
				<Paper shadow='sm' p='md' >
					<Stack gap='xs'>
						<ContextMenu trigger={contextMenuTrigger} offsetLeft={70} offsetTop={-75}>
							<TrackContextMenu
								onPlayNext={contextMenuTrigger?.item === queuePosition ? undefined : handlePlayNext}
								onAddToQueue={handleAddToQueue}
								onShowFile={handleShowFile}
								onCopyUris={handleCopyUris}
								onRemove={handleRemove}
							/>
						</ContextMenu>
						{queueRendered}
					</Stack>
				</Paper>
			</ScrollArea>
			<Group justify='flex-end'>
				<ActionIcon
					variant='default'
					size='lg'
					title='Clear queue'
					aria-label='Clear queue'
					disabled={queueEmpty}
					onClick={() => api.clearQueue()}
				>
					<TbClearAll size={20} />
				</ActionIcon>
			</Group>
		</Stack>
	);
}
