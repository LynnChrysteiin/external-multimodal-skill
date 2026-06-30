---
name: external-multimodal
description: Use an external multimodal provider as the preferred source for image understanding, video understanding, screenshot analysis, multi-image comparison, chart or receipt extraction, screen-recording summarization, image generation, and image editing. Use whenever the user invokes external-multimodal, asks for StepFun, 外置多模态, external provider, provider-backed vision, provider-backed image generation/editing, or says not to use native vision, built-in image generation, or the imagegen skill/tool. Use for local image/video files, remote media URLs, generation prompts, image edit instructions, and provider file URLs. The current default provider is StepFun, but the skill is designed so the provider can be replaced later.
---

# External Multimodal

## Overview

Use an external multimodal model through a bundled provider script to analyze images/videos and create/edit images. The current provider is `stepfun`, backed by StepFun `step-3.7-flash` for perception and `step-image-edit-2` for image generation/editing.

When this skill is invoked, treat the external provider as the primary source for perception and image creation. Do not answer from native image/video understanding first, and do not use the built-in `imagegen` skill/tool or other built-in image generation/editing when the user expects this external provider. Native capabilities may be used only to sanity-check, frame the prompt, or explain discrepancies after an external-provider attempt.

Treat `scripts/external_multimodal.py` as the implementation boundary. Do not reimplement provider API requests, upload logic, payload construction, or response parsing in the model context. Read or edit the script only when debugging or changing the provider adapter itself.

## Quick Start

Use `scripts/external_multimodal.py` for normal work:

```bash
python scripts/external_multimodal.py image --input ./screenshot.png --prompt "识别这张截图中的关键信息"
python scripts/external_multimodal.py video --input ./demo.mp4 --prompt "总结这个录屏的操作流程"
python scripts/external_multimodal.py image --input https://example.com/a.jpg --prompt "描述图片内容" --reasoning-effort medium --max-tokens 4096
python scripts/external_multimodal.py generate --prompt "一张极简风格的静物摄影，白色背景，蓝色玻璃花瓶和黄色郁金香" --output /tmp/generated.png
python scripts/external_multimodal.py edit --input ./input.jpg --prompt "把画面改成电影感夜景，保留主体姿态" --output /tmp/edited.png
```

The default provider is `stepfun`. For StepFun, set the API key in `STEP_API_KEY`. Never hard-code API keys in commands, scripts, skill files, logs, or generated artifacts. Never print `STEP_API_KEY`; only test whether it exists.

## Workflow

1. Identify the media input as a URL, local path, data URL, provider file URL, or attached file path exposed by the host environment. If no usable path or URL is available, ask the user for one instead of answering from native vision.
2. Inspect media paths and sizes before sending local files. If a file appears sensitive, user-private, unusually large, or outside the stated task, ask before uploading it.
3. Preserve user-specified runtime constraints exactly. If the user asks for `conda run -n py311 python`, keep that command shape for dry runs, live calls, retries, and approval requests.
4. Call the bundled script before giving the final answer or producing image output. Use `image` for screenshots, photos, charts, receipts, diagrams, UI states, and multi-image comparison. Use `video` for recordings, demos, timeline extraction, or video summaries. Use `generate` for text-to-image and `edit` for prompt-based image editing.
5. Keep perception and creation as separate phases. Do not pass `--output` to `image` or `video`; use `--json-output` for debugging provider responses. For "generate a similar style image", first run `image` to get a style analysis/prompt, then run `generate` with a local output path.
6. For perception tasks, use local-file default transport unless there is a reason to override it:
   - Local files: default `--transport files`; the script handles provider upload details.
   - Remote URLs: pass the URL directly.
   - One-off small local images: use `--transport base64` if persistent provider storage is undesirable.
7. For image generation/editing, pass a clear prompt and an `--output` path. Use `--image-size`, `--steps`, `--cfg-scale`, `--seed`, `--negative-prompt`, and `--text-mode` only when the user request calls for those controls.
8. Choose `--reasoning-effort` deliberately for perception tasks:
   - `low`: simple description, OCR-like extraction, short summary.
   - `medium`: default for comparison, screenshots, charts, and ordinary video summaries.
   - `high`: complex planning, code/UI diagnosis from screenshots, or detailed video timeline analysis.
9. Use enough output budget for perception tasks. The script defaults to `--max-tokens 4096`; keep that for detailed image/video analysis. Raise it when the user asks for long structured output, or lower `--reasoning-effort` if reasoning appears to consume too much budget.
10. Report the external provider result to the user as the main answer, plus any important caveats. For generation/editing, return the saved local output path or provider URL. If the provider fails, returns empty content, or truncates output, say that explicitly and either retry with a safer prompt/transport/token budget or ask how to proceed. Do not silently substitute native capabilities as if they came from the external provider.

## Provider Adapter

- Current default: `--provider stepfun`.
- StepFun-specific provider name, models, environment variable, formats, generation/edit options, limits, and troubleshooting live in `references/stepfun_provider.md`.
- If a future provider replaces StepFun, update the script adapter and add a provider reference file without changing this skill's name or user-facing trigger.

## Common Tasks

- Screenshot or UI analysis: use `image`, include the question and expected output format in `--prompt`.
- Multi-image comparison: pass multiple `--input` values to `image` and ask for the comparison criteria.
- Receipt, chart, or document image extraction: ask for structured JSON, Markdown table, or concise bullet output.
- Video summary or screen-recording timeline: use `video`; ask for key moments, actions, errors, timestamps if visible, and next steps.
- Text-to-image generation: use `generate`; write the result to `--output` when a local artifact is expected.
- Image editing or retouching: use `edit` with exactly one local input image and an edit instruction; write the result to `--output`.

## Failure Handling

Follow this troubleshooting ladder before giving up:

1. Confirm the runtime command and environment without exposing secrets. Use `source ~/.zshrc >/dev/null 2>&1` and `test -n "$STEP_API_KEY"`; do not run commands that print environment variable values.
2. Missing provider API key: tell the user which environment variable is required before a live call can run. Use `--dry-run` only for input and command-shape validation.
3. Missing SDK: report the dependency issue and suggest installing the provider SDK or switching to an existing Python environment with the package. If a network-restricted install or live provider call fails because of sandbox/network limits, retry the same command shape with the required network approval.
4. URL failure: verify the media URL with a lightweight fetch such as `curl -I`. If the URL is reachable but the provider fails, download the media to `/tmp` and retry as a local file through the script.
5. Empty or truncated content: retry once with a shorter, simpler prompt, `--reasoning-effort low`, `--max-tokens 4096` or higher, and `--json-output /tmp/external-multimodal-response.json` so the full response can be inspected.
6. Generation/editing failure: simplify the prompt, ensure the prompt is within provider limits, reduce requested complexity, and retry once with `--json-output` only when the task supports it.
7. Upload failure, `404`, `500`, or connection error: preserve the exact error message. For local perception files, retry once with `--transport base64`, `--reasoning-effort low`, `--max-tokens 4096`, and `--json-output /tmp/external-multimodal-response.json` before treating it as a provider or endpoint problem.
8. Video too large or long: check the current provider limits. Ask the user to trim/compress, or use `ffmpeg` to segment the file.
9. Still failing: summarize attempted steps, last error, and the safest next action. Do not silently substitute native vision or built-in image generation output.

## Reference

Read `references/stepfun_provider.md` when using the current StepFun provider and you need provider usage, supported formats, or troubleshooting details.
