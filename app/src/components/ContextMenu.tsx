import { Button, Menu } from '@mantine/core';
import { useWindowEvent } from '@mantine/hooks';
import { Dispatch, PropsWithChildren, SetStateAction, useEffect, useState } from 'react';

interface ContextMenuTrigger<T> {
	item: T,
	x: number,
	y: number
}

interface useContextMenuOptions {
	showOnClick?: boolean;
}

/**
 * Use this hook in conjunction with the ContextMenu component
 * const [contextMenuTrigger, setContextMenuTrigger] = useContextMenu<number>();
 * onContextMenu={e => {
 * 	e.preventDefault();
 *	setContextMenuTrigger({
 *  item: index,
 *  x: e.clientX,
 *  y: e.clientY,
 * });
 * }}
 * <ContextMenu trigger={contextMenuTrigger} offsetLeft={70} offsetTop={-75}><Dropdown></ContextMenu>
 */
export function useContextMenu<T>({ showOnClick }: useContextMenuOptions = { showOnClick: false }): [ContextMenuTrigger<T> | null, Dispatch<SetStateAction<ContextMenuTrigger<T> | null>>] {
	const [menuTrigger, setMenuTrigger] = useState<ContextMenuTrigger<T> | null>(null);
	useEffect(() => {
		const closeMenu = () => setMenuTrigger(null);
		const closeWhenHidden = () => {
			if (document.visibilityState === 'hidden') closeMenu();
		};

		// A controlled Mantine menu will otherwise remain open when its window or
		// browser tab loses focus, and reappear when the user returns.
		window.addEventListener('blur', closeMenu);
		window.addEventListener('pagehide', closeMenu);
		window.addEventListener('resize', closeMenu);
		window.addEventListener('scroll', closeMenu, true);
		document.addEventListener('visibilitychange', closeWhenHidden);
		return () => {
			window.removeEventListener('blur', closeMenu);
			window.removeEventListener('pagehide', closeMenu);
			window.removeEventListener('resize', closeMenu);
			window.removeEventListener('scroll', closeMenu, true);
			document.removeEventListener('visibilitychange', closeWhenHidden);
		};
	}, []);
	// Listen in the window's capture phase. Components such as tabs may stop the
	// event while it bubbles, but changing views must still dismiss an open menu.
	useWindowEvent('click', event => {
		if (menuTrigger && (!showOnClick || event.clientX !== menuTrigger.x || event.clientY !== menuTrigger.y)) {
			setMenuTrigger(null);
		}
	}, true);
	useWindowEvent('contextmenu', event => {
		if (menuTrigger && (event.clientX !== menuTrigger.x || event.clientY !== menuTrigger.y)) {
			setMenuTrigger(null);
		}
	}, true);
	useWindowEvent('keydown', event => {
		if (event.key === 'Escape') setMenuTrigger(null);
	}, true);
	return [menuTrigger, setMenuTrigger];
}

interface ContextMenuProps<T> extends PropsWithChildren {
	offsetLeft?: number;
	offsetTop?: number;
	trigger: ContextMenuTrigger<T> | null;
}

/// use the useContextMenu hook to set the trigger
export function ContextMenu<T>({ trigger, children, offsetLeft = 0, offsetTop = 0 }: ContextMenuProps<T>) {
	return (
		<Menu opened={trigger !== null} key={JSON.stringify(trigger)}>
			<Menu.Target>
				<Button unstyled
					style={{
						position: 'absolute',
						width: 0,
						height: 0,
						padding: 0,
						border: 0,
						left: (trigger?.x ?? 0) + offsetLeft,
						top: (trigger?.y ?? 0) + offsetTop,
					}} />
			</Menu.Target>
			{children}
		</Menu>
	);
}
