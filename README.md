# External Multimodal Skill

A Codex skill for routing multimodal work to an external provider instead of relying on the current model's native image, video, or image-generation capabilities.

The current provider adapter is StepFun. The skill is intentionally named `external-multimodal` so the provider can be replaced later without changing the user-facing skill name.

## Capabilities

- Analyze local or remote images
- Analyze local or remote videos
- Compare multiple images
- Extract structured information from screenshots, charts, receipts, and document images
- Summarize screen recordings or demo videos
- Generate images from text prompts
- Edit or retouch an existing local image

## Current Provider

- Provider: StepFun
- Perception model: `step-3.7-flash`
- Image generation/editing model: `step-image-edit-2`
- Base URL: `https://api.stepfun.com/step_plan/v1`
- API key environment variable: `STEP_API_KEY`

API keys must stay in environment variables. Do not hard-code keys in commands, source files, prompts, logs, or generated artifacts.

## Install

Clone this repository into a Codex skills directory, or copy the `external-multimodal` folder into your skills path.

Common local install path:

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/LynnChrysteiin/external-multimodal-skill.git ~/.codex/skills/external-multimodal
```

Set the StepFun API key:

```bash
export STEP_API_KEY="your_api_key_here"
```

Install the Python SDK used by the provider adapter:

```bash
python -m pip install --upgrade "openai>=1.0"
```

## Usage

In Codex, ask to use `$external-multimodal` for image, video, generation, or editing tasks.

For new conversations, explicit invocation is the most reliable route because Codex also has a built-in `imagegen` skill/tool for generic image generation and editing prompts. Use `$external-multimodal`, `StepFun`, `external provider`, or `外置多模态` in the request when you want this skill to handle the task.

Examples:

```text
Use $external-multimodal to describe this screenshot.
Use $external-multimodal to summarize this screen recording.
Use $external-multimodal to generate an image in this style.
Use $external-multimodal to edit this image and add the missing sleeve.
```

The bundled CLI can also be run directly from the skill folder.

Analyze an image:

```bash
python scripts/external_multimodal.py image \
  --input ./screenshot.png \
  --prompt "识别这张截图中的关键信息"
```

Analyze a video:

```bash
python scripts/external_multimodal.py video \
  --input ./demo.mp4 \
  --prompt "总结这个录屏的操作流程"
```

Analyze a remote image:

```bash
python scripts/external_multimodal.py image \
  --input https://example.com/a.jpg \
  --prompt "描述图片内容" \
  --reasoning-effort medium
```

Generate an image:

```bash
python scripts/external_multimodal.py generate \
  --prompt "一张极简风格的静物摄影，白色背景，蓝色玻璃花瓶和黄色郁金香" \
  --output /tmp/generated.png
```

Edit an image:

```bash
python scripts/external_multimodal.py edit \
  --input ./input.jpg \
  --prompt "把画面改成电影感夜景，保留主体姿态" \
  --output /tmp/edited.png
```

Validate command shape without making a live provider request:

```bash
python scripts/external_multimodal.py image \
  --input ./screenshot.png \
  --prompt "描述图片内容" \
  --dry-run
```

## Notes

- Local image/video perception defaults to provider file upload.
- Use `--transport base64` for small one-off local images when persistent provider storage is undesirable.
- Use `--max-tokens 4096` or higher for detailed image/video analysis.
- If perception output is empty or truncated, retry with a shorter prompt, `--reasoning-effort low`, and `--json-output /tmp/external-multimodal-response.json`.
- For provider-specific options, formats, and troubleshooting, see `references/stepfun_provider.md`.

## Repository Layout

```text
external-multimodal/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── stepfun_provider.md
└── scripts/
    └── external_multimodal.py
```
