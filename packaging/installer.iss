#define MyAppName "Health Tools UI"
#ifndef MyAppVersion
  #define MyAppVersion "0.3.2"
#endif
#ifndef MyOutputBaseFilename
  #define MyOutputBaseFilename "health-tools-ui-setup-0.3.2"
#endif
#define MyAppPublisher "XiaoPb"
#define MyAppExeName "HealthToolsUI.exe"

[Setup]
AppId={{7DA61ACD-0B77-4B6E-BDA9-4BF5DCC557AD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Health Tools UI
DefaultGroupName={#MyAppName}
OutputDir=..\dist
OutputBaseFilename={#MyOutputBaseFilename}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile=..\src\health_tools_ui\assets\app-icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\HealthToolsUI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\offline"
Name: "{app}\config"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
