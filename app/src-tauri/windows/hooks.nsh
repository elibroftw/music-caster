!define OLD_MC_UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\{FBE8A652-58D6-482D-B6A9-B3D7931CC9C5}_is1"

!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Checking for a previous Music Caster installation..."

  ClearErrors
  ReadRegStr $0 HKCU "${OLD_MC_UNINSTALL_KEY}" "QuietUninstallString"
  ${If} $0 == ""
    ReadRegStr $0 HKCU "${OLD_MC_UNINSTALL_KEY}" "UninstallString"
  ${EndIf}

  ${If} $0 != ""
		DetailPrint "Uninstalling Music Caster v5 ($0)..."
		ExecWait '$0' $2
		DetailPrint "Previous Music Caster uninstaller exited with code $2."
  ${EndIf}
!macroend

!macro NSIS_HOOK_POSTINSTALL
  DetailPrint "Registering Music Caster file associations..."
  !insertmacro RegisterFileAssociations "$INSTDIR\${MAINBINARYNAME}.exe"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  DetailPrint "Removing Music Caster file associations..."
  !insertmacro UnregisterFileAssociations
!macroend
