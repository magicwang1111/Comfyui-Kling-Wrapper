import time
import jwt
import httpx
from .exceptions import KLingAPIError
from enum import Enum


DEFAULT_GET_RETRY_COUNT = 3
DEFAULT_GET_RETRY_DELAY = 1.0
DEFAULT_CONNECT_RETRY_COUNT = 2


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code != 200 or 'data' not in resp.json():
        raise KLingAPIError.from_response(resp)


class ApiLocation(Enum):
    CHINA = "https://api-beijing.klingai.com"
    GLOBAL = "https://api-singapore.klingai.com"


class Client:
    __token = None
    __client = None

    def __init__(self, access_key, secret_key, in_china=True, timeout=30, poll_interval=1.0, ttl=1800):
        super().__init__()
        self._access_key = access_key
        self._secret_key = secret_key
        self._timeout = timeout
        self._create_time = None
        self._ttl = ttl
        self._area = ApiLocation.CHINA if in_china else ApiLocation.GLOBAL

        self.poll_interval = poll_interval

    def request(self, method: str, path: str, **kwargs) -> dict:
        method_upper = str(method or "").upper()
        if "json" in kwargs:
            import json as _json
            _preview = {k: (v[:60] + "...[truncated]" if isinstance(v, str) and len(v) > 60 else v) for k, v in kwargs["json"].items()}
            print(f"[KLING DEBUG] {method} {path} payload keys={list(kwargs['json'].keys())}")
            print(f"[KLING DEBUG] payload preview: {_json.dumps(_preview, default=str)[:500]}")
        retry_count = DEFAULT_GET_RETRY_COUNT if method_upper == "GET" else DEFAULT_CONNECT_RETRY_COUNT
        for attempt in range(1, retry_count + 1):
            try:
                resp = self._client.request(method, path, **kwargs)
                break
            except httpx.ConnectError as exc:
                if attempt < retry_count:
                    print(
                        f"[KLING DEBUG] retrying {method_upper} {path} after connect error "
                        f"({attempt}/{retry_count}): {exc}"
                    )
                    self.close()
                    time.sleep(DEFAULT_GET_RETRY_DELAY)
                    continue
                raise ConnectionError(
                    f"Kling API request failed while connecting for {method} {path}: {exc}"
                ) from exc
            except httpx.TimeoutException as exc:
                if method_upper == "GET" and attempt < retry_count:
                    print(
                        f"[KLING DEBUG] retrying {method_upper} {path} after timeout "
                        f"({attempt}/{retry_count}): {exc}"
                    )
                    self.close()
                    time.sleep(DEFAULT_GET_RETRY_DELAY)
                    continue
                raise TimeoutError(
                    f"Kling API request timed out after {self._timeout}s while waiting for {method} {path}. "
                    "Try increasing the client request_timeout, especially for advanced element creation "
                    "with multiple reference images."
                ) from exc
            except httpx.TransportError as exc:
                if method_upper == "GET" and attempt < retry_count:
                    print(
                        f"[KLING DEBUG] retrying {method_upper} {path} after transport error "
                        f"({attempt}/{retry_count}): {exc}"
                    )
                    self.close()
                    time.sleep(DEFAULT_GET_RETRY_DELAY)
                    continue
                raise ConnectionError(
                    f"Kling API request failed during transport for {method} {path}: {exc}"
                ) from exc
        _raise_for_status(resp)
        return resp.json()

    @property
    def _is_expired(self):
        if self._create_time is None:
            return True
        return time.time() - self._create_time > self._ttl

    @property
    def _token(self):
        self._create_time = time.time()
        headers = {
            "alg": "HS256",
            "typ": "JWT"
        }
        payload = {
            "iss": self._access_key,
            "exp": int(self._create_time) + self._ttl,
            "nbf": int(self._create_time) - 5
        }
        self.__token = jwt.encode(payload, self._secret_key, headers=headers)
        print(f'create token: {self._create_time}')
        return self.__token

    @property
    def _client(self) -> httpx.Client:
        if self.__client is None or self._is_expired:
            base_url = str(self._area.value)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}"
            }
            timeout = httpx.Timeout(connect=10.0, read=self._timeout, write=self._timeout, pool=self._timeout)
            self.__client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout)
        return self.__client

    def close(self) -> None:
        if self.__client is not None:
            self.__client.close()
            self.__client = None
