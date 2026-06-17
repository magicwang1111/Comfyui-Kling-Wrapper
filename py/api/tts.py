from .prediction import Prediction, TTSResponse


class TTS(Prediction):
    text: str
    voice_id: str
    voice_language: str
    voice_speed: float

    def __init__(self):
        super().__init__()
        self._request_method = "POST"
        self._request_path = "/v1/audio/tts"
        self._response_cls = TTSResponse

    def run(self, client):
        resp = client.request(method=self._request_method, path=self._request_path, json=self.to_dict())
        return self._response_cls(**resp.get("data"))
