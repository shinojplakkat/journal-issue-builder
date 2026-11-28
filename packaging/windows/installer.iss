; Inno Setup script for the Windows installer.
; Build manually: iscc /DAppVersion=0.3.0 packaging\windows\installer.iss
; Installs for the current user only, so no administrator password is needed.

#ifndef AppVersion
  #define AppVersion "0.3.0"
#endif

[Setup]
AppId={{8C4A2F6E-3B7D-4E2A-9F51-6A0D7C1B2E94}
AppName=Journal Issue Builder
AppVersion={#AppVersion}
AppPublisher=Journal Issue Builder
DefaultDirName={localappdata}\Programs\Journal Issue Builder
DefaultGroupName=Journal Issue Builder
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=JournalIssueBuilder-{#AppVersion}-Windows-Setup
SetupIconFile=..\build\icon.ico
UninstallDisplayIcon={app}\JournalIssueBuilder.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\..\LICENSE

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\..\dist\JournalIssueBuilder\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Journal Issue Builder"; Filename: "{app}\JournalIssueBuilder.exe"
Name: "{group}\Uninstall Journal Issue Builder"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Journal Issue Builder"; Filename: "{app}\JournalIssueBuilder.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\JournalIssueBuilder.exe"; Description: "Start Journal Issue Builder"; Flags: nowait postinstall skipifsilent

[Code]
function LibreOfficeInstalled(): Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf64}\LibreOffice\program\soffice.exe')) or
            FileExists(ExpandConstant('{commonpf32}\LibreOffice\program\soffice.exe'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not LibreOfficeInstalled()) and (not WizardSilent()) then
    MsgBox('LibreOffice was not found on this computer.' + #13#10 + #13#10 +
           'Journal Issue Builder needs LibreOffice (free) to lay out Word and ODT articles. ' +
           'Please install it from https://www.libreoffice.org/download/', mbInformation, MB_OK);
end;
