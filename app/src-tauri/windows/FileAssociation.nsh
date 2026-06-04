; FileAssociation.nsh - Windows Registry Handlers for Music Caster
; Ported from Python registry code

!ifndef FILE_ASSOCIATION_NSH
!define FILE_ASSOCIATION_NSH

!macro RegisterFileAssociations EXE_PATH
  ; Register Music Caster as a program to open audio files and folders

  ; Define variables
  !define MC_FILE "MusicCaster_file"
  !define CLASSES_PATH "SOFTWARE\Classes"

  ; Create URL protocol handler (music-caster://)
  WriteRegStr HKCU "${CLASSES_PATH}\music-caster" "" "URL:music-caster Protocol"
  WriteRegStr HKCU "${CLASSES_PATH}\music-caster" "URL Protocol" ""
  WriteRegStr HKCU "${CLASSES_PATH}\music-caster\DefaultIcon" "" '"${EXE_PATH}"'
  WriteRegStr HKCU "${CLASSES_PATH}\music-caster\shell\open\command" "" '"${EXE_PATH}" --urlprotocol "%1"'

  ; Create Audio File type
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}" "" "Audio File"
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\DefaultIcon" "" "${EXE_PATH}"

  ; Create "Play with Music Caster" context menu (open handler)
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\open" "" "Play with Music Caster"
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\open" "MultiSelectModel" "Player"
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\open" "Icon" "${EXE_PATH}"
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\open\command" "" '"${EXE_PATH}" --shell "%1"'

  ; Create "Queue in Music Caster" context menu
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\queue" "" "Queue in Music Caster"
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\queue" "MultiSelectModel" "Player"
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\queue" "Icon" "${EXE_PATH}"
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\queue\command" "" '"${EXE_PATH}" -q --shell "%1"'

  ; Create "Play next in Music Caster" context menu
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\play_next" "" "Play next in Music Caster"
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\play_next" "MultiSelectModel" "Player"
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\play_next" "Icon" "${EXE_PATH}"
  WriteRegStr HKCU "${CLASSES_PATH}\${MC_FILE}\shell\play_next\command" "" '"${EXE_PATH}" -n --shell "%1"'

  ; Register file extensions
  !insertmacro RegisterExtension "mp3"
  !insertmacro RegisterExtension "flac"
  !insertmacro RegisterExtension "m4a"
  !insertmacro RegisterExtension "aac"
  !insertmacro RegisterExtension "ogg"
  !insertmacro RegisterExtension "opus"
  !insertmacro RegisterExtension "aiff"
  !insertmacro RegisterExtension "wma"
  !insertmacro RegisterExtension "wav"
  !insertmacro RegisterExtension "mpeg"
  !insertmacro RegisterExtension "m3u"
  !insertmacro RegisterExtension "m3u8"

  ; Register Directory context menu handlers
  ; Play folder with Music Caster
  WriteRegStr HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterPlayFolder" "" "Play with Music Caster"
  WriteRegStr HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterPlayFolder" "Icon" "${EXE_PATH}"
  WriteRegStr HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterPlayFolder\command" "" '"${EXE_PATH}" --shell "%1"'

  ; Queue folder in Music Caster
  WriteRegStr HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterQueueFolder" "" "Queue in Music Caster"
  WriteRegStr HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterQueueFolder" "Icon" "${EXE_PATH}"
  WriteRegStr HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterQueueFolder\command" "" '"${EXE_PATH}" -q --shell "%1"'

  ; Play next folder in Music Caster
  WriteRegStr HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterPlayNextFolder" "" "Play next in Music Caster"
  WriteRegStr HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterPlayNextFolder" "Icon" "${EXE_PATH}"
  WriteRegStr HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterPlayNextFolder\command" "" '"${EXE_PATH}" -n --shell "%1"'

  ; Notify shell of changes
  System::Call 'shell32.dll::SHChangeNotify(i, i, i, i) v (0x08000000, 0, 0, 0)'
!macroend

!macro RegisterExtension EXT
  ; Check if extension key exists, if not create it with MC as default
  ReadRegStr $0 HKCU "${CLASSES_PATH}\\.${EXT}" ""
  ${If} $0 == ""
    WriteRegStr HKCU "${CLASSES_PATH}\\.${EXT}" "" "${MC_FILE}"
  ${EndIf}

  ; Add to Open With (prompts user to set default program)
  WriteRegNone HKCU "${CLASSES_PATH}\\.${EXT}\\OpenWithProgids" "${MC_FILE}"
!macroend

!macro UnregisterFileAssociations
  ; Remove URL protocol handler
  DeleteRegKey HKCU "${CLASSES_PATH}\music-caster"

  ; Remove file type
  DeleteRegKey HKCU "${CLASSES_PATH}\${MC_FILE}"

  ; Remove file extension associations
  !insertmacro UnregisterExtension "mp3"
  !insertmacro UnregisterExtension "flac"
  !insertmacro UnregisterExtension "m4a"
  !insertmacro UnregisterExtension "aac"
  !insertmacro UnregisterExtension "ogg"
  !insertmacro UnregisterExtension "opus"
  !insertmacro UnregisterExtension "aiff"
  !insertmacro UnregisterExtension "wma"
  !insertmacro UnregisterExtension "wav"
  !insertmacro UnregisterExtension "mpeg"
  !insertmacro UnregisterExtension "m3u"
  !insertmacro UnregisterExtension "m3u8"

  ; Remove directory context menu handlers
  DeleteRegKey HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterPlayFolder"
  DeleteRegKey HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterQueueFolder"
  DeleteRegKey HKCU "${CLASSES_PATH}\Directory\shell\MusicCasterPlayNextFolder"

  ; Notify shell of changes
  System::Call 'shell32.dll::SHChangeNotify(i, i, i, i) v (0x08000000, 0, 0, 0)'
!macroend

!macro UnregisterExtension EXT
  ; Remove from OpenWithProgids if it's set to MusicCaster
  DeleteRegValue HKCU "${CLASSES_PATH}\\.${EXT}\\OpenWithProgids" "${MC_FILE}"

  ; If the default handler is MusicCaster, remove it
  ReadRegStr $0 HKCU "${CLASSES_PATH}\\.${EXT}" ""
  ${If} $0 == "${MC_FILE}"
    DeleteRegValue HKCU "${CLASSES_PATH}\\.${EXT}" ""
  ${EndIf}
!macroend

!endif ; FILE_ASSOCIATION_NSH
