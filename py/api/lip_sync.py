from .prediction import FaceIdentifyResponse, Prediction, VideoPredictionResponse


class LipSyncInput(Prediction):
    mode: str
    text: str
    voice_id: str
    voice_language: str
    voice_speed: float
    audio_id: str
    audio_url: str
    audio_duration_ms: int
    sound_start_time: int
    sound_end_time: int


class FaceIdentify(Prediction):
    video_id: str
    video_url: str

    def __init__(self):
        super().__init__()
        self._request_method = "POST"
        self._request_path = "/v1/videos/identify-face"

    def run(self, client):
        resp = client.request(method=self._request_method, path=self._request_path, json=self.to_dict())
        return FaceIdentifyResponse(**resp.get("data"))


class AdvancedLipSync(Prediction):
    session_id: str
    face_choose: list

    def __init__(self):
        super().__init__()
        self._request_method = "POST"
        self._request_path = "/v1/videos/advanced-lip-sync"
        self._query_prediction_info_method = "GET"
        self._query_prediction_info_path = "/v1/videos/advanced-lip-sync"
        self._response_cls = VideoPredictionResponse
