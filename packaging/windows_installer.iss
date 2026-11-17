; Inno Setup script for the Windows installer. Built on CI:  iscc /DAppVersion=2.1.0 packaging\windows_installer.iss
#ifndef AppVersion
  #define AppVersion "2.1.0"
#endif

[Setup]
AppId={{6F1E2C1B-7A43-4D0F-9C55-2B7E0E3D9A21}
AppName=TrailBuddy Analyzer
AppVersion={#AppVersion}
AppPublisher=TrailBuddy class project
DefaultDirName={localappdata}\Programs\TrailBuddy Analyzer
DefaultGroupName=TrailBuddy Analyzer
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=TrailBuddy-Analyzer-{#AppVersion}-Windows-x64-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\TrailBuddy Analyzer.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\TrailBuddy Analyzer\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\TrailBuddy Analyzer"; Filename: "{app}\TrailBuddy Analyzer.exe"
Name: "{autodesktop}\TrailBuddy Analyzer"; Filename: "{app}\TrailBuddy Analyzer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TrailBuddy Analyzer.exe"; Description: "Start TrailBuddy Analyzer"; Flags: nowait postinstall skipifsilent
