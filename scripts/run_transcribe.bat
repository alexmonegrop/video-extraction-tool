@echo off
REM Convenience wrapper: transcribe with in-process diarization.
REM HF_TOKEN must be set in the environment (setx HF_TOKEN hf_...) or via .env.
REM Usage: run_transcribe.bat "videos\my-video.mp4"

if "%~1"=="" (
  echo Usage: %~nx0 ^<video-path^>
  exit /b 1
)

set PYTHONUNBUFFERED=1
python -u "%~dp0..\src\transcribe.py" "%~1" "%~dp0..\transcripts" --diarize
echo EXIT_CODE=%ERRORLEVEL%
