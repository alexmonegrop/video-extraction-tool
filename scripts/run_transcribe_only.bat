@echo off
REM Convenience wrapper: transcribe WITHOUT diarization.
REM Usage: run_transcribe_only.bat "videos\my-video.mp4"

if "%~1"=="" (
  echo Usage: %~nx0 ^<video-path^>
  exit /b 1
)

set PYTHONUNBUFFERED=1
python -u "%~dp0..\src\transcribe.py" "%~1" "%~dp0..\transcripts"
echo EXIT_CODE=%ERRORLEVEL%
