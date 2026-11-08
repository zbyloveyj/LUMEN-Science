Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
Name "LUMEN Science"
OutFile "..\dist\LUMEN-Science-${VERSION}-windows-x64-setup.exe"
InstallDir "$LOCALAPPDATA\Programs\LUMENScience"
InstallDirRegKey HKCU "Software\LUMENScience" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
!define MUI_ICON "lumen.ico"
!define MUI_UNICON "lumen.ico"
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\LUMENScience.exe"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "LUMEN Science requires 64-bit Windows 10/11."
    Abort
  ${EndIf}
FunctionEnd

Section "LUMEN Science" Main
  SetShellVarContext current
  ; Microsoft-documented Evergreen runtime detection (check both machine/user scopes).
  SetRegView 32
  ReadRegStr $0 HKLM "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ReadRegStr $1 HKCU "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${If} $0 == ""
  ${AndIf} $1 == ""
    InitPluginsDir
    SetOutPath "$PLUGINSDIR"
    File "..\.tools\MicrosoftEdgeWebview2Setup.exe"
    ExecWait '"$PLUGINSDIR\MicrosoftEdgeWebview2Setup.exe" /silent /install' $2
    ${If} $2 != 0
      MessageBox MB_ICONSTOP "Microsoft WebView2 could not be installed. Install the Evergreen Runtime from developer.microsoft.com/microsoft-edge/webview2, then retry."
      SetErrorLevel 1
      Abort
    ${EndIf}
  ${EndIf}
  SetOutPath "$INSTDIR"
  File /r "..\dist\LUMENScience\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\LUMEN Science"
  CreateShortCut "$SMPROGRAMS\LUMEN Science\LUMEN Science.lnk" "$INSTDIR\LUMENScience.exe"
  CreateShortCut "$SMPROGRAMS\LUMEN Science\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortCut "$DESKTOP\LUMEN Science.lnk" "$INSTDIR\LUMENScience.exe"
  WriteRegStr HKCU "Software\LUMENScience" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LUMENScience" "DisplayName" "LUMEN Science"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LUMENScience" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LUMENScience" "Publisher" "LUMEN Science contributors"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LUMENScience" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LUMENScience" "DisplayIcon" "$INSTDIR\LUMENScience.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LUMENScience" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LUMENScience" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  SetRegView 32
  !include "..\build\uninstall-files.nsh"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$DESKTOP\LUMEN Science.lnk"
  Delete "$SMPROGRAMS\LUMEN Science\LUMEN Science.lnk"
  Delete "$SMPROGRAMS\LUMEN Science\Uninstall.lnk"
  RMDir "$SMPROGRAMS\LUMEN Science"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LUMENScience"
  DeleteRegKey HKCU "Software\LUMENScience"
  ; Projects, settings and credentials in LocalAppData\LUMENScience are deliberately retained.
SectionEnd
