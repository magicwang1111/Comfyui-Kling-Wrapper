from .prediction import CustomVoiceResponse, Prediction


class CustomVoiceCreate(Prediction):
    voice_name: str
    voice_url: str
    video_id: str
    callback_url: str
    external_task_id: str

    def __init__(self):
        super().__init__()
        self._request_method = "POST"
        self._request_path = "/v1/general/custom-voices"
        self._query_prediction_info_method = "GET"
        self._query_prediction_info_path = "/v1/general/custom-voices"
        self._response_cls = CustomVoiceResponse


class CustomVoiceQuery(Prediction):
    def __init__(self, identifier=None):
        super().__init__()
        self.identifier = identifier
        self._request_method = "GET"
        self._request_path = "/v1/general/custom-voices"
        self._response_cls = CustomVoiceResponse

    def run(self, client):
        identifier = str(self.identifier or "").strip()
        if not identifier:
            raise ValueError("task_id_or_external_task_id is required.")
        resp = client.request(method=self._request_method, path=f"{self._request_path}/{identifier}")
        return self._response_cls(**resp.get("data"))
