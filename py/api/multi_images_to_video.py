from .prediction import Prediction, VideoPredictionResponse


class MultiImages2Video(Prediction):
    image: str
    model_name: str
    image_list: list
    image_tail: str
    prompt: str
    negative_prompt: str
    mode: str
    duration: str
    aspect_ratio: str
    watermark_info: dict

    def __init__(self):
        super().__init__()
        self._request_method = "POST"
        self._request_path = "/v1/videos/image2video"
        self._query_prediction_info_method = "GET"
        self._query_prediction_info_path = "/v1/videos/image2video"
        self._response_cls = VideoPredictionResponse
