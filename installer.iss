; Inno Setup Script for WinOCR-Html v0.8.0
; Build with iscc installer.iss

[Setup]
AppId={{B8A3C9D4-5E6F-7A8B-9C0D-1E2F3A4B5C6D}
AppName=WinOCR-Html
AppVersion=0.8.0
AppPublisher=WinOCR Team
AppPublisherURL=https://github.com/beyondaguan/WinOCR-Html
AppSupportURL=https://github.com/beyondaguan/WinOCR-Html/issues
AppUpdatesURL=https://github.com/beyondaguan/WinOCR-Html/releases
DefaultDirName={autopf}\WinOCR-Html
DefaultGroupName=WinOCR-Html
AllowNoIcons=yes
LicenseFile=extension\LICENSE
OutputDir=D:\AI
OutputBaseFilename=WinOCR-Html-Setup-v0.8.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredAllowedOverrides=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "D:\AI\WinOCR-Html0.3 - 副本\extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "D:\AI\WinOCR-Html0.3 - 副本\native_host\winocr_host.exe"; DestDir: "{app}\native_host"; Flags: ignoreversion
Source: "D:\AI\WinOCR-Html0.3 - 副本\native_host\winocr_config.json"; DestDir: "{app}\native_host"; Flags: ignoreversion
Source: "D:\AI\WinOCR-Html0.3 - 副本\native_host\com.winocr_host.json"; DestDir: "{app}\native_host"; Flags: ignoreversion
Source: "D:\AI\WinOCR-Html0.3 - 副本\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\AI\WinOCR-Html0.3 - 副本\extension\native_host\MODELS.md"; DestDir: "{app}\extension\native_host"; Flags: ignoreversion
Source: "D:\AI\WinOCR-Html0.3 - 副本\extension\native_host\install_host.bat"; DestDir: "{app}\extension\native_host"; Flags: ignoreversion
Source: "D:\AI\WinOCR-Html0.3 - 副本\extension\native_host\uninstall_host.bat"; DestDir: "{app}\extension\native_host"; Flags: ignoreversion

[Icons]
Name: "{group}\WinOCR-Html"; Filename: "{app}\native_host\winocr_host.exe"; Parameters: "--standalone"
Name: "{group}\{cm:UninstallProgram,WinOCR-Html}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\WinOCR-Html"; Filename: "{app}\native_host\winocr_host.exe"; Parameters: "--standalone"; Tasks: desktopicon

[Run]
Filename: "{app}\extension\native_host\install_host.bat"; Description: "Register Native Host for Browser Extension"; Flags: runhidden

[Registry]
Root: HKCU; Subkey: "Software\Google\Chrome\NativeMessagingHosts\com.winocr_host"; ValueType: string; ValueName: ""; ValueData: "{app}\native_host\com.winocr_host.json"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Edge\NativeMessagingHosts\com.winocr_host"; ValueType: string; ValueName: ""; ValueData: "{app}\native_host\com.winocr_host.json"; Flags: uninsdeletekey

[UninstallDelete]
Type: filesandordirs; Name: "{app}\models"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := true;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Update manifest with installed path
    SaveStringToFile(ExpandConstant('{app}\native_host\com.winocr_host.json'), 
      '{"name":"com.winocr_host","description":"WinOCR-Html Native Host","path":"' + 
      ExpandConstant('{app}\native_host\winocr_host.exe') + 
      '","type":"stdio","allowed_origins":["chrome-extension://*"]}', false);
  end;
end;
