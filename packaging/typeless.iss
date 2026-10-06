; Inno Setup script — builds dist\TypelessSetup.exe from dist\Typeless (PyInstaller onedir).
; Per-user install, no admin rights needed.

#define AppName "Typeless"
#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif

[Setup]
AppId={{6C1B7A0E-3F4D-4E59-9C7B-7A55E1C0D2A1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=imangali01
AppPublisherURL=https://github.com/imangali01/typeless
DefaultDirName={localappdata}\Programs\Typeless
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=TypelessSetup
SetupIconFile=typeless.ico
UninstallDisplayIcon={app}\Typeless.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
AppMutex=TypelessAppMutex
CloseApplications=yes

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Ярлык на рабочем столе"; GroupDescription: "Дополнительно:"
Name: "autostart"; Description: "Запускать Typeless вместе с Windows"; GroupDescription: "Дополнительно:"

[Files]
Source: "..\dist\Typeless\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Typeless.exe"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\Typeless.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Typeless"; \
  ValueData: """{app}\Typeless.exe"" --background"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\Typeless.exe"; Description: "Запустить Typeless"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
