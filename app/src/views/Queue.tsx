import { Box, Flex, Paper, ScrollArea, Skeleton, Stack, Text } from '@mantine/core';
import { useContext, useEffect, useRef } from 'react';
import { PlayerStateContext } from '../common/contexts';

export default function Queue() {
	const playerState = useContext(PlayerStateContext);
	const scrolledRef = useRef(false);
	const currentTrackRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!scrolledRef.current && currentTrackRef.current && playerState) {
			currentTrackRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
			scrolledRef.current = true;
		}
	}, [playerState]);

	if (playerState?.status === 'NOT_RUNNING') {
		return (
			<Box style={{ height: 'calc(100vh - 150px)' }}>
				<Paper shadow="sm" p="md" style={{ height: '100%', overflow: 'hidden' }}>
					<ScrollArea style={{ height: '100%' }}>
						<Stack gap="xs">
							{[...Array(10)].map((_, index) => (
								<Skeleton key={index} height={60} />
							))}
						</Stack>
					</ScrollArea>
				</Paper>
			</Box>
		);
	}

	return (
		<Box style={{ height: 'calc(100vh - 150px)' }}>
			<Paper shadow="sm" p="md" style={{ height: '100%', overflow: 'hidden' }}>
				<ScrollArea style={{ height: '100%' }}>
					{!playerState || playerState.queue.length === 0 ? (
						<Text ta="center" c="dimmed" mt="xl">Queue is empty</Text>
					) : (
						<Stack gap="xs">
							{playerState.queue.map((track, index) => (
								<Paper
									key={index}
									ref={index === playerState.queue_position ? currentTrackRef : null}
									p="sm"
									withBorder
									style={{
										cursor: 'pointer',
										backgroundColor: index === playerState.queue_position ? 'var(--mantine-color-blue-light)' : undefined
									}}
								>
									<Flex gap="md" align="center">
										<Text size="sm" c="dimmed" style={{ minWidth: '2em', textAlign: 'right' }}>
											{index - playerState.queue_position + 1}
										</Text>
										<Text size="sm" fw={500}>{track}</Text>
									</Flex>
								</Paper>
							))}
						</Stack>
					)}
				</ScrollArea>
			</Paper>
		</Box>
	);
}
