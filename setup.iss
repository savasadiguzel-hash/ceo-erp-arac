; CEO ERP Araçları — Inno Setup 6 Kurulum Scripti
; Derleme: create_installer.bat  veya  ISCC.exe setup.iss
; Çıktı:   dist\CEO-ERP-Kurulum.exe

#define AppName    "CEO ERP Araçları"
#define AppVersion "1.0"
#define AppExe     "CEO-ERP-Araclar.exe"
#define Publisher  "CEO"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={autopf}\CEO ERP Araclar
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=CEO-ERP-Kurulum
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=no
PrivilegesRequired=admin
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek görevler:"; Flags: unchecked

[Files]
; Ana uygulama
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

; Gerçek bağlantı bilgileri (şirket içi kullanım — tüm PC'ler aynı CEO ERP veritabanına bağlanır)
; Yalnızca config.json yoksa kopyalanır (mevcut/özelleştirilmiş ayarları günceleme kurulumunda silmez)
Source: "dist\config.json"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist

[Icons]
; Başlat Menüsü
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName}'ı Kaldır"; Filename: "{uninstallexe}"

; Masaüstü kısayolu (kullanıcı seçerse)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; Kurulum bittikten sonra programı başlatma seçeneği
Filename: "{app}\{#AppExe}"; Description: "{#AppName}'ı şimdi başlat"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Kaldırma sırasında log dosyalarını temizle (config.json korunur)
Type: files; Name: "{app}\ceo_erp.log"
