import { ActionIcon, Alert, Anchor, Box, Button, Flex, Group, HoverCard, Image, Loader, Modal, Paper, Radio, Select, SimpleGrid, Skeleton, Slider, Stack, Text, TextInput } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useElementSize, useMediaQuery } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { appLogDir, join } from '@tauri-apps/api/path';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { open as openFileDialog } from '@tauri-apps/plugin-dialog';
import { revealItemInDir } from '@tauri-apps/plugin-opener';
import { QRCodeSVG } from 'qrcode.react';
import { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { IoMusicalNotes } from 'react-icons/io5';
import { TbArrowsShuffle, TbBrandGithub, TbClock, TbDots, TbDownload, TbFileImport, TbFileText, TbFolderOpen, TbInfoCircle, TbLink, TbPlayerPauseFilled, TbPlayerPlayFilled, TbPlayerSkipBackFilled, TbPlayerSkipForwardFilled, TbPin, TbRepeat, TbRepeatOff, TbRepeatOnce, TbSettings, TbVolume, TbWorld, TbWorldOff } from 'react-icons/tb';
import { AUDIO_EXTENSIONS, PlayAction, type WebUrl } from '../common/commands';
import { MusicCasterAPIContext, PlayerStateContext } from '../common/contexts';
import { formatTime } from '../common/format';
import { fmtError } from '../common/utils';
import SettingsModal from './SettingsModal';

interface Track {
	artist: string;
	album: string;
	title: string;
	track: string;
	length: string;
	bpm: string;
	bitrate: string;
}

// one state for every modal so at most one can ever be open
enum ActiveModal {
	None,
	Settings,
	QrCode,
	Info,
	Timer,
	StreamURL,
	FilePicker,
}

interface PlaybackAsideProps {
	trayAction: string | null;
	onTrayActionConsumed: () => void;
	// present only when an update is available; installs it and relaunches
	onInstallUpdate?: () => void;
}

export default function PlaybackAside({ trayAction, onTrayActionConsumed, onInstallUpdate }: PlaybackAsideProps) {
	const playerState = useContext(PlayerStateContext);
	const daemonLoading = playerState === null || playerState.status === 'NOT_RUNNING';
	const api = useContext(MusicCasterAPIContext)!;

	const [activeModal, setActiveModal] = useState(ActiveModal.None);
	const closeModal = () => setActiveModal(ActiveModal.None);
	const [pickSource, setPickSource] = useState<'files' | 'folders'>('files');
	const [pickAction, setPickAction] = useState<PlayAction>(PlayAction.PLAY);
	const [picking, setPicking] = useState(false);
	const [timerAction, setTimerAction] = useState('stop');
	const [timerInput, setTimerInput] = useState('');
	const [timerStatus, setTimerStatus] = useState<string | null>(null);
	const [albumArtUrl, setAlbumArtUrl] = useState<string | null>(null);
	const [webUrl, setWebUrl] = useState<WebUrl | null>(null);
	const [webUrlLoading, setWebUrlLoading] = useState(false);
	const [webUrlError, setWebUrlError] = useState<string | null>(null);
	// bumped on every fetch so a response from a previous open cannot overwrite a newer one
	const webUrlRequest = useRef(0);
	const collapseIconColumn = useMediaQuery('(height < 520px)', false, { getInitialValueInEffect: false });
	// the art takes whatever height is left after the always-visible controls, so it shrinks
	// continuously with the window instead of jumping between sizes. measured, not a media
	// query, so it is right in both hosts (aside vs. playing tab). both host heights derive
	// from the viewport, so measuring them cannot feed back on the content being sized
	const { ref: rootRef, height: rootHeight } = useElementSize();
	const { ref: controlsRef, height: controlsHeight } = useElementSize();
	// paper padding (32) + art/text gap (16) + root stack gap (16) + three text lines (~90);
	// a constant rather than a measurement so switching layouts cannot oscillate
	const NOW_PLAYING_CHROME = 154;
	const MAX_ART = 220;
	// below this the art is too small to be worth its own row; use the thumbnail layout
	const MIN_ART = 96;
	const measured = rootHeight > 0 && controlsHeight > 0;
	const artSize = measured ? Math.min(MAX_ART, rootHeight - controlsHeight - NOW_PLAYING_CHROME) : MAX_ART;
	// until the first measurement lands, fall back to the viewport heuristic to avoid a flash
	const shortViewport = useMediaQuery('(height < 480px)', false, { getInitialValueInEffect: false });
	const compactNowPlaying = measured ? artSize < MIN_ART : shortViewport;
	const hideDeviceRow = useMediaQuery('(height < 340px)', false, { getInitialValueInEffect: false });

	// local value while dragging so the player state poll doesn't fight the slider
	const [pendingVolume, setPendingVolume] = useState<number | null>(null);

	// initialized from the window since this component remounts when it moves
	// between the aside and the playing tab, while the pin state survives
	const [alwaysOnTop, setAlwaysOnTop] = useState(false);
	useEffect(() => {
		getCurrentWindow().isAlwaysOnTop().then(setAlwaysOnTop).catch(() => {});
	}, []);
	const handleToggleAlwaysOnTop = async () => {
		const next = !alwaysOnTop;
		try {
			await getCurrentWindow().setAlwaysOnTop(next);
			setAlwaysOnTop(next);
		} catch (error) {
			notifications.show({
				title: 'Could not toggle pin to top',
				message: fmtError(error),
				color: 'red'
			});
		}
	};

	useEffect(() => {
		setPendingVolume(null);
	}, [playerState?.volume]);

	// scrub target held until the daemon reports a nearby position, since
	// track_position changes every poll and would snap the thumb back mid-seek
	const [pendingPosition, setPendingPosition] = useState<number | null>(null);
	const isScrubbing = useRef(false);
	const lastSeekAt = useRef(0);

	useEffect(() => {
		if (pendingPosition === null || !playerState || isScrubbing.current) return;
		if (Math.abs(playerState.track_position - pendingPosition) < 2 || Date.now() - lastSeekAt.current > 4000) {
			setPendingPosition(null);
		}
	}, [playerState?.track_position]);

	const streamURLForm = useForm({
		mode: 'uncontrolled',
		initialValues: {
			url: '',
			action: PlayAction.PLAY,
		},

		validate: {
			url: (value) => value.startsWith('http') || value.startsWith('www') || value.startsWith('//') ? null : 'Not a URL',
		},
	});

	const handleStreamURLSubmit = ({ url, action }: typeof streamURLForm.values) => {
		api.playUri(url, action);
		closeModal();
	};

	// the OS picker is the submit step: pick, then dispatch with the chosen action
	const handleFilePickerSubmit = async () => {
		setPicking(true);
		try {
			const selected = pickSource === 'folders'
				? await openFileDialog({ directory: true, multiple: true, title: 'Select Folders' })
				: await openFileDialog({
					multiple: true,
					title: 'Select Audio Files',
					filters: [{ name: 'Audio Files', extensions: AUDIO_EXTENSIONS }]
				});
			// null when the dialog was cancelled
			if (selected === null || selected.length === 0) return;
			await api.invokePlayUris({
				uris: selected,
				queue: pickAction === PlayAction.QUEUE,
				playNext: pickAction === PlayAction.PLAY_NEXT
			});
			closeModal();
		} catch (error) {
			notifications.show({
				title: 'Could not play selection',
				message: fmtError(error),
				color: 'red'
			});
		} finally {
			setPicking(false);
		}
	};

	const handleTimerSubmit = async () => {
		if (!timerInput.trim()) return;
		try {
			const timerSettings = ['timer_shut_down', 'timer_sleep', 'timer_hibernate', 'timer_stop'];
			for (const setting of timerSettings) {
				await api.changeSetting(setting, setting === `timer_${timerAction}`);
			}
			const result = await api.setTimer(timerInput.trim());
			setTimerStatus(result);
			setTimerInput('');
		} catch (error) {
			console.error('Failed to set timer:', error);
		}
	};

	useEffect(() => {
		if (activeModal === ActiveModal.StreamURL) {
			if (streamURLForm.values.url.length === 0) {
				// TODO: read from clipboard and prefill if matches URL
			}
		}
	}, [activeModal]);

	useEffect(() => {
		if (activeModal === ActiveModal.Timer) {
			api.getTimer().then(val => setTimerStatus(val === '0' ? null : val)).catch(() => setTimerStatus(null));
		}
	}, [activeModal]);

	const fetchWebUrl = useCallback(async () => {
		const request = ++webUrlRequest.current;
		setWebUrlLoading(true);
		setWebUrlError(null);
		try {
			const result = await api.getWebUrl();
			if (request !== webUrlRequest.current) return;
			setWebUrl(result);
		} catch (error) {
			if (request !== webUrlRequest.current) return;
			setWebUrl(null);
			setWebUrlError(fmtError(error));
		} finally {
			if (request === webUrlRequest.current) setWebUrlLoading(false);
		}
	}, [api]);

	useEffect(() => {
		if (activeModal === ActiveModal.QrCode) fetchWebUrl();
	}, [activeModal]);

	// tauri_plugin_log writes to <appLogDir>/logs.log; revealing the file lands the
	// explorer inside the log dir, whereas revealing the dir only selects it in its parent
	const handleOpenLogs = useCallback(async () => {
		const logDir = await appLogDir();
		try {
			await revealItemInDir(await join(logDir, 'logs.log'));
		} catch {
			try {
				// no log file yet (or it was deleted), settle for the folder
				await revealItemInDir(logDir);
			} catch {
				notifications.show({
					title: 'Could not open logs folder',
					message: logDir,
					color: 'red'
				});
			}
		}
	}, []);

	useEffect(() => {
		if (!trayAction) return;
		if (trayAction === 'timer-set') {
			setActiveModal(ActiveModal.Timer);
		} else if (trayAction === 'url-play') {
			streamURLForm.setFieldValue('action', PlayAction.PLAY);
			setActiveModal(ActiveModal.StreamURL);
		} else if (trayAction === 'url-queue') {
			streamURLForm.setFieldValue('action', PlayAction.QUEUE);
			setActiveModal(ActiveModal.StreamURL);
		} else if (trayAction === 'url-next') {
			streamURLForm.setFieldValue('action', PlayAction.PLAY_NEXT);
			setActiveModal(ActiveModal.StreamURL);
		}
		onTrayActionConsumed();
	}, [trayAction]);

	useEffect(() => {
		const fetchAlbumArt = async () => {
			try {
				const dataSrc = await api.getAlbumArtUrl();
				setAlbumArtUrl(dataSrc);
			} catch (error) {
				setAlbumArtUrl(null);
			}
		};

		fetchAlbumArt();
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

	const displayedPosition = Math.floor(pendingPosition ?? playerState?.track_position ?? 0);

	const handleScrub = (position: number) => {
		isScrubbing.current = true;
		setPendingPosition(position);
	};

	const handleScrubEnd = async (position: number) => {
		isScrubbing.current = false;
		lastSeekAt.current = Date.now();
		try {
			await api.seek(position);
		} catch (error) {
			console.error('Failed to seek:', error);
			setPendingPosition(null);
		}
	};

	const handleVolumeChangeEnd = async (volume: number) => {
		try {
			await api.setVolume(volume);
		} catch (error) {
			console.error('Failed to set volume:', error);
			setPendingVolume(null);
		}
	};

	const handleToggleRepeat = async () => {
		try {
			await api.toggleRepeat();
		} catch (error) {
			console.error('Failed to toggle repeat:', error);
		}
	};

	const shuffleEnabled = playerState?.shuffle ?? false;
	const repeatMode = playerState?.repeat ?? 'off';
	const RepeatIcon = repeatMode === 'one' ? TbRepeatOnce : repeatMode === 'all' ? TbRepeat : TbRepeatOff;
	const repeatLabel = { off: 'Repeat off', all: 'Repeat all', one: 'Repeat one' }[repeatMode];

	// rendered either directly in the icon column (enough vertical room) or inside
	// the "..." overflow menu's grid (short windows)
	const menuIcons = <>
		<ActionIcon disabled={daemonLoading} size='lg' variant='filled' title='Settings' onClick={() => setActiveModal(ActiveModal.Settings)}><TbSettings size={20} /></ActionIcon>
		<ActionIcon size='lg' variant='default' title='About' onClick={() => setActiveModal(ActiveModal.Info)}><TbInfoCircle size={20} /></ActionIcon>
		<ActionIcon size='lg' variant='default' title='Sleep timer' onClick={() => setActiveModal(ActiveModal.Timer)}><TbClock size={20} /></ActionIcon>
		{/* <ActionIcon size='lg' variant='default'><TbPlus size={20} /></ActionIcon> */}
		{/* <ActionIcon size='lg' variant='default'>Play Next</ActionIcon> */}
		{/* <ActionIcon size='lg' variant='default'><TbCopy size={20} /></ActionIcon> */}
		{/* <ActionIcon size='lg' variant='default'><TbList size={20} /></ActionIcon> */}
		{/* <ActionIcon size='lg' variant='default'><TbChevronUp size={20} /></ActionIcon>
		<ActionIcon size='lg' variant='default'><TbX size={20} /></ActionIcon>
		<ActionIcon size='lg' variant='default'><TbChevronDown size={20} /></ActionIcon> */}
		<ActionIcon size='lg' variant='default' title='Remote access' onClick={() => setActiveModal(ActiveModal.QrCode)}><TbWorld size={20} /></ActionIcon>
		<ActionIcon size='lg' variant='default' title='Stream a URL' onClick={() => setActiveModal(ActiveModal.StreamURL)}><TbLink size={20} /></ActionIcon>
		<ActionIcon size='lg' variant='default' title='Play files or folders' onClick={() => setActiveModal(ActiveModal.FilePicker)}><TbFileImport size={20} /></ActionIcon>
	</>;

	return (
		<>
			<SettingsModal opened={activeModal === ActiveModal.Settings} onClose={closeModal} />

			<Modal
				opened={activeModal === ActiveModal.QrCode}
				onClose={closeModal}
				title='Remote Access'
				centered
			>
				<Stack align='center' gap='md'>
					<Text size='sm'>Scan this QR code to access Music Caster remotely</Text>
					<Box
						style={{
							width: '216px',
							height: '216px',
							// the QR code needs a light background in both color schemes
							backgroundColor: '#fff',
							border: '1px solid #e0e0e0',
							borderRadius: '4px',
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center'
						}}
					>
						{webUrlLoading
							? <Loader color='dark' />
							: webUrl
								? <QRCodeSVG value={webUrl.url} size={200} level='M' bgColor='#fff' fgColor='#000' />
								: <TbWorldOff size={64} color='#adb5bd' />}
					</Box>
					{webUrlLoading && <Skeleton height={16} width='60%' />}
					{webUrlError && (
						<Alert color='red' variant='light' w='100%' title='Remote access unavailable'>
							<Stack gap='xs' align='flex-start'>
								<Text size='xs'>{webUrlError}</Text>
								<Button size='xs' variant='light' color='red' onClick={fetchWebUrl}>Retry</Button>
							</Stack>
						</Alert>
					)}
					{webUrl && (
						<Anchor href={webUrl.url} target='_blank' rel='noopener noreferrer' size='xs' c='dimmed'>
							{`http://${webUrl.ip}:${webUrl.port}`}
						</Anchor>
					)}
				</Stack>
			</Modal>

			<Modal
				opened={activeModal === ActiveModal.Info}
				onClose={closeModal}
				title='About'
				centered
			>
				<Stack align='center' gap='md'>
					<Text size='lg' fw={500}>Music Caster</Text>
					<Text size='sm' c='dimmed'>Version {__VERSION__}</Text>
					<Anchor
						href='https://raw.githubusercontent.com/elibroftw/music-caster/refs/heads/master/CHANGELOG.txt'
						target='_blank'
						rel='noopener noreferrer'
					>
						<Group gap='xs'>
							<TbFileText size={20} />
							<Text size='sm'>Changelog</Text>
						</Group>
					</Anchor>
					<Anchor component='button' type='button' onClick={handleOpenLogs}>
						<Group gap='xs'>
							<TbFolderOpen size={20} />
							<Text size='sm'>Open Logs Folder</Text>
						</Group>
					</Anchor>
					<Text size='sm'>
						Developed by Elijah Lopez <Anchor href='mailto:elijahllopezz@gmail.com'>{'elijahllopezz@gmail.com'}</Anchor>
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
				opened={activeModal === ActiveModal.Timer}
				onClose={closeModal}
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
						<Button color='red' onClick={handleTimerSubmit}>Submit</Button>
					</Group>
					<Group justify='space-between'>
						<Text size='sm' c='dimmed'>{timerStatus ? `Timer set` : 'No Timer Set'}</Text>
						{timerStatus && (
							<Button size='xs' variant='subtle' color='red' onClick={async () => {
								await api.cancelTimer();
								setTimerStatus(null);
							}}>Cancel Timer</Button>
						)}
					</Group>
				</Stack>
			</Modal>

			<Modal
				opened={activeModal === ActiveModal.StreamURL}
				onClose={closeModal}
				title='Stream URL'
				centered
			>
				<form onSubmit={streamURLForm.onSubmit(handleStreamURLSubmit)}>
					<Stack gap='md'>
						<TextInput
							placeholder='Enter stream URL'
							style={{ flex: 1 }}
							{...streamURLForm.getInputProps('url')}
						/>
						<Radio.Group {...streamURLForm.getInputProps('action')}>
							<Group gap='md'>
								<Radio value={PlayAction.PLAY} label='Play now' />
								<Radio value={PlayAction.QUEUE} label='Add to queue' />
								<Radio value={PlayAction.PLAY_NEXT} label='Play next' />
							</Group>
						</Radio.Group>
						<Button type='submit'>Submit</Button>
					</Stack>
				</form>
			</Modal>

			<Modal
				opened={activeModal === ActiveModal.FilePicker}
				onClose={closeModal}
				title='Play Files or Folders'
				centered
			>
				<Stack gap='md'>
					<Radio.Group
						label='Source'
						value={pickSource}
						onChange={value => setPickSource(value as typeof pickSource)}
					>
						<Group gap='md' mt='xs'>
							<Radio value='files' label='Files' />
							<Radio value='folders' label='Folders' />
						</Group>
					</Radio.Group>
					<Radio.Group
						label='Action'
						value={pickAction}
						onChange={value => setPickAction(value as PlayAction)}
					>
						<Group gap='md' mt='xs'>
							<Radio value={PlayAction.PLAY} label='Play now' />
							<Radio value={PlayAction.QUEUE} label='Add to queue' />
							<Radio value={PlayAction.PLAY_NEXT} label='Play next' />
						</Group>
					</Radio.Group>
					<Button loading={picking} onClick={handleFilePickerSubmit}>
						{pickSource === 'folders' ? 'Choose Folders' : 'Choose Files'}
					</Button>
				</Stack>
			</Modal>

			<Stack ref={rootRef} h='100%' justify='space-between'>
				<Group align='flex-start' justify='space-between' gap='xs' wrap='nowrap' style={{ minHeight: 0, overflow: 'hidden' }}>
					<Paper p='md' style={{ flex: 1, minWidth: 0 }}>
						{compactNowPlaying ? (
							<Stack gap={4} id='now-playing-info'>
								<Group gap='sm' wrap='nowrap'>
									<Box
										style={{
											width: 58,
											height: 58,
											flexShrink: 0,
											backgroundColor: '#2c2c2c',
											display: 'flex',
											alignItems: 'center',
											justifyContent: 'center',
											borderRadius: 'var(--mantine-radius-sm)',
											overflow: 'hidden'
										}}
									>
										{albumArtUrl ? (
											<Image
												src={albumArtUrl}
												alt='Album Art'
												style={{ width: '100%', height: '100%', objectFit: 'cover' }}
											/>
										) : (
											<IoMusicalNotes size={28} color='#6c757d' />
										)}
									</Box>
									<Stack gap={2} justify='center' style={{ flex: 1, minWidth: 0 }}>
										{
											daemonLoading ?
												<>
													<Skeleton height={13} width='45%' />
													<Skeleton height={13} width='50%' />
												</> : <>
													<Text fz={13} c='dimmed' lineClamp={1} title={playerState.artist || undefined}>
														{playerState.artist || ''}
													</Text>
													<Text fz={13} c='dimmed' lineClamp={1} title={playerState.album || undefined}>
														{playerState.album === playerState.title ? 'Single' : (playerState.album || '')}
													</Text>
												</>
										}
									</Stack>
								</Group>
								{
									daemonLoading ?
										<Skeleton height={15} width='60%' /> :
										<Text fz={15} fw={500} title={playerState.title || undefined} style={{ wordBreak: 'break-word' }}>
											{playerState.title || 'Nothing Playing'}
										</Text>
								}
							</Stack>
						) : (
							<Flex gap='md' wrap='wrap' align='center' justify='center'>
								<Box
									style={{
										width: artSize,
										height: artSize,
										flexShrink: 0,
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

								{/* capped and scrollable: a long title/artist/album in a narrow window would
								    otherwise grow tall enough to push the playback controls off screen */}
								<Stack gap='xs' align='center' id='now-playing-info' mah={140} style={{ overflowY: 'auto', flex: '1 1 180px', minWidth: 0 }}>
									{
										daemonLoading ?
											<>
												<Skeleton height={20} width='50%' />
												<Skeleton height={20} width='45%' />
												<Skeleton height={20} width='55%' />
											</> : <>
												<Text size='sm' fw={500} ta='center' lineClamp={2} title={playerState.title || undefined} style={{ wordBreak: 'break-word' }}>
													{playerState.title || 'Nothing Playing'}
												</Text>
												<Text size='sm' fw={500} ta='center' lineClamp={2} title={playerState.artist || undefined} style={{ wordBreak: 'break-word' }}>
													{playerState.artist || ''}
												</Text>
												<Text size='sm' fw={500} ta='center' lineClamp={2} title={playerState.album || undefined} style={{ wordBreak: 'break-word' }}>
													{playerState.album === playerState.title ? 'Single' : (playerState.album || '')}
												</Text>
											</>
									}
								</Stack>
							</Flex>
						)}
					</Paper>

					<SimpleGrid cols={1} spacing='lg' verticalSpacing='5'>
						{collapseIconColumn ? (
							/* below Mantine's modal layer (200) so the dropdown can't float over an open
							   modal; popovers default to 300 */
							<HoverCard shadow='md' position='left-start' withArrow openDelay={0} closeDelay={150} zIndex={190}>
								<HoverCard.Target>
									<ActionIcon size='lg' variant='default' title='More actions'><TbDots size={20} /></ActionIcon>
								</HoverCard.Target>
								<HoverCard.Dropdown p='xs'>
									<SimpleGrid cols={3} spacing='xs' verticalSpacing='xs'>
										{menuIcons}
									</SimpleGrid>
								</HoverCard.Dropdown>
							</HoverCard>
						) : menuIcons}
						<ActionIcon
							size='lg'
							variant={alwaysOnTop ? 'filled' : 'default'}
							title={alwaysOnTop ? 'Unpin from top' : 'Pin to top'}
							aria-pressed={alwaysOnTop}
							onClick={handleToggleAlwaysOnTop}
						>
							<TbPin size={20} />
						</ActionIcon>
						{/* an available update is always actionable, so it survives the icon-column collapse */}
						{onInstallUpdate && <ActionIcon size='lg' variant='filled' color='teal' title='Install update and relaunch' onClick={onInstallUpdate}><TbDownload size={20} /></ActionIcon>}
					</SimpleGrid>
				</Group>

				<Stack ref={controlsRef} gap='xs' style={{ flexShrink: 0 }}>
					<Group justify='center' gap='xs'>
						<ActionIcon
							size='sm'
							variant={shuffleEnabled ? 'filled' : 'default'}
							title={shuffleEnabled ? 'Shuffle on' : 'Shuffle off'}
							aria-pressed={shuffleEnabled}
							onClick={handleToggleShuffle}
						>
							<TbArrowsShuffle size={16} />
						</ActionIcon>
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
						<ActionIcon
							size='sm'
							variant={repeatMode === 'off' ? 'default' : 'filled'}
							title={repeatLabel}
							aria-pressed={repeatMode !== 'off'}
							onClick={handleToggleRepeat}
						>
							<RepeatIcon size={16} />
						</ActionIcon>
					</Group>

					<Stack gap='xs'>
						<Group>
							<ActionIcon size='sm' variant='default'><TbVolume size={16} /></ActionIcon>
							<Box style={{ flex: 1 }}>
								<Slider
									min={0}
									max={100}
									value={pendingVolume ?? playerState?.volume ?? 0}
									step={1}
									disabled={daemonLoading}
									onChange={setPendingVolume}
									onChangeEnd={handleVolumeChangeEnd}
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
											<Text size='xs'>{formatTime(displayedPosition)}</Text>
											<Text size='xs'>-{formatTime(Math.floor(playerState.track_length || 0) - displayedPosition)}</Text>
										</>
								}
							</Group>
							<Slider
								min={0}
								max={Math.floor(playerState?.track_length || 0)}
								value={displayedPosition}
								step={1}
								label={formatTime}
								disabled={daemonLoading}
								onChange={handleScrub}
								onChangeEnd={handleScrubEnd}
							/>
						</Stack>
					</Box>

					{!hideDeviceRow && (
						<Group justify='space-between'>
							<Text size='sm' fw={500}>Device</Text>
							{
								daemonLoading ?
									<Skeleton style={{ flex: 1 }} height={36} /> :
									<Select value='LOCAL DEVICE' style={{ flex: 1 }} data={['LOCAL DEVICE']}></Select>
							}

						</Group>
					)}
				</Stack>
			</Stack>
		</>
	);
}
