# StepFun Provider Usage

Sources:
- https://platform.stepfun.com/docs/zh/guides/models/step-3.7-flash-quickstart
- https://platform.stepfun.com/docs/zh/guides/models/image
- https://platform.stepfun.com/docs/zh/guides/models/step-image-edit-2

## Contents

- [Provider](#provider)
- [Safe Execution](#safe-execution)
- [Commands](#commands)
- [Inputs](#inputs)
- [Options](#options)
- [Supported Formats And Limits](#supported-formats-and-limits)
- [Troubleshooting Ladder](#troubleshooting-ladder)

This is the current provider guide for the `external-multimodal` skill. It tells the agent which provider is configured and how to use the bundled script. The Python script owns API calls, uploads, request construction, response parsing, and image file decoding.

## Provider

- Provider adapter: `stepfun`
- Perception model: `step-3.7-flash`
- Image generation/editing model: `step-image-edit-2`
- Perception and Files API base URL configured in the script: `https://api.stepfun.com/v1`
- Image generation/editing base URL configured in the script: `https://api.stepfun.com/step_plan/v1`
- API key environment variable: `STEP_API_KEY`
- Python dependency for live calls: `openai>=1.0`
- Default script: `scripts/external_multimodal.py`

Do not hard-code API keys. Do not print `STEP_API_KEY`. Do not rebuild StepFun API requests manually when the script can be used. Do not collapse StepFun's perception/files and image generation/editing base URLs into one setting.

## Safe Execution

When the user specifies an environment such as `py311`, keep that command shape for dry runs, live calls, retries, and approval requests:

```bash
conda run -n py311 python scripts/external_multimodal.py image \
  --input /tmp/input.jpg \
  --transport base64 \
  --reasoning-effort low \
  --max-tokens 4096 \
  --json-output /tmp/external-multimodal-analysis.json \
  --prompt "请分析这张图的主题、构图、色彩、光影、材质、镜头感和可复现风格提示词。"
```

Check the API key only by presence:

```bash
source ~/.zshrc >/dev/null 2>&1
test -n "$STEP_API_KEY"
```

Never use commands that print the key, and never inline the key before a command.

## Commands

Analyze a remote image:

```bash
python scripts/external_multimodal.py image \
  --provider stepfun \
  --input https://example.com/a.jpg \
  --prompt "描述图片" \
  --max-tokens 4096
```

Analyze a local image:

```bash
python scripts/external_multimodal.py image \
  --provider stepfun \
  --input /tmp/input.jpg \
  --prompt "识别这张截图中的关键信息"
```

Analyze a local image after file upload fails, for example after provider `404` from the default `files` transport:

```bash
conda run -n py311 python scripts/external_multimodal.py image \
  --provider stepfun \
  --input /tmp/input.jpg \
  --transport base64 \
  --reasoning-effort low \
  --max-tokens 4096 \
  --json-output /tmp/external-multimodal-analysis.json \
  --prompt "请分析这张图的主题、构图、色彩、光影、材质、镜头感和可复现风格提示词。"
```

Analyze a local video:

```bash
python scripts/external_multimodal.py video \
  --provider stepfun \
  --input /tmp/demo.mp4 \
  --prompt "总结这个录屏的操作流程"
```

Generate an image from text:

```bash
python scripts/external_multimodal.py generate \
  --provider stepfun \
  --prompt "一张极简风格的静物摄影，白色背景，蓝色玻璃花瓶和黄色郁金香" \
  --output /tmp/generated.png
```

Edit a local image:

```bash
python scripts/external_multimodal.py edit \
  --provider stepfun \
  --input /tmp/input.jpg \
  --prompt "把画面改成电影感夜景，保留主体姿态" \
  --output /tmp/edited.png
```

Validate command shape without a live provider call:

```bash
python scripts/external_multimodal.py image \
  --provider stepfun \
  --input https://example.com/a.jpg \
  --prompt "描述图片" \
  --dry-run
```

Save the full provider response when debugging:

```bash
python scripts/external_multimodal.py image \
  --provider stepfun \
  --input /tmp/input.jpg \
  --prompt "请用三句话描述这张图片。" \
  --reasoning-effort low \
  --max-tokens 4096 \
  --json-output /tmp/external-multimodal-response.json
```

## Inputs

- `image`: remote image URL, local image path, data URL, or provider file URL.
- `video`: remote video URL, local video path, data URL, or provider file URL.
- `generate`: prompt only, no input file.
- `edit`: exactly one local image path.

For perception local files, keep the default transport unless there is a reason to override it. For editing, pass a local file; download remote images first.

For a task that asks to generate a similar-style image from a reference, use two separate phases:

1. Run `image` without `--output`, optionally with `--json-output`, to produce a style analysis and generation prompt.
2. Run `generate` with the derived, de-identified prompt and an `--output` image path.

## Options

- `--reasoning-effort low|medium|high`: use `low` for simple description, `medium` for default analysis, `high` for complex reasoning. If content is empty or truncated, retry with `low` because reasoning can consume output budget on some providers.
- `--max-tokens N`: maximum output budget. The script defaults to `4096`; use at least this for detailed descriptions, and raise it for long structured reports.
- `--detail high|low|auto`: image detail level; default is `high`.
- `--transport files|base64|url`: use the default `files` for local files; use `base64` for small one-off images; use `url` only for URL-like inputs.
- `--json-output PATH`: write full provider response for debugging.
- `--dry-run`: validate inputs and print a provider-neutral command summary.
- `--output PATH`: save generated or edited image output locally. Use only with `generate` or `edit`; use `--json-output` for `image` or `video`.
- `--image-size SIZE`: generated image size. Current StepFun values are `1024x1024`, `768x1360`, `896x1184`, `1360x768`, `1184x896`.
- `--steps N`: generation/editing steps, default `8`, range `1` to `50`.
- `--cfg-scale N`: generation/editing guidance scale, default `1.0`, range `1.0` to `10.0`.
- `--seed N`: generation/editing seed, optional, range `0` to `2147483647`.
- `--negative-prompt TEXT`: optional negative prompt for generation/editing.
- `--text-mode`: enable StepFun text-scene optimization when the prompt asks for visible text in the image.

## Supported Formats And Limits

- Perception images: JPG, JPEG, PNG, GIF, WebP.
- Videos: MP4, QuickTime MOV, Matroska MKV.
- Recommended video envelope: 128 MB or smaller, 5 minutes or shorter.
- Generation/editing prompt limit: 512 characters.
- Editing input image limit: one local image, up to 4096x4096.
- Step Image Edit 2 returns one generated/edited image per request.

For oversized video, split with ffmpeg:

```bash
ffmpeg -i input.mp4 -c copy -f segment -segment_time 120 -reset_timestamps 1 output_%d.mp4
```

## Troubleshooting Ladder

1. Confirm the command can see the API key:

```bash
source ~/.zshrc
test -n "$STEP_API_KEY"
```

2. Confirm the Python environment has the SDK:

```bash
python -c "from openai import OpenAI; print('openai ok')"
```

If this fails, switch to an environment with `openai>=1.0` or install the dependency. In this workspace, `conda run -n py311 python` has worked for live calls.

3. Validate command shape with `--dry-run`.

4. For remote URL failures, verify the URL first:

```bash
curl -I https://example.com/a.jpg
```

If the URL is reachable but the provider fails, download to `/tmp` and retry as a local file:

```bash
curl -L https://example.com/a.jpg -o /tmp/external-multimodal-input.jpg
python scripts/external_multimodal.py image \
  --provider stepfun \
  --input /tmp/external-multimodal-input.jpg \
  --prompt "描述图片"
```

5. For empty or truncated perception output, retry once with a simpler prompt, `--reasoning-effort low`, `--max-tokens 4096` or higher, and `--json-output /tmp/external-multimodal-response.json`.

6. For upload failures or provider `404` from the default `files` transport, first check that perception and file upload are using `https://api.stepfun.com/v1`, not the Step Plan image base URL. Then verify file path, format, size, and network access. For local images, retry once with `--transport base64`, `--reasoning-effort low`, `--max-tokens 4096`, and `--json-output /tmp/external-multimodal-analysis.json`.

7. For generation/editing failures, check prompt length, simplify the requested change, set `--text-mode` when rendering visible text, and retry once with a fixed `--seed` if reproducibility matters.

8. For video failures, check format, 128 MB recommendation, and 5 minute recommendation.

9. For slow responses, use local-file mode when a remote URL is unreliable, reduce image resolution when acceptable, keep video short, and keep prompts specific.

10. If all steps fail, report the exact command shape, transport, attempted fallback, and final error. Do not invent visual results and do not present native vision or built-in generation output as external-provider output.
