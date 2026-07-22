#!/usr/bin/env python3
"""Register four clothing images as one persistent Tencent VOD element."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import oss2
from PIL import Image, ImageOps


REPO_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = REPO_ROOT.parents[1]
for path in (COMFYUI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from py.api.providers import (  # noqa: E402
    AdvancedElementCreateRequest,
    TencentVodVideoConfig,
    TencentVodVideoProvider,
)


DEFAULT_FRONTAL_IMAGE = Path(
    r"D:\测试素材\20260625衣服资产\B250246350DY_松烁沙\B250246350DY_松烁沙1.png"
)
DEFAULT_REFERENCE_IMAGES = [
    Path(r"D:\测试素材\20260625衣服资产\B250246350DY_松烁沙\B250246350DY_松烁沙7H03 女_B250246350DY-松烁沙7H03 2.png"),
    Path(r"D:\测试素材\20260625衣服资产\B250246350DY_松烁沙\B250246350DY_松烁沙7H03 女_B250246350DY-松烁沙7H03 7.jpg"),
    Path(r"D:\测试素材\20260625衣服资产\B250246350DY_松烁沙\B250246350DY_松烁沙7H03 女_B250246350DY-松烁沙7H03 4.jpg"),
]
DEFAULT_REPORT = Path(__file__).with_name("tencent_vod_clothing_asset_report.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register a Tencent VOD clothing element from four images.")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config.local.json")
    parser.add_argument("--frontal-image", type=Path, default=DEFAULT_FRONTAL_IMAGE)
    parser.add_argument("--reference-images", type=Path, nargs="+", default=DEFAULT_REFERENCE_IMAGES)
    parser.add_argument("--element-name", default="B250246350DY松烁沙")
    parser.add_argument(
        "--element-description",
        default="波司登米白色连帽羽绒服，包含正面、背面、袖标和胸标细节。",
    )
    parser.add_argument("--tag-list-json", default="", help="Optional Tencent TagList JSON array.")
    parser.add_argument("--image-size", type=int, default=1024)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--keep-oss-inputs", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def config_value(config: dict[str, Any], primary: str, fallback: str | None = None) -> Any:
    value = config.get(primary)
    if value in (None, "") and fallback:
        value = config.get(fallback)
    if value in (None, ""):
        raise KeyError(f"Missing config value: {primary}")
    return value


def build_bucket(config: dict[str, Any]) -> oss2.Bucket:
    endpoint = str(config_value(config, "oss_endpoint"))
    if "://" not in endpoint:
        endpoint = f"https://{endpoint}"
    auth = oss2.Auth(
        config_value(config, "oss_access_key_id"),
        config_value(config, "oss_access_key_secret"),
    )
    return oss2.Bucket(auth, endpoint, config_value(config, "oss_bucket"))


def make_provider(config: dict[str, Any]) -> TencentVodVideoProvider:
    return TencentVodVideoProvider(TencentVodVideoConfig(
        secret_id=str(config_value(config, "tencent_secret_id", "secret_id")),
        secret_key=str(config_value(config, "tencent_secret_key", "secret_key")),
        sub_app_id=int(config_value(config, "tencent_sub_app_id", "sub_app_id")),
        region=str(config.get("tencent_region") or config.get("region") or "ap-guangzhou"),
        request_timeout=int(config.get("tencent_request_timeout") or 120),
        poll_interval=float(config.get("tencent_poll_interval") or 5.0),
        max_wait_seconds=int(config.get("tencent_max_wait_seconds") or 3600),
    ))


def prepare_image(source: Path, destination: Path, image_size: int) -> None:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        image.thumbnail((image_size, image_size), Image.Resampling.LANCZOS)
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            background.alpha_composite(rgba)
            image = background.convert("RGB")
        else:
            image = image.convert("RGB")
        image.save(destination, "JPEG", quality=92, optimize=True)


def upload_images(
    bucket: oss2.Bucket,
    config: dict[str, Any],
    images: list[Path],
) -> tuple[list[str], list[str]]:
    prefix = str(config.get("oss_prefix") or "").strip("/")
    run_id = f"clothing-element-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    expires = int(config.get("oss_signed_url_expires") or 86400)
    urls, keys = [], []
    for index, path in enumerate(images, 1):
        key = "/".join(part for part in (prefix, run_id, path.name) if part)
        print(f"[upload {index}/{len(images)}] {path.name}", flush=True)
        bucket.put_object_from_file(key, str(path))
        keys.append(key)
        urls.append(bucket.sign_url("GET", key, expires, slash_safe=True))
    return urls, keys


def parse_tag_list(raw: str) -> list[dict[str, Any]] | None:
    if not raw.strip():
        return None
    value = json.loads(raw)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("--tag-list-json must decode to an array of objects.")
    return value


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    source_images = [args.frontal_image, *args.reference_images]
    if len(source_images) < 2 or len(source_images) > 4:
        raise SystemExit("Tencent VOD elements require 1 frontal image plus 1-3 reference images.")
    for path in source_images:
        if not path.is_file():
            raise SystemExit(f"Missing clothing image: {path}")
    if not 1 <= len(args.element_name) <= 20:
        raise SystemExit("--element-name must contain 1-20 characters.")
    if not 1 <= len(args.element_description) <= 100:
        raise SystemExit("--element-description must contain 1-100 characters.")
    if args.image_size <= 0:
        raise SystemExit("--image-size must be positive.")
    tag_list = parse_tag_list(args.tag_list_json)

    print("Tencent VOD clothing element registration")
    print("Element name:", args.element_name)
    print("Frontal image:", args.frontal_image)
    for index, path in enumerate(args.reference_images, 1):
        print(f"Reference image {index}:", path)
    print("Resize limit:", f"{args.image_size}px")
    print("The created element is persistent and will not be deleted by this script.")
    if args.dry_run:
        print("Dry run only. No upload or Tencent VOD request was made.")
        return 0

    bucket = build_bucket(config)
    provider = make_provider(config)
    object_keys: list[str] = []
    retain_oss_inputs = args.keep_oss_inputs
    report: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "element_name": args.element_name,
        "element_description": args.element_description,
        "frontal_image": str(args.frontal_image),
        "reference_images": [str(path) for path in args.reference_images],
        "ok": False,
    }
    started = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory(prefix="tencent-clothing-element-") as temp_dir:
            prepared = []
            for index, source in enumerate(source_images, 1):
                destination = Path(temp_dir) / f"image-{index}.jpg"
                prepare_image(source, destination, args.image_size)
                prepared.append(destination)
            urls, object_keys = upload_images(bucket, config, prepared)
            result = provider.create_element(AdvancedElementCreateRequest(
                element_name=args.element_name,
                element_description=args.element_description,
                reference_type="image_refer",
                element_image_list={
                    "frontal_image": urls[0],
                    "refer_images": [{"image_url": url} for url in urls[1:]],
                },
                tag_list=tag_list,
            ))
            queried = provider.query_element("element_id", result.element_id)
            report.update({
                "ok": True,
                "task_id": result.task_id,
                "request_id": result.request_id,
                "element_id": result.element_id,
                "query_element_id": queried.element_id,
                "element": result.element,
            })
            print("Created persistent clothing element:", result.element_id, flush=True)
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        retain_oss_inputs = retain_oss_inputs or isinstance(exc, TimeoutError)
        print("Registration failed:", report["error"], flush=True)
    finally:
        report["elapsed_s"] = round(time.perf_counter() - started, 4)
        report["oss_inputs_retained"] = retain_oss_inputs
        provider.close()
        if object_keys and not retain_oss_inputs:
            for key in object_keys:
                try:
                    bucket.delete_object(key)
                except Exception as exc:
                    print(f"[cleanup-fail] OSS {key}: {exc}", flush=True)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Report:", args.report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
