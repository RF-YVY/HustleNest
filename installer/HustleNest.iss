; Inno Setup script to package HustleNest into a Windows installer
#define AppName "HustleNest"
#define AppVersion "3.0"
#define AppPublisher "HustleNest"
#define AppURL "https://github.com/RF-YVY/HustleNest"
#define OutputBase "HustleNestSetup"

[Setup]
AppId={{3ECAA3E2-E24B-4B08-9B03-DC7D0AF2C9B5}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableDirPage=no
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\build
OutputBaseFilename={#OutputBase}
SetupIconFile=..\HustleNest.ico
UninstallDisplayIcon={app}\HustleNest.exe
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=no
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\HustleNest\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\HustleNest.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\HustleNest.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\HustleNest.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
