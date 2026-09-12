; ============================================================
; JarvisOS - Windows Installer Configuration
; Inno Setup 6
; ============================================================

#define MyAppName "JarvisOS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "JarvisOS"
#define MyAppExeName "JarvisOS.exe"
#define MyAppOutputName "JarvisOS-Setup"

[Setup]

; Unique application ID
AppId={{8F4B4D8A-6F3A-4A7E-BF15-7D2C8D6A91F2}

AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

; Default installation location
DefaultDirName={autopf}{#MyAppName}

; Start Menu folder
DefaultGroupName={#MyAppName}

; Installer output
OutputDir=..\dist
OutputBaseFilename={#MyAppOutputName}

; Compression
Compression=lzma2
SolidCompression=yes

; Modern installer interface
WizardStyle=modern

; 64-bit Windows installation
ArchitecturesInstallIn64BitMode=x64

; Require administrator permission for installation
PrivilegesRequired=admin

; Uninstaller
UninstallDisplayName={#MyAppName}
Uninstallable=yes

; Allow user to choose installation directory
DisableDirPage=no

; Version information
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription={#MyAppName} Windows Installer
VersionInfoProductName={#MyAppName}
VersionInfoCompany={#MyAppPublisher}

; Installer appearance
WizardResizable=yes

; ============================================================
; FILES
; ============================================================

[Files]

; Main JarvisOS executable created by PyInstaller
Source: "..\build\dist\JarvisOS.exe"; 
DestDir: "{app}"; 
Flags: ignoreversion

; ============================================================
; SHORTCUTS
; ============================================================

[Icons]

; Start Menu shortcut
Name: "{group}\JarvisOS"; 
Filename: "{app}\JarvisOS.exe"; 
WorkingDir: "{app}"

; Desktop shortcut
Name: "{autodesktop}\JarvisOS"; 
Filename: "{app}\JarvisOS.exe"; 
WorkingDir: "{app}"; 
Tasks: desktopicon

; ============================================================
; OPTIONAL TASKS
; ============================================================

[Tasks]

Name: "desktopicon"; 
Description: "Create a desktop shortcut"; 
GroupDescription: "Additional shortcuts:"; 
Flags: unchecked

; ============================================================
; INSTALLER FINISH PAGE
; ============================================================

[Run]

; Launch JarvisOS after installation
Filename: "{app}\JarvisOS.exe"; 
Description: "Launch JarvisOS"; 
Flags: nowait postinstall skipifsilent

; ============================================================
; UNINSTALL
; ============================================================

[UninstallDelete]

; Remove generated local configuration/cache files
Type: filesandordirs; 
Name: "{app}\build"

; ============================================================
; END
; ============================================================
