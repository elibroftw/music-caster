#define MyAppName "Music Caster"
#define MyAppVersion "4.60.8"
#define MyAppPublisher "Elijah Lopez"
#define MyAppURL "http://elopez.me/#music-caster"
#define MyAppExeName "Music Caster.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{FBE8A652-58D6-482D-B6A9-B3D7931CC9C5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
;AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
Compression=lzma
SolidCompression=yes
WizardStyle=modern
MinVersion=0,6.0.6001
; Minimum version is Windows Vista or later
; Remove the following line to run in administrative install mode (install for all users.)
PrivilegesRequired=lowest
OutputDir={#SourcePath}\..\dist
OutputBaseFilename=Music Caster Setup
UninstallDisplayName=Music Caster
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile="..\resources\Music Caster.ico"

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourcePath}\..\dist\Music Caster\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "{#SourcePath}CHANGELOG.txt"; DestDir: "{app}"; DestName: "CHANGELOG.txt"; Flags: ignoreversion
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[InstallDelete]
Type: files; Name: {app}\*.pyd
Type: files; Name: {app}\*.dll
; delete previous version folders and those that may contain old files
Type: filesandordirs; Name: {app}\pygame
Type: filesandordirs; Name: {app}\images
Type: filesandordirs; Name: {app}\wx
Type: filesandordirs; Name: {app}\lxml
Type: filesandordirs; Name: {app}\lib2to3
Type: filesandordirs; Name: {app}\google
Type: filesandordirs; Name: {app}\markupsafe
Type: filesandordirs; Name: {app}\Crypto
Type: filesandordirs; Name: {app}\templates


[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall
; skipifsilent
