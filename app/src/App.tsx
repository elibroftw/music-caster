import { ActionIcon, AppShell, Burger, Button, Group, Space, Tabs, Text, useComputedColorScheme, useMantineColorScheme } from '@mantine/core';
import { useDisclosure, useHotkeys } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { isTauri } from '@tauri-apps/api/core';
import * as tauriEvent from '@tauri-apps/api/event';
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
import * as tauriLogger from '@tauri-apps/plugin-log';
import { relaunch } from '@tauri-apps/plugin-process';
import * as tauriUpdater from '@tauri-apps/plugin-updater';
import { JSX, lazy, LazyExoticComponent, Suspense, useEffect, useRef, useState } from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import { useTranslation } from 'react-i18next';
import { BsMoonStarsFill } from 'react-icons/bs';
import { ImCross } from 'react-icons/im';
import { IoSunnySharp } from 'react-icons/io5';
import { Navigate, NavLink, Route, Routes } from 'react-router-dom';
import SimpleBar from 'simplebar-react';
import 'simplebar-react/dist/simplebar.min.css';
import classes from './App.module.css';
import { useCookie, useLocalForage } from './common/utils';
import { MusicCasterAPIContext, PlayerStateContext } from './common/contexts';
import LanguageHeaders from './components/LanguageHeaders';
import PlaybackAside from './components/PlaybackAside';
import { ScrollToTop } from './components/ScrollToTop';
import SettingsModal from './components/SettingsModal';
import { useTauriContext } from './tauri/TauriProvider';
import { TitleBar } from './tauri/TitleBar';
import Developer from './views/Developer';
import ExampleView from './views/ExampleView';
import FallbackAppRender from './views/FallbackErrorBoundary';
import FallbackSuspense from './views/FallbackSuspense';
import MusicLibrary from './views/MusicLibrary';
import Queue from './views/Queue';
import MusicCasterAPI, { PlayerState } from './common/commands';
// if some views are large, you can use lazy loading to reduce the initial app load time
const LazyView = lazy(() => import('./views/LazyView'));

// imported views need to be added to the `views` list variable
interface View {
	component: (() => JSX.Element) | LazyExoticComponent<() => JSX.Element>,
	path: string,
	exact?: boolean,
	name: string
}

