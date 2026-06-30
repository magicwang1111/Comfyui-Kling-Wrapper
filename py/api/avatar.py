from .prediction import Prediction, VideoPredictionResponse


class Avatar(Prediction):
    image: str
    audio_id: str
    sound_file: str
    prompt: str
    mode: str

    def __init__(self):
        super().__init__()
        self._request_method = "POST"
        self._request_path = "/v1/videos/avatar/image2video"
        self._query_prediction_info_method = "GET"
        self._query_prediction_info_path = "/v1/videos/avatar/image2video"
        self._response_cls = VideoPredictionResponse
