from .prediction import Prediction, VideoPredictionResponse


class MotionControl(Prediction):
    model_name: str
    prompt: str
    mode: str
    image_url: str
    video_url: str
    keep_original_sound: str
    character_orientation: str
    negative_prompt: str
    duration: str
    element_list: list
    watermark_info: dict

    def __init__(self):
        super().__init__()
        self._request_method = "POST"
        self._request_path = "/v1/videos/motion-control"
        self._query_prediction_info_method = "GET"
        self._query_prediction_info_path = "/v1/videos/motion-control"
        self._response_cls = VideoPredictionResponse
