; CEO Barkod — Inno Setup 6 Kurulum Scripti
; Derleme: create_installer_barkod.bat  veya  ISCC.exe setup_barkod.iss
; Çıktı:   dist\CEO-Barkod-Kurulum.exe
; Pakete YALNIZ derlenmiş exe + bağlantı ayarı girer; kaynak kod (.py) paketlenmez.

#define AppName    "CEO Barkod"
#define AppVersion "1.0"
#define AppExe     "CEO-Barkod.exe"
#define Publisher  "Gempa Elektro Mekanik Müh. Ltd. Şti."

[Setup]
; ERP Araçları kurulumundan FARKLI AppId (ikisi aynı PC'de yan yana kurulabilir)
AppId={{7C3E9B52-4D1A-4F6E-8A27-5B0D9E41C6A3}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={autopf}\CEO Barkod
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=CEO-Barkod-Kurulum
SetupIconFile=assets\barkod.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek görevler:"

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

; Veritabanı bağlantı ayarı. Yalnızca config.json yoksa kopyalanır (güncelleme kurulumunda
; özelleştirilmiş ayarı silmez). Program ilk açılışta bunu kullanıcı veri klasörüne tohumlar.
Source: "dist\config.json"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName}'ı Kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{#AppName}'ı şimdi başlat"; Flags: nowait postinstall skipifsilent
