#!/usr/bin/env python3
"""Call an external multimodal provider for perception and image creation."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_PROVIDER = "stepfun"
STEPFUN_BASE_URL = "https://api.stepfun.com/step_plan/v1"
STEPFUN_PERCEPTION_MODEL = "step-3.7-flash"
STEPFUN_IMAGE_MODEL = "step-image-edit-2"
STEPFUN_API_KEY_ENV = "STEP_API_KEY"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}
STEPFUN_IMAGE_SIZES = {"1024x1024", "768x1360", "896x1184", "1360x768", "1184x896"}


class MultimodalCliError(Exception):
    """User-correctable CLI error."""


def is_remote_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


def is_stepfile_url(value: str) -> bool:
    return value.startswith("stepfile://")


def describe_input(value: str) -> dict[str, str]:
    if is_remote_url(value):
        return {"kind": "remote_url", "value": value}
    if is_stepfile_url(value):
        return {"kind": "provider_file_url", "value": "provider_file_url"}
    if value.startswith("data:"):
        return {"kind": "data_url", "value": "data_url"}
    return {"kind": "local_file", "value": str(Path(value).expanduser())}


def guess_mime(path: Path, kind: str) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if mime:
        return mime
    return "image/jpeg" if kind in {"image", "edit"} else "video/mp4"


def validate_local_file(path: Path, kind: str) -> None:
    if not path.exists():
        raise MultimodalCliError(f"Input file does not exist: {path}")
    if not path.is_file():
        raise MultimodalCliError(f"Input path is not a file: {path}")

    suffix = path.suffix.lower()
    allowed = IMAGE_EXTENSIONS if kind in {"image", "edit"} else VIDEO_EXTENSIONS
    if suffix not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise MultimodalCliError(f"Unsupported {kind} extension '{suffix}'. Allowed: {allowed_text}")

    if kind == "video":
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > 128:
            raise MultimodalCliError(
                f"Video is {size_mb:.1f} MB. Current provider recommends videos within 128 MB; "
                "trim or compress it before upload."
            )


def validate_image_options(args: argparse.Namespace) -> None:
    if len(args.prompt) > 512:
        raise MultimodalCliError("Prompt is too long for the current image provider; keep it within 512 characters.")
    if args.negative_prompt and len(args.negative_prompt) > 512:
        raise MultimodalCliError("Negative prompt is too long for the current image provider; keep it within 512 characters.")
    if args.image_size not in STEPFUN_IMAGE_SIZES:
        allowed = ", ".join(sorted(STEPFUN_IMAGE_SIZES))
        raise MultimodalCliError(f"Unsupported image size '{args.image_size}'. Allowed: {allowed}")
    if not (1 <= args.steps <= 50):
        raise MultimodalCliError("--steps must be between 1 and 50.")
    if not (1.0 <= args.cfg_scale <= 10.0):
        raise MultimodalCliError("--cfg-scale must be between 1.0 and 10.0.")
    if args.seed is not None and not (0 <= args.seed <= 2147483647):
        raise MultimodalCliError("--seed must be between 0 and 2147483647.")


def encode_data_url(path: Path, kind: str) -> str:
    mime = guess_mime(path, kind)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def upload_file(client: Any, path: Path) -> str:
    with path.open("rb") as file_obj:
        uploaded = client.files.create(file=file_obj, purpose="storage")
    return f"stepfile://{uploaded.id}"


def resolve_media_url(
    *,
    client: Any | None,
    value: str,
    kind: str,
    transport: str,
    dry_run: bool,
) -> str:
    if is_remote_url(value) or is_stepfile_url(value) or value.startswith("data:"):
        return value

    path = Path(value).expanduser()
    validate_local_file(path, kind)

    if transport == "url":
        raise MultimodalCliError("--transport url requires a remote URL, data URL, or provider file URL input")
    if transport == "base64":
        return encode_data_url(path, kind)
    if dry_run:
        return f"stepfile://DRY_RUN_{path.name}"
    if client is None:
        raise MultimodalCliError("Internal error: live file upload requested without a client")
    return upload_file(client, path)


def build_perception_payload(args: argparse.Namespace, media_urls: list[str]) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": args.prompt}]

    for media_url in media_urls:
        if args.kind == "image":
            image_url: dict[str, Any] = {"url": media_url}
            if args.detail != "auto":
                image_url["detail"] = args.detail
            content.append({"type": "image_url", "image_url": image_url})
        else:
            content.append({"type": "video_url", "video_url": {"url": media_url}})

    return {
        "model": STEPFUN_PERCEPTION_MODEL,
        "messages": [{"role": "user", "content": content}],
        "reasoning_effort": args.reasoning_effort,
        "max_tokens": args.max_tokens,
    }


def image_extra_body(args: argparse.Namespace) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "cfg_scale": args.cfg_scale,
        "steps": args.steps,
        "text_mode": args.text_mode,
    }
    if args.seed is not None:
        extra["seed"] = args.seed
    if args.negative_prompt:
        extra["negative_prompt"] = args.negative_prompt
    return extra


def response_to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "to_dict"):
        return response.to_dict()
    return json.loads(response.model_dump_json())


def response_item_to_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "to_dict"):
        return item.to_dict()
    if isinstance(item, dict):
        return item
    return dict(item)


def default_output_path(task: str) -> Path:
    return Path("/tmp") / f"external-multimodal-{task}-{int(time.time())}.png"


def decode_image_response(response: Any, output: str | None, task: str) -> dict[str, Any]:
    item = response.data[0]
    item_dict = response_item_to_dict(item)
    result: dict[str, Any] = {
        "finish_reason": item_dict.get("finish_reason"),
        "seed": item_dict.get("seed"),
    }
    b64_json = item_dict.get("b64_json")
    url = item_dict.get("url")

    if b64_json:
        output_path = Path(output).expanduser() if output else default_output_path(task)
        output_path.write_bytes(base64.b64decode(b64_json))
        result["output"] = str(output_path)
    if url:
        result["url"] = url
        if output:
            result["note"] = "Provider returned a URL; download it separately if a local file is required."
    return result


def extract_text(response: Any) -> str:
    choice = response.choices[0]
    content = choice.message.content
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def provider_api_key_env(provider: str) -> str:
    if provider == "stepfun":
        return STEPFUN_API_KEY_ENV
    raise MultimodalCliError(f"Unsupported provider: {provider}")


def redact_secrets(text: str) -> str:
    redacted = text
    for env_name in (STEPFUN_API_KEY_ENV,):
        secret = os.environ.get(env_name)
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def create_client(provider: str, api_key: str) -> Any:
    if provider != "stepfun":
        raise MultimodalCliError(f"Unsupported provider: {provider}")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise MultimodalCliError("Missing dependency: install with `pip install --upgrade 'openai>=1.0'`.") from exc
    return OpenAI(api_key=api_key, base_url=STEPFUN_BASE_URL)


def generate_image(client: Any, args: argparse.Namespace) -> dict[str, Any]:
    validate_image_options(args)
    response = client.images.generate(
        model=STEPFUN_IMAGE_MODEL,
        prompt=args.prompt,
        response_format=args.response_format,
        size=args.image_size,
        n=1,
        extra_body=image_extra_body(args),
    )
    if args.json_output:
        Path(args.json_output).expanduser().write_text(json.dumps(response_to_dict(response), ensure_ascii=False, indent=2))
    return decode_image_response(response, args.output, "generate")


def edit_image(client: Any, args: argparse.Namespace) -> dict[str, Any]:
    if len(args.inputs) != 1:
        raise MultimodalCliError("Edit mode accepts exactly one --input image.")
    if is_remote_url(args.inputs[0]) or args.inputs[0].startswith("data:") or is_stepfile_url(args.inputs[0]):
        raise MultimodalCliError("Edit mode currently requires a local image file. Download remote images before editing.")
    input_path = Path(args.inputs[0]).expanduser()
    validate_local_file(input_path, "edit")
    validate_image_options(args)

    with input_path.open("rb") as image_file:
        response = client.images.edit(
            model=STEPFUN_IMAGE_MODEL,
            image=image_file,
            prompt=args.prompt,
            response_format=args.response_format,
            extra_body=image_extra_body(args),
        )
    if args.json_output:
        Path(args.json_output).expanduser().write_text(json.dumps(response_to_dict(response), ensure_ascii=False, indent=2))
    return decode_image_response(response, args.output, "edit")


def build_dry_run_summary(args: argparse.Namespace) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "provider": args.provider,
        "task": args.kind,
        "live_call": False,
        "prompt_chars": len(args.prompt),
    }
    if args.inputs:
        summary["input_count"] = len(args.inputs)
        summary["inputs"] = [describe_input(value) for value in args.inputs]
    if args.kind in {"image", "video"}:
        summary["transport"] = args.transport
        summary["reasoning_effort"] = args.reasoning_effort
        summary["max_tokens"] = args.max_tokens
    if args.kind == "image":
        summary["detail"] = args.detail
    if args.kind in {"generate", "edit"}:
        summary.update(
            {
                "image_model": STEPFUN_IMAGE_MODEL,
                "image_size": args.image_size,
                "response_format": args.response_format,
                "steps": args.steps,
                "cfg_scale": args.cfg_scale,
                "seed": args.seed,
                "text_mode": args.text_mode,
                "has_negative_prompt": bool(args.negative_prompt),
                "output": args.output or str(default_output_path(args.kind)),
            }
        )
    return summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Use an external multimodal provider for perception, image generation, or image editing.",
    )
    parser.add_argument("kind", choices=["image", "video", "generate", "edit"], help="Task type.")
    parser.add_argument("--provider", choices=["stepfun"], default=DEFAULT_PROVIDER, help="External provider adapter.")
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        dest="inputs",
        help="Media input. Required for image/video/edit tasks; repeat for multiple images.",
    )
    parser.add_argument("--prompt", required=True, help="Question, generation prompt, or edit instruction.")
    parser.add_argument("--transport", choices=["files", "base64", "url"], default="files", help="How to send local perception files.")
    parser.add_argument("--detail", choices=["high", "low", "auto"], default="high", help="Image detail level for perception.")
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"], default="medium", help="Provider reasoning effort for perception.")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Maximum perception output tokens.")
    parser.add_argument("--output", help="Output path for generated or edited image files. Defaults to /tmp.")
    parser.add_argument("--response-format", choices=["b64_json", "url"], default="b64_json", help="Generated/edited image return format.")
    parser.add_argument("--image-size", default="1024x1024", help="Generated image size.")
    parser.add_argument("--steps", type=int, default=8, help="Image generation/editing steps.")
    parser.add_argument("--cfg-scale", type=float, default=1.0, help="Image generation/editing guidance scale.")
    parser.add_argument("--seed", type=int, help="Image generation/editing random seed.")
    parser.add_argument("--negative-prompt", default="", help="Negative prompt for image generation/editing.")
    parser.add_argument("--text-mode", action="store_true", help="Enable text-scene optimization for image generation/editing.")
    parser.add_argument("--json-output", help="Write the full JSON response for perception tasks.")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print a provider-neutral command summary.")
    args = parser.parse_args(argv)

    if args.kind in {"image", "video", "edit"} and not args.inputs:
        raise MultimodalCliError(f"{args.kind} mode requires --input.")
    if args.kind == "generate" and args.inputs:
        raise MultimodalCliError("Generate mode does not accept --input; use edit mode for image editing.")
    if args.kind == "video" and len(args.inputs) > 1:
        raise MultimodalCliError("Video mode accepts exactly one --input.")
    if args.kind == "video" and args.detail != "high":
        raise MultimodalCliError("--detail is only valid for image perception tasks.")
    if args.kind in {"image", "video"} and args.output:
        raise MultimodalCliError("--output is only valid for generate/edit tasks; use --json-output for perception responses.")
    return args


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv or sys.argv[1:])

        api_key_env = provider_api_key_env(args.provider)
        api_key = os.environ.get(api_key_env)
        if not args.dry_run and not api_key:
            raise MultimodalCliError(f"Missing {api_key_env}. Set it before making a live provider request.")

        if args.dry_run:
            if args.kind in {"image", "video"}:
                for value in args.inputs:
                    if not (is_remote_url(value) or is_stepfile_url(value) or value.startswith("data:")):
                        validate_local_file(Path(value).expanduser(), args.kind)
            if args.kind in {"generate", "edit"}:
                validate_image_options(args)
            if args.kind == "edit":
                edit_input = Path(args.inputs[0]).expanduser()
                validate_local_file(edit_input, "edit")
            print(json.dumps(build_dry_run_summary(args), ensure_ascii=False, indent=2))
            return 0

        client = create_client(args.provider, api_key or "")

        if args.kind == "generate":
            print(json.dumps(generate_image(client, args), ensure_ascii=False, indent=2))
            return 0
        if args.kind == "edit":
            print(json.dumps(edit_image(client, args), ensure_ascii=False, indent=2))
            return 0

        media_urls = [
            resolve_media_url(
                client=client,
                value=value,
                kind=args.kind,
                transport=args.transport,
                dry_run=False,
            )
            for value in args.inputs
        ]
        payload = build_perception_payload(args, media_urls)
        response = client.chat.completions.create(**payload)
        print(extract_text(response))

        if args.json_output:
            output_path = Path(args.json_output).expanduser()
            output_path.write_text(json.dumps(response_to_dict(response), ensure_ascii=False, indent=2))

        return 0
    except MultimodalCliError as exc:
        print(f"error: {redact_secrets(str(exc))}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: external multimodal request failed: {redact_secrets(str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
