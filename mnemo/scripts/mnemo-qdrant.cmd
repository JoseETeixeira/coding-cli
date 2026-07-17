@echo off
REM Start (or restart) the mnemo Qdrant vector DB on host port 1337.
REM Data persists in the named docker volume "mnemo_qdrant_storage".
setlocal
set NAME=mnemo-qdrant
set PORT=1337

docker inspect %NAME% >nul 2>&1
if %errorlevel%==0 (
  echo [mnemo] container %NAME% exists - starting if stopped...
  docker start %NAME%
) else (
  echo [mnemo] creating %NAME% on port %PORT% ...
  docker run -d --name %NAME% -p %PORT%:6333 -v mnemo_qdrant_storage:/qdrant/storage --restart unless-stopped qdrant/qdrant:latest
)

echo [mnemo] waiting for readiness on http://127.0.0.1:%PORT%/readyz ...
for /l %%i in (1,1,20) do (
  curl -s http://127.0.0.1:%PORT%/readyz >nul 2>&1 && (echo [mnemo] Qdrant ready & goto :done)
  timeout /t 1 >nul
)
:done
endlocal
