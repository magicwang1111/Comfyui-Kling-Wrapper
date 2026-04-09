from .prediction import ElementPredictionResponse, Prediction


class AdvancedCustomElements(Prediction):
    name: str
    type: str
    image: str
    image_list: list
    video_url: str
    element_voice_id: str

    def __init__(self):
        super().__init__()
        self._request_method = "POST"
        self._request_path = "/v1/general/advanced-custom-elements"
        self._query_prediction_info_method = "GET"
        self._query_prediction_info_path = "/v1/general/advanced-custom-elements"
        self._response_cls = ElementPredictionResponse
