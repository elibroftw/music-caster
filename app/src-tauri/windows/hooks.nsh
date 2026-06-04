!define OLD_MC_UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\{FBE8A652-58D6-482D-B6A9-B3D7931CC9C5}_is1"

; Tauri itself calls APP_ASSOCIATE once per file association, e.g.
;   !insertmacro APP_ASSOCIATE "mp3" "MP3" "MP3 - Audio File" \
;     "$INSTDIR\${MAINBINARYNAME}.exe,0" "Open with ${PRODUCTNAME}" \
;     "$INSTDIR\${MAINBINARYNAME}.exe $\"%1$\""

!define MC_EXE "$\"$INSTDIR\${MAINBINARYNAME}.exe$\""
!define MC_ICON "$INSTDIR\${MAINBINARYNAME}.exe,0"

!macro MC_REGISTER_FILE_VERBS FILECLASS

 ; .EXT registry and DefaultIcon are already set via Tauri

	WriteRegStr SHELL_CONTEXT "Software\Classes\${FILECLASS}\shell\open" "MultiSelectModel" "Player"

  WriteRegStr SHELL_CONTEXT "Software\Classes\${FILECLASS}\shell\queue" "" "Queue in ${PRODUCTNAME}"
	WriteRegStr SHELL_CONTEXT "Software\Classes\${FILECLASS}\shell\queue\command" "" `${MC_EXE} -q --shell "%1$"`
  WriteRegStr SHELL_CONTEXT "Software\Classes\${FILECLASS}\shell\queue" "MultiSelectModel" "Player"

	WriteRegStr SHELL_CONTEXT "Software\Classes\${FILECLASS}\shell\play_next" "" `Play next in ${PRODUCTNAME}`
	WriteRegStr SHELL_CONTEXT "Software\Classes\${FILECLASS}\shell\play_next\command" "" `${MC_EXE} -n --shell "%1$"`
  WriteRegStr SHELL_CONTEXT "Software\Classes\${FILECLASS}\shell\play_next" "MultiSelectModel" "Player"
!macroend

!macro MC_UNREGISTER_FILE_VERBS FILECLASS
  !insertmacro APP_ASSOCIATE_REMOVEVERB "${FILECLASS}" "queue"
	!insertmacro APP_ASSOCIATE_REMOVEVERB "${FILECLASS}" "playnext"
!macroend

; Add a Directory (folder) context-menu handler.
!macro MC_REGISTER_DIR_VERB KEY TEXT COMMAND
  !insertmacro APP_ASSOCIATE_ADDVERB "Directory" "${KEY}" "${TEXT}" "${COMMAND}"
  WriteRegStr SHELL_CONTEXT "Software\Classes\Directory\shell\${KEY}" "Icon" "${MC_ICON}"
!macroend

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
  DetailPrint "Registering Music Caster context-menu actions..."

  ; Extra verbs on each audio/playlist file class created by Tauri's APP_ASSOCIATE.
  ; ext / class name / description match the association in tauri.conf.json.
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.MP3"
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.FLAC"
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.M4A"
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.AAC"
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.OGG"
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.OPUS"
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.AIFF"
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.WMA"
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.WAV"
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.MPEG"
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.M3U"
  !insertmacro MC_REGISTER_FILE_VERBS "MusicCaster.M3U8"

  ; Folder (Directory) context-menu handlers.
  !insertmacro MC_REGISTER_DIR_VERB "MusicCasterPlayFolder" "Play with ${PRODUCTNAME}" "${MC_EXE} --shell $\"%1$\""
  !insertmacro MC_REGISTER_DIR_VERB "MusicCasterQueueFolder" "Queue in ${PRODUCTNAME}" "${MC_EXE} -q --shell $\"%1$\""
  !insertmacro MC_REGISTER_DIR_VERB "MusicCasterPlayNextFolder" "Play next in ${PRODUCTNAME}" "${MC_EXE} -n --shell $\"%1$\""

  !insertmacro UPDATEFILEASSOC
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  DetailPrint "Removing Music Caster context-menu actions..."
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.MP3"
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.FLAC"
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.M4A"
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.AAC"
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.OGG"
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.OPUS"
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.AIFF"
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.WMA"
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.WAV"
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.MPEG"
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.M3U"
	!insertmacro MC_UNREGISTER_FILE_VERBS "MusicCaster.M3U8"

  !insertmacro APP_ASSOCIATE_REMOVEVERB "Directory" "MusicCasterPlayFolder"
  !insertmacro APP_ASSOCIATE_REMOVEVERB "Directory" "MusicCasterQueueFolder"
  !insertmacro APP_ASSOCIATE_REMOVEVERB "Directory" "MusicCasterPlayNextFolder"

  !insertmacro UPDATEFILEASSOC
!macroend
