from .prediction import Prediction, VideoPredictionResponse


class MotionControl(Prediction):
    model_name: str
    prompt: str
    negative_prompt: str
    mode: str
    duration: str
    reference_image: str
    reference_video: str
    element_list: list
    watermark_info: dict

    def __init__(self):
        super().__init__()
        self._request_method = "POST"
        self._request_path = "/v1/videos/motion-control"
        self._query_prediction_info_method = "GET"
        self._query_prediction_info_path = "/v1/videos/motion-control"
        self._response_cls = VideoPredictionResponse
