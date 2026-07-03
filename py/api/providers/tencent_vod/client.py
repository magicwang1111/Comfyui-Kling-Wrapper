from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import time
from typing import Any

import requests

from ..base import TencentVodVideoConfig

VOD_ENDPOINT = "vod.tencentcloudapi.com"
VOD_HTTP_URL = f"https://{VOD_ENDPOINT}/"
VOD_SERVICE = "vod"
VOD_VERSION = "2018-07-17"


class TencentVodError(RuntimeError):
    pass


class TencentVodClient:
    def __init__(self, config: TencentVodVideoConfig):
        self.config = config
        self.session = requests.Session()

    def close(self) -> None:
        self.session.close()

    @staticmethod
    def canonical_json(data: Any) -> str:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _sign(secret_key: str, date_str: str, string_to_sign: str) -> str:
        secret_date = hmac.new(
            ("TC3" + secret_key).encode("utf-8"),
            date_str.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        secret_service = hmac.new(secret_date, VOD_SERVICE.encode("utf-8"), hashlib.sha256).digest()
        secret_signing = hmac.new(secret_service, b"tc3_request", hashlib.sha256).digest()
        return hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    def _headers(self, action: str, payload: dict[str, Any]) -> dict[str, str]:
        timestamp = int(time.time())
        date_str = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).strftime("%Y-%m-%d")
        body = self.canonical_json(payload)
        canonical_request = "\n".join([
            "POST",
            "/",
            "",
            f"content-type:application/json; charset=utf-8\nhost:{VOD_ENDPOINT}\nx-tc-action:{action.lower()}\n",
            "content-type;host;x-tc-action",
            hashlib.sha256(body.encode("utf-8")).hexdigest(),
        ])
        credential_scope = f"{date_str}/{VOD_SERVICE}/tc3_request"
        string_to_sign = "\n".join([
            "TC3-HMAC-SHA256",
            str(timestamp),
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ])
        signature = self._sign(self.config.secret_key, date_str, string_to_sign)
        authorization = (
            f"TC3-HMAC-SHA256 Credential={self.config.secret_id}/{credential_scope}, "
            f"SignedHeaders=content-type;host;x-tc-action, Signature={signature}"
        )
        return {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": VOD_ENDPOINT,
            "X-TC-Action": action,
            "X-TC-Version": VOD_VERSION,
            "X-TC-Region": self.config.region,
            "X-TC-Timestamp": str(timestamp),
        }

    def request(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = self.canonical_json(payload)
        response = self.session.post(
            VOD_HTTP_URL,
            headers=self._headers(action, payload),
            data=body.encode("utf-8"),
            timeout=self.config.request_timeout,
        )
        try:
            decoded = response.json()
        except ValueError as exc:
            raise TencentVodError(
                f"{action} returned non-JSON HTTP {response.status_code}: {response.text[:500]}"
            ) from exc
        top = decoded.get("Response")
        if response.status_code != 200 or not isinstance(top, dict):
            raise TencentVodError(f"{action} HTTP {response.status_code}: {decoded}")
        if "Error" in top:
            error = top.get("Error") or {}
            raise TencentVodError(
                f"{action} Code={error.get('Code')}, Message={error.get('Message')}, "
                f"RequestId={top.get('RequestId')}"
            )
        return top
