from .prediction import ElementPredictionResponse, Prediction


class AdvancedCustomElements(Prediction):
    element_name: str
    element_description: str
    reference_type: str  # "image_refer" or "video_refer"
    element_image_list: dict
    element_video_list: dict
    element_voice_id: str

    def __init__(self):
        super().__init__()
        self._request_method = "POST"
        self._request_path = "/v1/general/advanced-custom-elements"
        self._query_prediction_info_method = "GET"
        self._query_prediction_info_path = "/v1/general/advanced-custom-elements"
        self._response_cls = ElementPredictionResponse
