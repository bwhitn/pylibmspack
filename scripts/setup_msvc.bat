@echo off
setlocal

set "ARCH=%CIBW_ARCH%"
if "%ARCH%"=="" (
  set "ARCH=%CIBW_BUILD_ARCH%"
)
if "%ARCH%"=="" (
  if not "%CIBW_BUILD_IDENTIFIER%"=="" (
    echo %CIBW_BUILD_IDENTIFIER% | findstr /i "win_arm64" >nul
    if not errorlevel 1 set "ARCH=ARM64"
    echo %CIBW_BUILD_IDENTIFIER% | findstr /i "win_amd64" >nul
    if not errorlevel 1 set "ARCH=AMD64"
  )
)

if "%ARCH%"=="" (
  echo CIBW_ARCH is not set and could not be inferred.
  exit /b 1
)

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
  echo vswhere.exe not found at %VSWHERE%
  exit /b 1
)

for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -property installationPath`) do set "VSINSTALL=%%i"
if "%VSINSTALL%"=="" (
  echo Visual Studio installation not found.
  exit /b 1
)

set "VSCVARS=%VSINSTALL%\VC\Auxiliary\Build\vcvarsall.bat"
if not exist "%VSCVARS%" (
  echo vcvarsall.bat not found at %VSCVARS%
  exit /b 1
)

set "TARGET=%ARCH%"
if /I "%ARCH%"=="ARM64" set "TARGET=amd64_arm64"
if /I "%ARCH%"=="AMD64" set "TARGET=amd64"

call "%VSCVARS%" %TARGET%
if errorlevel 1 exit /b 1

endlocal
