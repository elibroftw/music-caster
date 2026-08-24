import { Alert, Button, Checkbox, Group, Modal, SimpleGrid, Stack, Tabs, Text, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useCallback, useContext, useEffect, useState } from 'react';
import type { BooleanSetting, DaemonSettings } from '../common/commands';
import { MusicCasterAPIContext } from '../common/contexts';
import { fmtError, IS_DEVELOPMENT } from '../common/utils';
import Developer from '../views/Developer';

interface SettingsModalProps {
	opened: boolean;
	onClose: () => void;
}

export default function SettingsModal({ opened, onClose }: SettingsModalProps) {
	const api = useContext(MusicCasterAPIContext)!;
	const [settings, setSettings] = useState<DaemonSettings | null>(null);
	const [settingsError, setSettingsError] = useState<string | null>(null);

	const loadSettings = useCallback(async () => {
		try {
			setSettings(await api.getSettings());
			setSettingsError(null);
		} catch (error) {
			setSettings(null);
			setSettingsError(fmtError(error));
		}
	}, [api]);

	// re-read on every open, so the modal cannot show a value the tray or the
	// daemon's own GUI has changed since last time
	useEffect(() => {
		if (opened) loadSettings();
	}, [opened]);

	const toggleSetting = async (key: BooleanSetting, value: boolean) => {
		// reflect the click right away, then let the daemon's copy have the last word
		setSettings(current => current && { ...current, [key]: value });
		try {
			// the daemon answers 'true' only when it accepted the change
			if (await api.changeSetting(key, value) !== 'true') throw new Error('the daemon rejected the change');
		} catch (error) {
			notifications.show({
				title: 'Could not save setting',
				message: fmtError(error),
				color: 'red'
			});
		}
		// the daemon layers its own rules on top (persistent queue and populate on
		// startup switch each other off), so re-read instead of trusting the click
		await loadSettings();
	};

	const settingCheckbox = (key: BooleanSetting, label: string) => (
		<Checkbox
			label={label}
			checked={settings?.[key] ?? false}
			disabled={settings === null}
			onChange={event => toggleSetting(key, event.currentTarget.checked)}
		/>
	);

	return (
		<Modal
			opened={opened}
			onClose={onClose}
			title='Settings'
			size='auto'
			centered
		>
			<Tabs defaultValue='queue' mih={320}>
				<Tabs.List>
					{/* <Tabs.Tab value='general'>General</Tabs.Tab> */}
					<Tabs.Tab value='queue'>Queue</Tabs.Tab>
					{/* <Tabs.Tab value='appearance'>Appearance</Tabs.Tab> */}
					{/* <Tabs.Tab value='library'>Music Library</Tabs.Tab> */}
					{IS_DEVELOPMENT && <Tabs.Tab value='developer'>Developer</Tabs.Tab>}
				</Tabs.List>

				<Tabs.Panel value='general' pt='md'>
					<SimpleGrid cols={2} spacing='md'>
						<Checkbox label='Run on startup' />
						<Checkbox label='Exit app on GUI close' />
						<Checkbox label='Discord presence' />
						<Checkbox label='Folder context menu' defaultChecked />
						<Checkbox label='Remember last folder' />
						<TextInput label='System Audio Delay' defaultValue='0' />
					</SimpleGrid>
				</Tabs.Panel>

				<Tabs.Panel value='queue' pt='md'>
					<Stack gap='md'>
						{settingsError && (
							<Alert color='red' variant='light' title='Settings unavailable'>
								<Stack gap='xs' align='flex-start'>
									<Text size='xs'>{settingsError}</Text>
									<Button size='xs' variant='light' color='red' onClick={loadSettings}>Retry</Button>
								</Stack>
							</Alert>
						)}
						<SimpleGrid cols={2} spacing='md'>
							{settingCheckbox('populate_queue_startup', 'Populate queue on startup')}
							{settingCheckbox('smart_queue', 'Smart queue')}
							{settingCheckbox('reversed_play_next', 'Reversed play next')}
							{settingCheckbox('show_queue_index', 'Show index in queue')}
							{settingCheckbox('queue_library', 'Always queue library')}
							{settingCheckbox('persistent_queue', 'Persistent queue')}
						</SimpleGrid>
					</Stack>
				</Tabs.Panel>

				<Tabs.Panel value='appearance' pt='md'>
					<SimpleGrid cols={2} spacing='md'>
						<Checkbox label='Save window positions' defaultChecked />
						<Checkbox label='Left-side music controls' />
						<Checkbox label='Show album art' defaultChecked />
						<Checkbox label='Use cover.* for album art' defaultChecked />
						<Checkbox label='Show track number' />
						<Checkbox label='Vertical GUI' />
						<Checkbox label='Mini mode on top' />
						<TextInput label='Track Format' defaultValue='&artist - &title' />
						<TextInput label='On battery resolution' defaultValue='' />
						<TextInput label='Plugged in resolution' defaultValue='' />
					</SimpleGrid>
				</Tabs.Panel>

				<Tabs.Panel value='library' pt='md'>
					<Stack gap='md'>
						<Checkbox label='Scan folders' />
						<TextInput label='Music Directory' placeholder='Select a folder...' />
						<Group>
							<Button variant='light'>Add Directory</Button>
							<Button variant='light'>Remove Selected</Button>
						</Group>
					</Stack>
				</Tabs.Panel>

				{IS_DEVELOPMENT && (
					<Tabs.Panel value='developer' pt='md'>
						<Developer />
					</Tabs.Panel>
				)}
			</Tabs>
		</Modal>
	);
}
