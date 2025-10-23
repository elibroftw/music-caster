import { Button, Checkbox, Group, Modal, Skeleton, Stack, Tabs, TextInput } from '@mantine/core';
import { useContext } from 'react';
import { PlayerStateContext } from '../common/contexts';

interface SettingsModalProps {
	opened: boolean;
	onClose: () => void;
}

export default function SettingsModal({ opened, onClose }: SettingsModalProps) {
	const playerState = useContext(PlayerStateContext);

	return (
		<Modal
			opened={opened}
			onClose={onClose}
			title="Settings"
			size="xl"
			centered
		>
			{playerState?.status === 'NOT_RUNNING' ? (
				<Stack gap="md">
					{[...Array(8)].map((_, i) => <Skeleton key={i} height={40} />)}
				</Stack>
			) : (
			<Tabs defaultValue="general">
				<Tabs.List>
					<Tabs.Tab value="general">General</Tabs.Tab>
					<Tabs.Tab value="queue">Queue</Tabs.Tab>
					<Tabs.Tab value="appearance">Appearance</Tabs.Tab>
					<Tabs.Tab value="library">Music Library</Tabs.Tab>
					<Tabs.Tab value="advanced">Advanced</Tabs.Tab>
				</Tabs.List>

				<Tabs.Panel value="general" pt="md">
					<Stack gap="md">
						<Checkbox label="Auto update" defaultChecked />
						<Checkbox label="Notifications" defaultChecked />
						<Checkbox label="Run on startup" />
						<Checkbox label="Exit app on GUI close" />
						<Checkbox label="Discord presence" />
						<Checkbox label="Folder context menu" defaultChecked />
						<Checkbox label="Remember last folder" />
						<TextInput label="System Audio Delay" defaultValue="0" />
					</Stack>
				</Tabs.Panel>

				<Tabs.Panel value="queue" pt="md">
					<Stack gap="md">
						<Checkbox label="Populate queue on startup" />
						<Checkbox label="Smart queue" defaultChecked />
						<Checkbox label="Reversed play next" />
						<Checkbox label="Show index in queue" />
						<Checkbox label="Always queue library" />
						<Checkbox label="Persistent queue" defaultChecked />
					</Stack>
				</Tabs.Panel>

				<Tabs.Panel value="appearance" pt="md">
					<Stack gap="md">
						<Checkbox label="Save window positions" defaultChecked />
						<Checkbox label="Left-side music controls" />
						<Checkbox label="Show album art" defaultChecked />
						<Checkbox label="Use cover.* for album art" defaultChecked />
						<Checkbox label="Show track number" />
						<Checkbox label="Vertical GUI" />
						<Checkbox label="Mini mode on top" />
						<TextInput label="Track Format" defaultValue="&artist - &title" />
						<TextInput label="On battery resolution" defaultValue="" />
						<TextInput label="Plugged in resolution" defaultValue="" />
					</Stack>
				</Tabs.Panel>

				<Tabs.Panel value="library" pt="md">
					<Stack gap="md">
						<Checkbox label="Scan folders" />
						<TextInput label="Music Directory" placeholder="Select a folder..." />
						<Group>
							<Button variant="light">Add Directory</Button>
							<Button variant="light">Remove Selected</Button>
						</Group>
					</Stack>
				</Tabs.Panel>

				<Tabs.Panel value="advanced" pt="md">
					<Stack gap="md">
						<Checkbox label="Experimental features" />
					</Stack>
				</Tabs.Panel>
			</Tabs>
			)}
		</Modal>
	);
}
