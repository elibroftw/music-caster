import { Alert, Button, Checkbox, Group, Modal, Paper, Stack, Text, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { open as openFileDialog } from '@tauri-apps/plugin-dialog';
import { useContext, useEffect, useState } from 'react';
import { TbSearch, TbTrash, TbUpload } from 'react-icons/tb';
import { MusicCasterAPIContext } from '../common/contexts';
import type { TrackMetadata } from '../common/commands';
import { fmtError } from '../common/utils';

type ArtAction = 'unchanged' | 'replace' | 'remove';

interface ArtworkData {
	data: string;
	mime: string;
}

interface MetadataEditorModalProps {
	filePath: string | null;
	onClose: () => void;
	onSaved?: () => void;
}

const ART_PREVIEW_SIZE = 150;

export default function MetadataEditorModal({ filePath, onClose, onSaved }: MetadataEditorModalProps) {
	const api = useContext(MusicCasterAPIContext)!;
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState<string | null>(null);
	const [title, setTitle] = useState('');
	const [artist, setArtist] = useState('');
	const [album, setAlbum] = useState('');
	const [genre, setGenre] = useState('');
	const [trackNumber, setTrackNumber] = useState('');
	const [explicit, setExplicit] = useState(false);
	const [art, setArt] = useState<ArtworkData | null>(null);
	const [artAction, setArtAction] = useState<ArtAction>('unchanged');
	const [searching, setSearching] = useState(false);
	const [saving, setSaving] = useState(false);

	useEffect(() => {
		if (filePath === null) return;
		let cancelled = false;
		(async () => {
			setLoading(true);
			setLoadError(null);
			try {
				const metadata: TrackMetadata = await api.getMetadata(filePath);
				if (cancelled) return;
				setTitle(metadata.title);
				setArtist(metadata.artist);
				setAlbum(metadata.album);
				setGenre(metadata.genre ?? '');
				const trackPlace = metadata.track_number == null || metadata.track_total == null
					? metadata.track_number ?? ''
					: `${metadata.track_number}/${metadata.track_total}`;
				setTrackNumber(trackPlace);
				setExplicit(metadata.explicit);
				setArt(metadata.art == null
					? null
					: { data: metadata.art, mime: metadata.mime ?? 'image/jpeg' });
				setArtAction('unchanged');
			} catch (error) {
				if (!cancelled) {
					setLoadError(fmtError(error));
				}
			} finally {
				if (!cancelled) setLoading(false);
			}
		})();
		return () => { cancelled = true; };
	}, [filePath]);

	const handleSelectArtwork = async () => {
		const selected = await openFileDialog({
			title: 'Select artwork',
			filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'bmp', 'gif', 'webp'] }],
		});
		if (typeof selected !== 'string') return;
		try {
			const artwork = await api.readArtwork(selected);
			setArt({ data: artwork.art, mime: artwork.mime });
			setArtAction('replace');
		} catch (error) {
			notifications.show({ title: 'Could not read image', message: fmtError(error), color: 'red' });
		}
	};

	const handleSearchArtwork = async () => {
		setSearching(true);
		try {
			const artwork = await api.searchArtwork(title, artist);
			setArt({ data: artwork.art, mime: artwork.mime });
			setArtAction('replace');
		} catch (error) {
			notifications.show({ title: 'Could not find artwork', message: fmtError(error), color: 'red' });
		} finally {
			setSearching(false);
		}
	};

	const handleRemoveArtwork = () => {
		setArt(null);
		setArtAction('remove');
	};

	const handleSave = async () => {
		if (filePath === null) return;
		setSaving(true);
		try {
			await api.setMetadata(filePath, {
				title,
				artist,
				album,
				genre,
				track_number: trackNumber,
				explicit,
				...(artAction === 'replace' && art !== null ? { art: art.data, mime: art.mime } : {}),
				...(artAction === 'remove' ? { remove_art: true } : {}),
			});
			notifications.show({ message: 'Metadata saved', color: 'green' });
			onSaved?.();
			onClose();
		} catch (error) {
			notifications.show({ title: 'Could not save metadata', message: fmtError(error), color: 'red' });
		} finally {
			setSaving(false);
		}
	};

	const artPreview = art !== null ? (
		<img
			src={`data:${art.mime};base64,${art.data}`}
			alt='Album art'
			width={ART_PREVIEW_SIZE}
			height={ART_PREVIEW_SIZE}
			style={{ objectFit: 'cover', borderRadius: 'var(--mantine-radius-sm)', display: 'block', flexShrink: 0 }}
		/>
	) : (
		<Paper
			withBorder
			w={ART_PREVIEW_SIZE}
			h={ART_PREVIEW_SIZE}
			style={{ display: 'grid', placeItems: 'center', flexShrink: 0 }}
		>
			<Text size='xs' c='dimmed'>No artwork</Text>
		</Paper>
	);

	return (
		<Modal
			opened={filePath !== null}
			onClose={onClose}
			title='Edit Metadata'
			centered
		>
			<Stack gap='md'>
				{filePath !== null && (
					<Text size='xs' c='dimmed' lineClamp={1} title={filePath}>{filePath}</Text>
				)}
				{loadError !== null && (
					<Alert color='red' variant='light' title='Could not read metadata'>{loadError}</Alert>
				)}
				<TextInput
					label='Title'
					value={title}
					onChange={e => setTitle(e.currentTarget.value)}
					disabled={loading}
				/>
				<TextInput
					label='Artist'
					value={artist}
					onChange={e => setArtist(e.currentTarget.value)}
					disabled={loading}
				/>
				<TextInput
					label='Album'
					value={album}
					onChange={e => setAlbum(e.currentTarget.value)}
					disabled={loading}
				/>
				<TextInput
					label='Genre'
					value={genre}
					onChange={e => setGenre(e.currentTarget.value)}
					disabled={loading}
				/>
				<TextInput
					label='Track Number'
					placeholder='e.g. 7 or 7/12'
					value={trackNumber}
					onChange={e => setTrackNumber(e.currentTarget.value)}
					disabled={loading}
				/>
				<Checkbox
					label='Explicit'
					checked={explicit}
					onChange={e => setExplicit(e.currentTarget.checked)}
					disabled={loading}
				/>
				<Group align='stretch' gap='md'>
					{artPreview}
					<Stack gap='xs' justify='center' style={{ flex: 1, minWidth: 0 }}>
						<Button
							variant='default'
							leftSection={<TbUpload size={16} />}
							onClick={handleSelectArtwork}
							disabled={loading}
						>
							Select artwork
						</Button>
						<Button
							variant='default'
							leftSection={<TbSearch size={16} />}
							onClick={handleSearchArtwork}
							loading={searching}
							disabled={loading || title.trim() === ''}
						>
							Search artwork
						</Button>
						<Button
							variant='default'
							color='red'
							leftSection={<TbTrash size={16} />}
							onClick={handleRemoveArtwork}
							disabled={loading || art === null}
						>
							Remove artwork
						</Button>
					</Stack>
				</Group>
				<Group justify='flex-end'>
					<Button variant='default' onClick={onClose}>Cancel</Button>
					<Button
						onClick={handleSave}
						loading={saving}
						disabled={loading || loadError !== null}
					>
						Save
					</Button>
				</Group>
			</Stack>
		</Modal>
	);
}
