<!-- Thanks for the PR! Fill in the sections below. Trim what doesn't apply. -->

## Summary

<!-- One or two sentences on what changed and why. -->

## Type of change

<!-- Check all that apply -->

- [ ] Bug fix
- [ ] New feature (pipeline module, skill, script, doc)
- [ ] Refactor / cleanup (no behaviour change)
- [ ] Documentation only
- [ ] Configuration / dependency change
- [ ] Breaking change (existing users will need to update something)

## Testing

<!-- How did you validate this change? Be specific.
     For pipeline modules: which test video did you run it against, and what was the wall-clock time and output?
     For skills/docs: did you exercise the workflow end-to-end?
     For dependency bumps: did you confirm CUDA still works and diarization still completes? -->

- [ ] Tested on the maintainer's reference hardware (RTX 4070 SUPER, CUDA 12.x, Python 3.10–3.14, Windows 11) — OR documented the alternate environment in the PR body
- [ ] Output files match the expected format (`_transcript.txt`, `_transcript_timestamped.txt`, `_transcript.json`, `_analysis.md` where applicable)
- [ ] No regression on the documented gotchas (cublas DLL fix, separate-process diarization, torchcodec workaround, exit-code-127 false-negative)
- [ ] Forbidden-token grep passes (no real PII / real participant names / real PATs / real `HF_TOKEN` introduced)
- [ ] `.env.example` updated if a new env var was introduced
- [ ] `CHANGELOG.md` updated under `## [Unreleased]` if user-visible

## Performance impact

<!-- If you touched the pipeline modules, report wall-clock before/after on a known-size video.
     "Transcribed a 63-minute meeting in 8m12s before, 7m48s after" is the kind of data point worth recording. -->

## Related issues

<!-- e.g. Closes #42, Refs #37. Or "n/a". -->
