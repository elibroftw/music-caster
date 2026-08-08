# Music Caster Migration Bootstrapper

Older running Music Caster instances will download the first _arbitrary_ exe in a release thinking it is a setup.
This executable is to be released alongside Tauri release files such that old update logic still results in a user successfully upgrading from v5 to v6.
This bootstrapper will do the following:

1. Check for latest MSI installer link
2. Download MSI and run it, waiting for the install to finish
3. In parallel run uninstaller
4. Launch the newly installed Music Caster
5. Self exit (if everything goes according to plan)

The bootstrapper is responsible for relaunching Music Caster. The old client appends
`&& Music Caster.exe` to the command it uses to start this executable, but that path no longer
exists once the v5 uninstaller has run, so the app never comes back on its own.

Alternatively, might look into customizing NSIS to launch the old uninstaller.
