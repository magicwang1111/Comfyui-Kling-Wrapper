from .prediction import ElementPredictionResponse, Prediction


class AdvancedCustomElements(Prediction):
    name: str
    type: str
    element_name: str
    element_type: str
    elementName: str
    description: str
    element_description: str
    elementDescription: str
    reference_type: str  # "image_refer" or "video_refer"
    image: str
    image_list: list
    element_image_list: dict
    elementImageList: str
    frontal_image: str   # base64, required for image_refer
    refer_images: list   # base64 list, optional for image_refer (1-3 images)
    video_url: str
    element_video_list: list  # list with 1 video URL, required for video_refer
    elementVideoList: str
    element_voice_id: str
    voice_id: str        # optional

    def __init__(self):
        super().__init__()
        self._request_method = "POST"
        self._request_path = "/v1/general/advanced-custom-elements"
        self._query_prediction_info_method = "GET"
        self._query_prediction_info_path = "/v1/general/advanced-custom-elements"
        self._response_cls = ElementPredictionResponse
