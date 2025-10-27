import { ActionIcon, Anchor, Box, Button, Group, Image, Modal, Paper, Radio, Select, SimpleGrid, Skeleton, Slider, Stack, Text, TextInput } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { useContext, useEffect, useState } from 'react';
import { IoMusicalNotes } from 'react-icons/io5';
import { TbArrowsShuffle, TbBrandGithub, TbClock, TbInfoCircle, TbPlayerPauseFilled, TbPlayerPlayFilled, TbPlayerSkipBackFilled, TbPlayerSkipForwardFilled, TbRepeat, TbSettings, TbVolume, TbWorld } from 'react-icons/tb';
import { MusicCasterAPIContext, PlayerStateContext } from '../common/contexts';

interface Track {
	artist: string;
	album: string;
	title: string;
	track: string;
	length: string;
	bpm: string;
	bitrate: string;
}

interface PlaybackAsideProps {
	onOpenSettings: () => void;
}

function formatTime(seconds: number): string {
	const hours = Math.floor(seconds / 3600);
	const minutes = Math.floor((seconds % 3600) / 60);
	const secs = seconds % 60;

	if (hours > 0) {
		return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
	}
	return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

export default function PlaybackAside({ onOpenSettings }: PlaybackAsideProps) {
	const playerState = useContext(PlayerStateContext);
	const daemonLoading = playerState === null || playerState.status === 'NOT_RUNNING';
	const api = useContext(MusicCasterAPIContext)!;

	const [qrCodeOpened, { open: openQrCode, close: closeQrCode }] = useDisclosure(false);
	const [infoOpened, { open: openInfo, close: closeInfo }] = useDisclosure(false);
	const [timerOpened, { open: openTimer, close: closeTimer }] = useDisclosure(false);
	const [timerAction, setTimerAction] = useState('stop');
	const [timerInput, setTimerInput] = useState('');
	const [albumArtUrl, setAlbumArtUrl] = useState<string | null>(null);


	useEffect(() => {
		const fetchAlbumArt = async () => {
			try {
				const dataSrc = await api.getAlbumArtUrl();
				setAlbumArtUrl(dataSrc);
			} catch (error) {
				setAlbumArtUrl(null);
			}
		};

		if (playerState?.file_name) {
			fetchAlbumArt();
		} else {
			setAlbumArtUrl(null);
		}
	}, [playerState?.file_name]);

	const handlePlayPause = async () => {
		try {
			if (playerState?.status === 'PLAYING') {
				await api.pause();
			} else {
				await api.play();
			}
		} catch (error) {
			console.error('Failed to toggle play/pause:', error);
		}
	};

	const handlePrev = async () => {
		try {
			await api.prev();
		} catch (error) {
			console.error('Failed to go to previous track:', error);
		}
	};

	const handleNext = async () => {
		try {
			await api.next();
		} catch (error) {
			console.error('Failed to go to next track:', error);
		}
	};

	const handleToggleShuffle = async () => {
		try {
			await api.toggleShuffle();
		} catch (error) {
			console.error('Failed to toggle shuffle:', error);
		}
	};

	const handleToggleRepeat = async () => {
		try {
			await api.toggleRepeat();
		} catch (error) {
			console.error('Failed to toggle repeat:', error);
		}
	};

	return (
		<>
			<Modal
				opened={qrCodeOpened}
				onClose={closeQrCode}
				title='Remote Access'
				centered
			>
				<Stack align='center' gap='md'>
					<Text size='sm'>Scan this QR code to access Music Caster remotely</Text>
					<Box
						style={{
							width: '200px',
							height: '200px',
							backgroundColor: '#fff',
							border: '1px solid #e0e0e0',
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center'
						}}
					>
						<Text c='dimmed'>QR Code</Text>
					</Box>
					<Text size='xs' c='dimmed'>http://192.168.1.100:8080</Text>
				</Stack>
			</Modal>

			<Modal
				opened={infoOpened}
				onClose={closeInfo}
				title='About'
				centered
			>
				<Stack align='center' gap='md'>
					<Text size='lg' fw={500}>Music Caster</Text>
					<Text size='sm' c='dimmed'>Version 1.0.0</Text>
					<Text size='sm'>
						Developed by Elijah Lopez <Anchor href='mailto:elijahlopez@proton.me'>{'elijahlopez@proton.me'}</Anchor>
					</Text>
					<Anchor href='https://github.com/elibroftw' target='_blank' rel='noopener noreferrer'>
						<Group gap='xs'>
							<TbBrandGithub size={20} />
							<Text size='sm'>Source Code</Text>
						</Group>
					</Anchor>
					<Text size='sm' ta='center'>
						You can support me by following me on{' '}
						<Anchor href='https://x.com/elibroftw' target='_blank' rel='noopener noreferrer'>
							Twitter
						</Anchor>
					</Text>
				</Stack>
			</Modal>

			<Modal
				opened={timerOpened}
				onClose={closeTimer}
				title='Sleep Timer'
				centered
			>
				<Stack gap='md'>
					<Radio.Group value={timerAction} onChange={setTimerAction}>
						<Stack gap='xs'>
							<Radio value='shutdown' label='Shut down when timer runs out' />
							<Radio value='sleep' label='Sleep when timer runs out' />
							<Radio value='hibernate' label='Hibernate when timer runs out' />
							<Radio value='stop' label='Only stop playback' />
						</Stack>
					</Radio.Group>
					<Group>
						<TextInput
							placeholder='Enter minutes or HH:MM'
							value={timerInput}
							onChange={(e) => setTimerInput(e.currentTarget.value)}
							style={{ flex: 1 }}
						/>
						<Button color='red'>Submit</Button>
					</Group>
					<Text size='sm' c='dimmed'>No Timer Set</Text>
				</Stack>
			</Modal>

			<Stack h='100%' justify='space-between'>
				<Group align='flex-start' gap='xs' wrap='nowrap'>
					<Paper p='md' style={{ flex: 1, minWidth: '250px' }}>
						<Stack gap='md'>
							<Box
								style={{
									width: '100%',
									aspectRatio: '1',
									backgroundColor: '#2c2c2c',
									display: 'flex',
									alignItems: 'center',
									justifyContent: 'center',
									borderRadius: '4px',
									overflow: 'hidden'
								}}
							>
								{albumArtUrl ? (
									<Image
										src={albumArtUrl}
										alt='Album Art'
										style={{
											width: '100%',
											height: '100%',
											objectFit: 'cover'
										}}
									/>
								) : (
									<IoMusicalNotes size={64} color='#6c757d' />
								)}
							</Box>

							<Stack gap='xs' align='center'>
								{
									daemonLoading ?
										<>
											<Skeleton height={20} width='50%' />
											<Skeleton height={20} width='45%' />
											<Skeleton height={20} width='55%' />
										</> : <>
											<Text size='sm' fw={500}>{playerState.title || 'Nothing Playing'}</Text>
											<Text size='sm' fw={500}>{playerState.artist || ''}</Text>
											<Text size='sm' fw={500}>
												{playerState.album === playerState.title ? 'Single' : (playerState.album || '')}
											</Text>
										</>
								}
							</Stack>
						</Stack>
					</Paper>

					<SimpleGrid cols={1} spacing='lg' verticalSpacing='5'>
						<ActionIcon disabled={daemonLoading} size='lg' variant='filled' onClick={onOpenSettings}><TbSettings size={20} /></ActionIcon>
						<ActionIcon size='lg' variant='default' onClick={openInfo}><TbInfoCircle size={20} /></ActionIcon>
						<ActionIcon size='lg' variant='default' onClick={openTimer}><TbClock size={20} /></ActionIcon>
						{/* <ActionIcon size='lg' variant='default'><TbPlus size={20} /></ActionIcon> */}
						{/* <ActionIcon size='lg' variant='default'><TbFile size={20} /></ActionIcon> */}
						{/* <ActionIcon size='lg' variant='default'>Play Next</ActionIcon> */}
						{/* <ActionIcon size='lg' variant='default'><TbCopy size={20} /></ActionIcon> */}
						{/* <ActionIcon size='lg' variant='default'><TbList size={20} /></ActionIcon> */}
						{/* <ActionIcon size='lg' variant='default'><TbChevronUp size={20} /></ActionIcon>
						<ActionIcon size='lg' variant='default'><TbX size={20} /></ActionIcon>
						<ActionIcon size='lg' variant='default'><TbChevronDown size={20} /></ActionIcon> */}
						<ActionIcon size='lg' variant='default' onClick={openQrCode}><TbWorld size={20} /></ActionIcon>
					</SimpleGrid>
				</Group>

				<Stack gap='md'>
					<Group justify='center' gap='xs'>
						<ActionIcon size='sm' variant='default' onClick={handleToggleShuffle}><TbArrowsShuffle size={16} /></ActionIcon>
						<ActionIcon size={36} variant='default' radius='xl' onClick={handlePrev}>
							<TbPlayerSkipBackFilled size={20} />
						</ActionIcon>
						<ActionIcon size={48} variant='filled' radius='xl' onClick={handlePlayPause}>
							{playerState?.status === 'PLAYING' ? (
								<TbPlayerPauseFilled size={24} />
							) : (
								<TbPlayerPlayFilled size={24} />
							)}
						</ActionIcon>
						<ActionIcon size={36} variant='default' radius='xl' onClick={handleNext}>
							<TbPlayerSkipForwardFilled size={20} />
						</ActionIcon>
						<ActionIcon size='sm' variant='default' onClick={handleToggleRepeat}><TbRepeat size={16} /></ActionIcon>
					</Group>

					<Stack gap='xs'>
						<Group>
							<ActionIcon size='sm' variant='default'><TbVolume size={16} /></ActionIcon>
							<Box style={{ flex: 1 }}>
								<Slider
									min={0}
									max={100}
									value={playerState?.volume}
									step={1}
								/>
							</Box>
						</Group>
					</Stack>

					<Box>
						<Stack gap={4}>
							<Group justify='space-between'>
								{
									daemonLoading || false ?
										<>
											<Skeleton height={17} width={35} />
											<Skeleton height={17} width={35} />
										</> :
										<>
											<Text size='xs'>{formatTime(Math.floor(playerState.track_position || 0))}</Text>
											<Text size='xs'>-{formatTime(Math.floor((playerState.track_length || 0) - (playerState.track_position || 0)))}</Text>
										</>
								}
							</Group>
							<Slider
								min={0}
								max={Math.floor(playerState?.track_length || 0)}
								value={Math.floor(playerState?.track_position || 0)}
								step={1}
								label={formatTime}
							/>
						</Stack>
					</Box>

					<Group justify='space-between'>
						<Text size='sm' fw={500}>Device</Text>
						{
							daemonLoading ?
								<Skeleton style={{ flex: 1 }} height={36} /> :
								<Select value='LOCAL DEVICE' style={{ flex: 1 }} data={['LOCAL DEVICE']}></Select>
						}

					</Group>
				</Stack>
			</Stack>
		</>
	);
}
