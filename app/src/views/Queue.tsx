import { ActionIcon, Badge, Flex, Paper, ScrollArea, Skeleton, Stack, Text } from '@mantine/core';
import { useElementSize } from '@mantine/hooks';
import { openUrl, revealItemInDir } from '@tauri-apps/plugin-opener';
import Database from '@tauri-apps/plugin-sql';
import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { TbClearAll } from 'react-icons/tb';
import { PlayAction } from '../common/commands';
import { MusicCasterAPIContext, PlayerStateContext } from '../common/contexts';
import { formatTime, formatTrackPlace } from '../common/format';
import { ContextMenu, useContextMenu } from '../components/ContextMenu';
import MetadataEditorModal from '../components/MetadataEditorModal';
import TrackContextMenu from '../components/TrackContextMenu';
import classes from './Queue.module.css';

// every row is this tall regardless of title length: padding plus two lines of
// `sm` text. skeletons match so the queue doesn't jump when the daemon comes up
const ROW_HEIGHT = 72;
const ROW_PADDING = 7;
// the album art slot is square at the row's content height
const ART_SIZE = ROW_HEIGHT - 2 * ROW_PADDING;
// the daemon resolves url metadata on a background thread, so a url queued a moment ago
// has no db row yet: re-read the db this many times, this far apart, while art is missing
const ART_RETRIES = 3;
const ART_RETRY_MS = 2000;

const isUrl = (uri: string) => uri.startsWith('http');

/** the video id shared by every form of a youtube link, or null for any other url */
function youtubeId(uri: string): string | null {
	try {
		const { hostname, pathname, searchParams } = new URL(uri);
		if (hostname === 'youtu.be') return pathname.slice(1) || null;
		if (!/(^|\.)youtube\.com$/.test(hostname)) return null;
		if (pathname === '/watch') return searchParams.get('v');
		return /^\/(?:embed|shorts|v|watch)\/([^/?]+)/.exec(pathname)?.[1] ?? null;
	} catch {
		// not a parseable url: nothing to match a url_metadata row on
		return null;
	}
}


