; Inno Setup script. Compiled by build.bat; @VER@ / @AUTHOR@ are substituted there.
#ifndef AppVer
  #define AppVer "@VER@"
#endif
#ifndef AppAuthor
  #define AppAuthor "@AUTHOR@"
#endif
#define AppName "TempGadget"

[Setup]
AppId={{3BCE7D56-E9B1-49A9-88AD-63FCD67A1893}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher={#AppAuthor}
AppCopyright=© 2026 {#AppAuthor}
AppComments=Виджет рабочего стола: температура и загрузка CPU, GPU, ОЗУ, дисков
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputBaseFilename=TempGadget_Setup
LicenseFile=license.txt
InfoBeforeFile=info.txt
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\TempGadget.exe
VersionInfoVersion={#AppVer}.0
VersionInfoCompany={#AppAuthor}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Messages]
WelcomeLabel2=TempGadget — компактный виджет рабочего стола. Показывает в реальном времени температуру и загрузку процессора, видеокарты, оперативной памяти и дисков.%n%nМастер установит [name/ver] на ваш компьютер. Перед продолжением рекомендуется закрыть остальные приложения.%n%nНажмите «Далее», чтобы продолжить.

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на &рабочем столе"; GroupDescription: "Дополнительные значки:"; Flags: unchecked
Name: "autostart"; Description: "Запускать &вместе с Windows"; GroupDescription: "Автозапуск:"
Name: "pawnio"; Description: "Установить драйвер &PawnIO (нужен для температуры процессора)"; GroupDescription: "Компоненты:"; Check: not PawnIOInstalled

[Files]
Source: "{#SrcExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\TempGadget.exe"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\TempGadget.exe"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""$ErrorActionPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; $f=Join-Path $env:TEMP 'PawnIO_setup.exe'; Invoke-WebRequest 'https://github.com/namazso/PawnIO.Setup/releases/latest/download/PawnIO_setup.exe' -OutFile $f; if (Test-Path $f) {{ Start-Process $f -Wait -ArgumentList '-install','-silent' }"""; StatusMsg: "Установка драйвера PawnIO..."; Flags: runhidden waituntilterminated; Tasks: pawnio
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Register-ScheduledTask -TaskName TempGadget -Force -RunLevel Highest -Action (New-ScheduledTaskAction -Execute '{app}\TempGadget.exe') -Trigger (New-ScheduledTaskTrigger -AtLogOn) -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0)"""; StatusMsg: "Настройка автозапуска..."; Flags: runhidden waituntilterminated; Tasks: autostart
Filename: "{app}\TempGadget.exe"; Description: "Запустить {#AppName}"; Flags: nowait postinstall skipifsilent shellexec

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/F /IM TempGadget.exe"; Flags: runhidden; RunOnceId: "KillApp"
Filename: "schtasks.exe"; Parameters: "/Delete /TN TempGadget /F"; Flags: runhidden; RunOnceId: "DelTask"

[Code]
function PawnIOInstalled: Boolean;
begin
  Result := RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\PawnIO');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  R: Integer;
begin
  if CurStep = ssInstall then
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM TempGadget.exe', '', SW_HIDE, ewWaitUntilTerminated, R);
end;
