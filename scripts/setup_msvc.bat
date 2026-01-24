@echo off
setlocal

if "%CIBW_ARCH%"=="" (
  echo CIBW_ARCH is not set.
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

set "TARGET=%CIBW_ARCH%"
if /I "%CIBW_ARCH%"=="ARM64" set "TARGET=amd64_arm64"
if /I "%CIBW_ARCH%"=="AMD64" set "TARGET=amd64"

call "%VSCVARS%" %TARGET%
if errorlevel 1 exit /b 1

endlocal