export default function Queue() {
	const { t } = useTranslation();
	const playerState = useContext(PlayerStateContext);
	const [contextMenuTrigger, setContextMenuTrigger] = useContextMenu<number>();

	const viewportRef = useRef<HTMLDivElement>(null);
	const targetRef = useRef<HTMLDivElement>(null);
	// narrow queues (not necessarily narrow windows: the aside also eats width) have
	// no room for the album art slot
	const { ref: queueRef, width: queueWidth } = useElementSize();
	const hideArt = queueWidth < 300;

	const api = useContext(MusicCasterAPIContext)!;

	const [editingUri, setEditingUri] = useState<string | null>(null);
	// bumped after a metadata save so the daemon-served thumbnails (sent with a
	// long max-age) aren't served from the browser cache
	const [artVersion, setArtVersion] = useState(0);

	const queuePosition = playerState?.queue_position ?? 0;
	// tracked as a boolean so the queue only re-renders when the daemon comes up
	// or goes away, not on every play/pause status change
	const daemonDown = playerState === null || playerState.status === 'NOT_RUNNING';

	// the daemon serves per-file cover thumbnails at /file/?path=...&thumbnail_only=true.
	// resolve one URL to learn the daemon's base (and api key suffix), then build every
	// row's URL from it locally instead of one IPC round-trip per track
	const [artUrlTemplate, setArtUrlTemplate] = useState<string | null>(null);
	useEffect(() => {
		(async () => {
			try {
				setArtUrlTemplate(await api.getFileUrl('DEFAULT_ART', true));
			} catch {
				// daemon not up yet: rows simply render without art
			}
		})();
	}, [daemonDown]);
	// cover urls for http queue items, keyed by the url_metadata row's src and, for youtube,
	// by the video id too: a queued youtu.be or shorts link shares the canonical row
	const [urlArt, setUrlArt] = useState<Map<string, string>>(new Map());
	// http URIs have no local file for the daemon to read a cover from: their cover is the
	// remote thumbnail the daemon stored in url_metadata
	const artUrl = (uri: string) => {
		if (isUrl(uri)) {
			const id = youtubeId(uri);
			return urlArt.get(uri) ?? (id === null ? undefined : urlArt.get(id));
		}
		if (artUrlTemplate === null) return undefined;
		return `${artUrlTemplate.replace('path=DEFAULT_ART', `path=${encodeURIComponent(uri)}`)}&v=${artVersion}`;
	};

	// title/artist per file path from the daemon's library db, keyed with posix separators
	// (queue URIs may use backslashes). rows without a db entry (urls, unindexed files)
	// fall back to the daemon-formatted single title
	const [dbMeta, setDbMeta] = useState<Map<string, { title: string, artist: string }>>(new Map());
	const loadDbMeta = useCallback(async () => {
		try {
			const db = await Database.load('sqlite:music_caster.db');
			const rows = await db.select<{ file_path: string, title: string, artist: string }[]>(
				'SELECT file_path, title, artist FROM file_metadata');
			setDbMeta(new Map(rows.map(row => [row.file_path.replaceAll('\\', '/'), row])));
			const urlRows = await db.select<{ src: string, id: string | null, type: string | null, album_cover_url: string }[]>(
				'SELECT src, id, type, album_cover_url FROM url_metadata WHERE album_cover_url IS NOT NULL');
			setUrlArt(new Map(urlRows.flatMap(row => {
				const keys = row.type === 'youtube' && row.id ? [row.src, row.id] : [row.src];
				return keys.map(key => [key, row.album_cover_url] as [string, string]);
			})));
		} catch {
			// db missing or table absent: keep whatever we had and rely on the fallback
		}
	}, []);
	const queueKey = JSON.stringify(playerState?.queue);
	const [artRetries, setArtRetries] = useState(0);
	useEffect(() => {
		setArtRetries(0);
		loadDbMeta();
	}, [queueKey, loadDbMeta]);

	// a url the daemon has not finished resolving has no cover yet: give it a beat and
	// re-read, so it fills in without waiting on the next queue change
	useEffect(() => {
		if (artRetries >= ART_RETRIES) return;
		const pending = playerState?.queue.some(track => isUrl(track[0]) && artUrl(track[0]) === undefined);
		if (!pending) return;
		const timeout = setTimeout(() => {
			setArtRetries(retries => retries + 1);
			loadDbMeta();
		}, ART_RETRY_MS);
		return () => clearTimeout(timeout);
	}, [queueKey, urlArt, artRetries, loadDbMeta]);

	const queueRendered = useMemo(
		() => {
			// no state yet, or the daemon is down: genuinely still loading
			if (playerState === null || playerState.status === 'NOT_RUNNING') return (
				[...Array(100)].map((_, index) => (
					<Skeleton key={index} height={ROW_HEIGHT} />
				))
			);

			if (playerState.queue.length === 0) return (
				<>
					{[...Array(10)].map((_, index) => (
						<Skeleton key={index} height={ROW_HEIGHT} animate={false} />
					))}
				</>
			);

			return playerState.queue.map((track, index) => {
				const meta = dbMeta.get(track[0].replaceAll('\\', '/'));
				const trackPlace = formatTrackPlace(track[3], track[4]);
				return (
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
					p={ROW_PADDING}
					h={ROW_HEIGHT}
					withBorder
					style={{
						cursor: 'pointer',
						// the title is clamped to two lines, so a long one can't outgrow the fixed height
						overflow: 'hidden',
						backgroundColor: index === queuePosition ? 'var(--mantine-color-blue-light)' : undefined
					}}
					onClick={() => onTrackClick(index - queuePosition)}
				>
					<Flex gap='md' align='stretch' h='100%'>
						{!hideArt && (
							<div style={{ width: ART_SIZE, flexShrink: 0 }}>
								{artUrl(track[0]) && (
									// lazy so only the covers scrolled into view are fetched
									<img
										src={artUrl(track[0])}
										alt=''
										width={ART_SIZE}
										height={ART_SIZE}
										loading='lazy'
										style={{ objectFit: 'cover', borderRadius: 'var(--mantine-radius-sm)', display: 'block' }}
									/>
								)}
							</div>
						)}
						{/* queue index badge in its own column between the art and the track text;
						    the negative margins fully collapse the row's md gap on the art side
						    and leave 4px before the text. with the art hidden the badge is the
						    first element, so the left pull-in must not apply */}
						<Flex direction='column' justify='center' style={{ flexShrink: 0, marginLeft: hideArt ? undefined : 'calc(-1 * var(--mantine-spacing-md))', marginRight: 'calc(4px - var(--mantine-spacing-md))' }}>
							<Badge size='sm' variant='light' color={index === queuePosition ? 'blue' : 'gray'}>
								{index - queuePosition}
							</Badge>
						</Flex>
						{meta ? (
							// db metadata: track name over artist, one point larger/smaller than the sm base
							<Stack gap={0} style={{ flex: 1, minWidth: 0, alignSelf: 'center' }}>
								<Text fz={15} fw={500} lineClamp={1} title={meta.title}>{meta.title}</Text>
								<Text fz={13} c='dimmed' lineClamp={1} title={meta.artist}>{meta.artist}</Text>
							</Stack>
						) : (
							<Text size='sm' fw={500} lineClamp={2} title={track[1]} style={{ flex: 1, minWidth: 0, wordBreak: 'break-word', alignSelf: 'center' }}>{track[1]}</Text>
						)}
						<Stack gap={0} align='flex-end' style={{ flexShrink: 0, alignSelf: 'center' }}>
							<Text size='sm' c='dimmed' style={{ whiteSpace: 'nowrap' }}>
								{track[2] == null ? '' : formatTime(track[2])}
							</Text>
							{trackPlace !== null && (
								<Text size='sm' c='dimmed' style={{ whiteSpace: 'nowrap' }}>{trackPlace}</Text>
							)}
						</Stack>
					</Flex>
				</Paper>);
			});
		}, [JSON.stringify(playerState?.queue), queuePosition, daemonDown, artUrlTemplate, dbMeta, urlArt, hideArt, artVersion]);

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

	const handleCopyUris = () => {
		const uri = playerState!.queue[contextMenuTrigger!.item]![0];
		navigator.clipboard.writeText(uri);
	};

	const triggerUri = contextMenuTrigger !== null
		? playerState?.queue[contextMenuTrigger.item]?.[0]
		: undefined;
	const triggerIsUrl = triggerUri !== undefined && isUrl(triggerUri);

	// a url has no file to reveal, so the menu opens it in the browser instead
	const handleShowFile = async () => {
		if (triggerUri === undefined) return;
		if (triggerIsUrl) await openUrl(triggerUri);
		else await revealItemInDir(triggerUri);
	};

	const handleEditMetadata = () => {
		if (triggerUri !== undefined && !triggerIsUrl) {
			setEditingUri(triggerUri);
		}
	};

	const handleMetadataSaved = () => {
		loadDbMeta();
		setArtVersion(version => version + 1);
	};

	const handleRemove = () => {
		if (contextMenuTrigger?.item !== undefined) {
			api.modifyQueue([contextMenuTrigger.item], 'remove');
		}
	};

	const queueEmpty = daemonDown || playerState!.queue.length === 0;

	return (
		// the button sits outside the ScrollArea so it stays put while the
		// queue auto-scrolls to the current track
		<Stack ref={queueRef} className={classes.tab} gap='xs'>
			<MetadataEditorModal
				filePath={editingUri}
				onClose={() => setEditingUri(null)}
				onSaved={handleMetadataSaved}
			/>
			<ScrollArea style={{ flex: 1, minHeight: 0 }} viewportRef={viewportRef}>
				{/* bottom padding keeps the last track reachable from under the floating button */}
				<Paper shadow='sm' p='md' pb={60}>
					<Stack gap='xs'>
						<ContextMenu trigger={contextMenuTrigger} offsetLeft={70} offsetTop={-75}>
							<TrackContextMenu
								isUrl={triggerIsUrl}
								onEditMetadata={triggerUri !== undefined && !triggerIsUrl ? handleEditMetadata : undefined}
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
			<ActionIcon
				className={classes.clearQueue}
				// inline: mantine's own unlayered `position: relative` on the ActionIcon root has the
				// same specificity as a module class and wins on bundle order
				style={{ position: 'absolute', right: 'var(--mantine-spacing-md)', bottom: 'var(--mantine-spacing-xs)', zIndex: 2 }}
				variant='default'
				size='lg'
				title={t('Clear queue')}
				aria-label='Clear queue'
				disabled={queueEmpty}
				onClick={() => api.clearQueue()}
			>
				<TbClearAll size={20} />
			</ActionIcon>
		</Stack>
	);
}
