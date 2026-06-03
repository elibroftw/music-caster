import { Button, Checkbox, Group, Modal, SimpleGrid, Stack, Tabs, TextInput } from '@mantine/core';
import { useContext } from 'react';
import { PlayerStateContext } from '../common/contexts';

interface SettingsModalProps {
	opened: boolean;
	onClose: () => void;
}

export default function SettingsModal({ opened, onClose }: SettingsModalProps) {
	return (
		<Modal
			opened={opened}
			onClose={onClose}
			title='Settings'
			size='auto'
			centered
		>
			<Tabs defaultValue='general' mih={320}>
				<Tabs.List>
					<Tabs.Tab value='general'>General</Tabs.Tab>
					<Tabs.Tab value='queue'>Queue</Tabs.Tab>
					<Tabs.Tab value='appearance'>Appearance</Tabs.Tab>
					<Tabs.Tab value='library'>Music Library</Tabs.Tab>
					<Tabs.Tab value='advanced'>Advanced</Tabs.Tab>
					<Tabs.Tab value='changelog'>Changelog</Tabs.Tab>
				</Tabs.List>

				<Tabs.Panel value='general' pt='md'>
					<SimpleGrid cols={2} spacing='md'>
						<Checkbox label='Auto update' defaultChecked />
						<Checkbox label='Notifications' defaultChecked />
						<Checkbox label='Run on startup' />
						<Checkbox label='Exit app on GUI close' />
						<Checkbox label='Discord presence' />
						<Checkbox label='Folder context menu' defaultChecked />
						<Checkbox label='Remember last folder' />
						<TextInput label='System Audio Delay' defaultValue='0' />
					</SimpleGrid>
				</Tabs.Panel>

				<Tabs.Panel value='queue' pt='md'>
					<SimpleGrid cols={2} spacing='md'>
						<Checkbox label='Populate queue on startup' />
						<Checkbox label='Smart queue' defaultChecked />
						<Checkbox label='Reversed play next' />
						<Checkbox label='Show index in queue' />
						<Checkbox label='Always queue library' />
						<Checkbox label='Persistent queue' defaultChecked />
					</SimpleGrid>
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

				<Tabs.Panel value='advanced' pt='md'>
					<Stack gap='md'>
						<Checkbox label='Experimental features' />
					</Stack>
				</Tabs.Panel>

				<Tabs.Panel value='changelog' pt='md'>
					TODO: SHOW CHANGELOG.TXT
				</Tabs.Panel>
			</Tabs>
		</Modal>
	);
}
