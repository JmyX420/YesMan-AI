; YesMan AI - A FNV Modding Toolbox for Claude and Codex
; Inno Setup installer script.
;
; Front-end for the unified configurator (installer\configure.py): copies the whole
; toolbox into the Fallout: New Vegas game folder, lets the user pick which Mod
; Organizer 2 instance to wire up, then runs configure.py post-copy to do the real
; wiring (placeholders, npm, MO2 plugin deploy, live-link deploy, MCP registration).
;
; Build:  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\YesManAI.iss
; Output: dist\YesManAI-Setup-<version>.exe

#define AppName "YesMan AI"
#define AppNameLong "YesMan AI - A FNV Modding Toolbox for Claude and Codex"
#define AppVersion "1.0.0"
#define AppPublisher "JmyX"

[Setup]
AppId={{8F1D2C4A-7E3B-4A9C-9B2E-YESMANFNV001}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppNameLong} {#AppVersion}
AppPublisher={#AppPublisher}
WizardStyle=modern
DefaultDirName={code:GetFNVDir}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=YesManAI-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayName={#AppNameLong}
; The install target is the FNV game folder, which already exists.
DirExistsWarning=no
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Shared base: the engine, docs, and the SHARED skills source (.claude\skills, which the
; configurator also deploys to Codex's .agents\skills). Dev-only/transient files are excluded,
; and so are the AGENT-SPECIFIC files -- those are installed by the per-agent entries below,
; gated on the wizard's agent choice. So Claude-only omits codex\, and Codex-only omits
; CLAUDE.md + the Claude-only .claude hooks/settings (while keeping the shared .claude\skills).
; NOTE: no createallsubdirs here -- we intentionally let Inno create only directories that
; actually receive files, so an excluded agent's folder (e.g. codex\ for a Claude-only install)
; is not created as an empty dir. The per-agent entries below carry their own subdirs.
Source: "..\*"; DestDir: "{app}"; \
  Flags: recursesubdirs ignoreversion; \
  Excludes: "\node_modules\*,\.git\*,\dist\*,\.gitignore,\.gitattributes,\.claude\backups\*,\.claude\plans\*,\.claude\settings.local.json,\.claude\settings.local.json.example,\.claude\settings.json,\.claude\hooks\*,\CLAUDE.md,\codex\*,\BUILD_PLAN.md,\mo2-mcp\PORT_PLAN.md,\live-link\PORT_PLAN.md,\installer\*.iss,*.zip,*.log,\xelib_log.txt,*.pyc"

; Claude Code integration -- only when Claude (or Both) is chosen.
Source: "..\CLAUDE.md"; DestDir: "{app}"; Flags: ignoreversion; Check: WantClaude
Source: "..\.claude\hooks\*"; DestDir: "{app}\.claude\hooks"; Flags: recursesubdirs createallsubdirs ignoreversion; Check: WantClaude
Source: "..\.claude\settings.json"; DestDir: "{app}\.claude"; Flags: ignoreversion; Check: WantClaude
Source: "..\.claude\settings.local.json.example"; DestDir: "{app}\.claude"; Flags: ignoreversion; Check: WantClaude

; Codex integration -- only when Codex (or Both) is chosen.
Source: "..\codex\*"; DestDir: "{app}\codex"; Flags: recursesubdirs createallsubdirs ignoreversion; Check: WantCodex

[Run]
; Post-copy wiring. Runs as the invoking user so ~/.claude.json is the real user's.
Filename: "{code:GetPython}"; \
  Parameters: "{code:GetConfigureCmd}"; \
  WorkingDir: "{app}"; \
  StatusMsg: "Configuring YesMan AI (detecting tools, wiring MO2 + MCP servers)..."; \
  Flags: runascurrentuser waituntilterminated; \
  Check: PythonAvailable

[UninstallRun]
Filename: "{code:GetPython}"; \
  Parameters: """{app}\installer\configure.py"" --game-root ""{app}"" --uninstall"; \
  WorkingDir: "{app}"; \
  Flags: runascurrentuser waituntilterminated; \
  RunOnceId: "YesManUnconfigure"; \
  Check: PythonAvailable

[Code]
var
  PythonExe: String;
  AgentPage: TInputOptionWizardPage;   // which AI coding agent(s) to wire up
  MO2Page: TInputOptionWizardPage;
  MO2Dirs: TStringList;      // ModOrganizer.exe folder for each detected NV instance
  MO2Profiles: TStringList;  // matching selected_profile
  NoMO2Index: Integer;       // index of the "I don't use MO2" radio option
  MO2PageBuilt: Boolean;     // True once the picker page is populated (never in silent mode)

{ ---- helpers ---- }

function ByteArrayDecode(S: String): String;
begin
  Result := S;
  if (Copy(Result, 1, 11) = '@ByteArray(') and (Copy(Result, Length(Result), 1) = ')') then
    Result := Copy(Result, 12, Length(Result) - 12);
  StringChangeEx(Result, '\\', '\', True);
end;

function SamePath(A, B: String): Boolean;
begin
  Result := CompareText(RemoveBackslashUnlessRoot(A), RemoveBackslashUnlessRoot(B)) = 0;
end;

{ ---- FNV game folder detection (default install dir) ---- }

function GetFNVDir(Param: String): String;
var
  P: String;
begin
  Result := '';
  { Bethesda registry key written by the FNV installer }
  if RegQueryStringValue(HKLM64, 'SOFTWARE\Bethesda Softworks\falloutnv', 'Installed Path', P) then
    if (P <> '') and FileExists(AddBackslash(P) + 'FalloutNV.exe') then
      Result := RemoveBackslashUnlessRoot(P);
  if Result = '' then
    if RegQueryStringValue(HKLM32, 'SOFTWARE\Bethesda Softworks\falloutnv', 'Installed Path', P) then
      if (P <> '') and FileExists(AddBackslash(P) + 'FalloutNV.exe') then
        Result := RemoveBackslashUnlessRoot(P);
  if Result = '' then
  begin
    if FileExists('C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas\FalloutNV.exe') then
      Result := 'C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas'
    else if FileExists('D:\SteamLibrary\steamapps\common\Fallout New Vegas\FalloutNV.exe') then
      Result := 'D:\SteamLibrary\steamapps\common\Fallout New Vegas'
    else
      Result := 'C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas';
  end;
end;

{ ---- real python.exe (skip Windows Store stub aliases) ---- }

function PythonFromHive(Hive: Integer): String;
var
  Names: TArrayOfString;
  I: Integer;
  Base, Exe: String;
begin
  Result := '';
  if RegGetSubkeyNames(Hive, 'SOFTWARE\Python\PythonCore', Names) then
    for I := 0 to GetArrayLength(Names) - 1 do
    begin
      if RegQueryStringValue(Hive, 'SOFTWARE\Python\PythonCore\' + Names[I] + '\InstallPath', '', Base) then
      begin
        Exe := AddBackslash(Base) + 'python.exe';
        if FileExists(Exe) then
        begin
          Result := Exe;
          Exit;
        end;
      end;
    end;
end;

function DetectPython: String;
begin
  Result := PythonFromHive(HKCU64);
  if Result = '' then Result := PythonFromHive(HKLM64);
  if Result = '' then Result := PythonFromHive(HKCU32);
  if Result = '' then Result := PythonFromHive(HKLM32);
end;

function GetPython(Param: String): String;
begin
  Result := PythonExe;
end;

function PythonAvailable: Boolean;
begin
  Result := (PythonExe <> '') and FileExists(PythonExe);
end;

{ ---- agent-choice gates for conditional [Files] copy ----
  AgentPage options: 0 = Claude Code, 1 = Codex, 2 = Both. In silent mode the page is
  still built (InitializeWizard) with index 0, so a silent install = Claude, matching the
  --agent default passed to configure.py. }
function WantClaude: Boolean;
begin
  Result := (AgentPage = nil) or (AgentPage.SelectedValueIndex = 0) or (AgentPage.SelectedValueIndex = 2);
end;

function WantCodex: Boolean;
begin
  Result := (AgentPage <> nil) and ((AgentPage.SelectedValueIndex = 1) or (AgentPage.SelectedValueIndex = 2));
end;

{ ---- MO2 instance scan (find instances whose gamePath == chosen game folder) ---- }

procedure AddIfMatch(IniPath, GameDir: String);
var
  GP, Prof, IniDir: String;
begin
  if not FileExists(IniPath) then Exit;
  GP := ByteArrayDecode(GetIniString('General', 'gamePath', '', IniPath));
  if (GP = '') or (not SamePath(GP, GameDir)) then Exit;
  IniDir := ExtractFileDir(IniPath);
  if MO2Dirs.IndexOf(IniDir) >= 0 then Exit;  { dedupe }
  Prof := ByteArrayDecode(GetIniString('General', 'selected_profile', '', IniPath));
  MO2Dirs.Add(IniDir);
  MO2Profiles.Add(Prof);
end;

procedure ScanChildren(ParentDir, GameDir: String);
var
  FR: TFindRec;
begin
  if FindFirst(AddBackslash(ParentDir) + '*', FR) then
  try
    repeat
      if (FR.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0)
         and (FR.Name <> '.') and (FR.Name <> '..') then
        AddIfMatch(AddBackslash(ParentDir) + FR.Name + '\ModOrganizer.ini', GameDir);
    until not FindNext(FR);
  finally
    FindClose(FR);
  end;
end;

procedure ScanRoot(Root, GameDir: String);
var
  FR: TFindRec;
  Sub: String;
begin
  { two levels deep from a drive root -- mirrors the configurator's glob }
  if FindFirst(AddBackslash(Root) + '*', FR) then
  try
    repeat
      if (FR.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0)
         and (FR.Name <> '.') and (FR.Name <> '..') then
      begin
        Sub := AddBackslash(Root) + FR.Name;
        AddIfMatch(Sub + '\ModOrganizer.ini', GameDir);
        ScanChildren(Sub, GameDir);
      end;
    until not FindNext(FR);
  finally
    FindClose(FR);
  end;
end;

procedure CollectMO2(GameDir: String);
var
  Base: String;
  D: Integer;
  Drive: String;
begin
  MO2Dirs.Clear;
  MO2Profiles.Clear;
  { global instances }
  Base := ExpandConstant('{localappdata}\ModOrganizer');
  if DirExists(Base) then ScanChildren(Base, GameDir);
  { portable instances on fixed drives C..H }
  for D := 0 to 5 do
  begin
    Drive := Chr(Ord('C') + D) + ':\';
    if DirExists(Drive) then ScanRoot(Drive, GameDir);
  end;
end;

{ ---- wizard wiring ---- }

procedure InitializeWizard;
begin
  MO2Dirs := TStringList.Create;
  MO2Profiles := TStringList.Create;
  NoMO2Index := -1;  { -1 until the page is actually built; guards silent installs }
  MO2PageBuilt := False;
  { Agent picker (static options, built here so it's valid even in silent mode) }
  AgentPage := CreateInputOptionPage(wpSelectDir,
    'AI Coding Agent', 'Which agent should YesMan AI set up?',
    'YesMan AI can wire up Claude Code, Codex, or both. This chooses which instruction '
    + 'file, skills, safety hooks, and MCP configuration get installed.',
    True, False);
  AgentPage.Add('Claude Code');
  AgentPage.Add('Codex');
  AgentPage.Add('Both (Claude Code + Codex)');
  AgentPage.SelectedValueIndex := 0;
  { MO2 picker comes after the agent choice }
  MO2Page := CreateInputOptionPage(AgentPage.ID,
    'Mod Organizer 2', 'Which MO2 instance should YesMan AI wire up?',
    'YesMan AI installs a live MO2 companion (conflict analysis, patches) and the live-link '
    + 'game mod. Choose the MO2 instance that manages this Fallout: New Vegas folder. '
    + 'If you don''t use MO2, pick the last option.',
    True, False);  { Exclusive (radio), not a listbox }
end;

procedure CurPageChanged(CurPageID: Integer);
var
  I: Integer;
  Caption: String;
begin
  if (MO2Page <> nil) and (CurPageID = MO2Page.ID) then
  begin
    { (re)build the option list for the currently chosen game folder }
    MO2Page.CheckListBox.Items.Clear;
    CollectMO2(WizardDirValue);
    for I := 0 to MO2Dirs.Count - 1 do
    begin
      Caption := MO2Profiles[I];
      if Caption = '' then Caption := '(default profile)';
      MO2Page.Add(Caption + '   ->   ' + MO2Dirs[I]);
    end;
    MO2Page.Add('I don''t use Mod Organizer 2 (manual / Vortex install)');
    NoMO2Index := MO2Dirs.Count;
    MO2PageBuilt := True;
    if MO2Dirs.Count > 0 then
      MO2Page.SelectedValueIndex := 0
    else
      MO2Page.SelectedValueIndex := NoMO2Index;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectDir then
    if not FileExists(AddBackslash(WizardDirValue) + 'FalloutNV.exe') then
      Result := (MsgBox('FalloutNV.exe was not found in:' + #13#10 + WizardDirValue + #13#10#13#10
        + 'YesMan AI must be installed into your Fallout: New Vegas game folder. '
        + 'Continue anyway?', mbConfirmation, MB_YESNO) = IDYES);
end;

function GetConfigureCmd(Param: String): String;
var
  Sel: Integer;
begin
  Result := '"' + ExpandConstant('{app}\installer\configure.py') + '"'
    + ' --game-root "' + ExpandConstant('{app}') + '"'
    + ' --python "' + PythonExe + '"';
  { agent choice (defaults to claude if the page wasn't shown, e.g. silent mode) }
  if AgentPage <> nil then
  begin
    if AgentPage.SelectedValueIndex = 1 then Result := Result + ' --agent codex'
    else if AgentPage.SelectedValueIndex = 2 then Result := Result + ' --agent both'
    else Result := Result + ' --agent claude';
  end;
  { Only pass an MO2 choice when the picker page was actually shown+built. In silent
    mode the page never builds, so we pass nothing and let configure.py auto-detect. }
  if MO2PageBuilt then
  begin
    Sel := MO2Page.SelectedValueIndex;
    if (Sel >= 0) and (Sel < MO2Dirs.Count) then
      Result := Result + ' --mo2-instance "' + MO2Dirs[Sel] + '"'
    else if Sel = NoMO2Index then
      Result := Result + ' --no-mo2';
  end;
end;

function InitializeSetup: Boolean;
begin
  PythonExe := DetectPython;
  Result := True;
  if not PythonAvailable then
    MsgBox('Python was not found on this PC.' + #13#10#13#10
      + 'YesMan AI needs Python 3 to finish setup (the live link and the configurator run on it). '
      + 'Install Python from https://www.python.org/downloads/ (tick "Add to PATH"), then re-run '
      + 'this installer. The files will still be copied now, but the automatic wiring step will be '
      + 'skipped -- you can run installer\configure.py yourself afterwards.',
      mbInformation, MB_OK);
end;

procedure DeinitializeSetup;
begin
  if MO2Dirs <> nil then MO2Dirs.Free;
  if MO2Profiles <> nil then MO2Profiles.Free;
end;