export default function () {
	const { t } = useTranslation();
	const api = new MusicCasterAPI();
	// check if using custom titlebar to adjust other components
	const { usingCustomTitleBar } = useTauriContext();
	const { toggleColorScheme } = useMantineColorScheme();
	const colorScheme = useComputedColorScheme();
	useHotkeys([['ctrl+J', toggleColorScheme]]);

	// opened is for mobile nav
	const [mobileNavOpened, { toggle: toggleMobileNav }] = useDisclosure();

	const [desktopNavOpenedCookie, setDesktopNavOpenedCookie] = useCookie('desktop-nav-opened', 'true');
	const desktopNavOpened = desktopNavOpenedCookie === 'true';
	const toggleDesktopNav = () => setDesktopNavOpenedCookie(o => o === 'true' ? 'false' : 'true');

	const [settingsOpened, { open: openSettings, close: closeSettings }] = useDisclosure(false);
	const [selectedTrack, setSelectedTrack] = useState<any>(null);
	const [activeTab, setActiveTab] = useState<string | null>('library');
	const [playerState, setPlayerState] = useState<PlayerState | null>(null);

	const [scroller, setScroller] = useState<HTMLElement | null>(null);
	// load preferences using localForage
	const [footersSeen, setFootersSeen, footersSeenLoading] = useLocalForage('footersSeen', {});

	const [navbarClearance, setNavbarClearance] = useState(0);
	const footerRef = useRef<HTMLElement | null>(null);
	useEffect(() => {
		if (footerRef.current) setNavbarClearance(footerRef.current.clientHeight);
	}, [footersSeen]);


	// Tauri event listeners (run on mount)
	if (isTauri()) {
		useEffect(() => {
			const promise = tauriEvent.listen('longRunningThread', ({ payload }: { payload: any }) => {
				tauriLogger.info(payload.message);
			});
			return () => { promise.then(unlisten => unlisten()) };
		}, []);
		// system tray events
		useEffect(() => {
			const promise = tauriEvent.listen('systemTray', ({ payload, ...eventObj }: { payload: { message: string } }) => {
				tauriLogger.info(payload.message);
				// for debugging purposes only
				notifications.show({
					title: '[DEBUG] System Tray Event',
					message: payload.message
				});
			});
			return () => { promise.then(unlisten => unlisten()) };
		}, []);

		// update checker
		useEffect(() => {
			(async () => {
				const update = await tauriUpdater.check();
				if (update) {
					const color = colorScheme === 'dark' ? 'teal' : 'teal.8';
					notifications.show({
						id: 'UPDATE_NOTIF',
						title: t('updateAvailable', { v: update.version }),
						color,
						message: <>
							<Text>{update.body}</Text>
							<Button color={color} style={{ width: '100%' }} onClick={() => update.downloadAndInstall(event => {
								switch (event.event) {
									case 'Started':
										notifications.show({ title: t('installingUpdate', { v: update.version }), message: t('relaunchMsg'), autoClose: false });
										// contentLength = event.data.contentLength;
										// tauriLogger.info(`started downloading ${event.data.contentLength} bytes`);
										break;
									case 'Progress':
										// downloaded += event.data.chunkLength;
										// tauriLogger.info(`downloaded ${downloaded} from ${contentLength}`);
										break;
									case 'Finished':
										// tauriLogger.info('download finished');
										break;
								}
							}).then(relaunch)}>{t('installAndRelaunch')}</Button>
						</>,
						autoClose: false
					});
				}
			})()
		}, []);

		// Handle additional app launches (url, etc.)
		useEffect(() => {
			const promise = tauriEvent.listen('newInstance', async ({ payload, ...eventObj }: { payload: { args: string[], cwd: string } }) => {
				const appWindow = getCurrentWebviewWindow();
				if (!(await appWindow.isVisible())) await appWindow.show();

				if (await appWindow.isMinimized()) {
					await appWindow.unminimize();
					await appWindow.setFocus();
				}

				let args = payload?.args;
				let cwd = payload?.cwd;
				if (args?.length > 1) {

				}
			});
			return () => { promise.then(unlisten => unlisten()) };
		}, []);



		// Player state change listener
		useEffect(() => {

			api.getState().then(s => setPlayerState(s));

			const promise = tauriEvent.listen('playerStateChanged', ({ payload }: { payload: PlayerState }) => {
				tauriLogger.info(`Player state changed`);
				setPlayerState(payload);
			});
			return () => { promise.then(unlisten => unlisten()) };
		}, []);
	}

	const FOOTER_KEY = 'footer[0]';
	const showFooter = FOOTER_KEY && !footersSeenLoading && !(FOOTER_KEY in footersSeen);
	// assume key is always available
	const footerText = t(FOOTER_KEY);

	// hack for global styling the vertical simplebar based on state
	useEffect(() => {
		const el = document.getElementsByClassName('simplebar-vertical')[0];
		if (el instanceof HTMLElement) {
			el.style.marginTop = usingCustomTitleBar ? '100px' : '70px';
			el.style.marginBottom = showFooter ? '50px' : '0px';
		}
	}, [usingCustomTitleBar, showFooter]);

	return (
		<PlayerStateContext.Provider value={playerState}>
			<MusicCasterAPIContext.Provider value={api}>
				<SettingsModal opened={settingsOpened} onClose={closeSettings} />

				{usingCustomTitleBar && <TitleBar />}
				<AppShell padding='md'
					header={{ height: 0 }}
					footer={showFooter ? { height: 60 } : undefined}
					aside={{ width: 350, breakpoint: 'md', collapsed: { desktop: false, mobile: true } }}
					className={classes.appShell}>
					<AppShell.Main>
						{usingCustomTitleBar && <Space h='xl' />}
						<SimpleBar scrollableNodeProps={{ ref: setScroller }} autoHide={false} className={classes.simpleBar}>
							<ErrorBoundary FallbackComponent={FallbackAppRender} /*onReset={_details => resetState()} */ onError={(e: Error) => tauriLogger.error(e.message)}>
								<Tabs value={activeTab} onChange={setActiveTab} >
									<Tabs.List>
										<Tabs.Tab value="queue">Queue</Tabs.Tab>
										<Tabs.Tab value="library">Music Library</Tabs.Tab>
										<Tabs.Tab value="dev">Developer</Tabs.Tab>
									</Tabs.List>
									<Tabs.Panel value="queue" pt="md">
										<Queue />
									</Tabs.Panel>
									<Tabs.Panel value="library" pt="md">
										<MusicLibrary />
									</Tabs.Panel>
									<Tabs.Panel value="dev" pt="md">
										<Developer />
									</Tabs.Panel>
								</Tabs>
							</ErrorBoundary>
							{/* prevent the footer from covering bottom text of a route view */}
							<Space h={showFooter ? 70 : 50} />
							<ScrollToTop scroller={scroller} bottom={showFooter ? 70 : 20} />
						</SimpleBar>
					</AppShell.Main>

					<AppShell.Aside className={classes.titleBarAdjustedHeight} p='md'>
						<PlaybackAside onOpenSettings={openSettings} selectedTrack={selectedTrack} />
					</AppShell.Aside>

					{showFooter &&
						<AppShell.Footer ref={footerRef} p='md' className={classes.footer}>
							{footerText}
							<Button variant='subtle' size='xs' onClick={() => setFootersSeen(prev => ({ ...prev, [FOOTER_KEY]: '' }))}>
								<ImCross />
							</Button>
						</AppShell.Footer>}
				</AppShell>
			</MusicCasterAPIContext.Provider>
		</PlayerStateContext.Provider>
	);
}
