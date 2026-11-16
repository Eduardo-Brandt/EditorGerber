#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef PayloadDir
  #error PayloadDir is required
#endif
#ifndef ReleaseDir
  #error ReleaseDir is required
#endif

[Setup]
AppId=br.com.brandttecnologia.editorgerber
AppName=Editor Gerber
AppVersion={#AppVersion}
AppPublisher=Eduardo Guilherme Brandt
AppPublisherURL=https://brandttecnologia.com.br/EditorGerber
AppSupportURL=https://brandttecnologia.com.br/EditorGerber/RelatarProblemas
DefaultDirName={localappdata}\Programs\EditorGerber
DefaultGroupName=Editor Gerber
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#ReleaseDir}
OutputBaseFilename=EditorGerber-v{#AppVersion}-setup-windows-x64
SetupIconFile=..\gerber_editor\assets\app_icon.ico
UninstallDisplayIcon={app}\EditorGerber.exe
LicenseFile=..\LICENSE
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
Uninstallable=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Editor Gerber"; Filename: "{app}\EditorGerber.exe"
Name: "{autodesktop}\Editor Gerber"; Filename: "{app}\EditorGerber.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\EditorGerber.exe"; Description: "{cm:LaunchProgram,Editor Gerber}"; Flags: nowait postinstall skipifsilent
