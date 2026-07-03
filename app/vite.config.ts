import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer';
// https://vitejs.dev/config/
// https://tauri.app/v1/guides/getting-started/setup/vite#create-the-frontend
export default defineConfig({
	plugins: [
		react({
			babel: {
				plugins: ['babel-plugin-react-compiler']
			}
		}),
		visualizer(),
		// removeConsole({includes: ['log', 'assert', 'info', 'error']})
	],
	// prevent vite from obscuring rust errors
	clearScreen: false,
	// Tauri expects a fixed port, fail if that port is not available
	server: {
		port: 1420,
		strictPort: true,
		// open in browser if not running with tauri
		open: process.env.TAURI_ENV_ARCH === undefined
	},
	// to make use of `TAURI_PLATFORM`, `TAURI_ARCH`, `TAURI_FAMILY`,
	// `TAURI_PLATFORM_VERSION`, `TAURI_PLATFORM_TYPE` and `TAURI_DEBUG`
	// env variables
	envPrefix: ['VITE_', 'TAURI_ENV_'],

	build: {
		// Tauri supports es2021
		target: ['es2021', 'chrome100', 'safari13'],
		// don't minify for debug builds
		minify: !process.env.TAURI_ENV_DEBUG ? 'oxc' : false,
		// produce sourcemaps for debug builds
		sourcemap: !!process.env.TAURI_ENV_DEBUG,
		outDir: 'build',
	}
})
