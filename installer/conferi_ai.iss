; Instalador do Conferi AI para Windows (Inno Setup 6).
; Antes, gere a pasta dist\ConferiAI com: pyinstaller conferi_ai.spec

#define AppName "Conferi AI"
#define AppVersion "0.1.0"
#define AppPublisher "MARCOS C. DATA"

[Setup]
AppId={{6B1F5D2E-3C47-4E0A-9F1B-7C2D4E8A1001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Conferi AI
DefaultGroupName=Conferi AI
OutputDir=..\dist\instalador
OutputBaseFilename=ConferiAI-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "..\dist\ConferiAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Conferi AI"; Filename: "{app}\ConferiAI.exe"
Name: "{autodesktop}\Conferi AI"; Filename: "{app}\ConferiAI.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ConferiAI.exe"; Description: "Abrir o Conferi AI"; Flags: nowait postinstall skipifsilent
