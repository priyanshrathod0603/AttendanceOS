from recognition.recognizer import FaceRecognizer


def test_blank_source_falls_back_to_default_camera_index():
    recognizer = FaceRecognizer(source="   ")
    assert recognizer.source == 0


def test_invalid_text_source_falls_back_to_default_camera_index():
    recognizer = FaceRecognizer(source=" ye run kyu nhi ho rha hee ")
    assert recognizer.source == 0


def test_rtsp_source_is_preserved():
    recognizer = FaceRecognizer(source="rtsp://example.com/live")
    assert recognizer.source == "rtsp://example.com/live"


def test_http_ip_webcam_source_appends_video():
    recognizer = FaceRecognizer(source="http://192.168.1.3:8080")
    assert recognizer.source == "http://192.168.1.3:8080/video"


def test_http_ip_webcam_source_with_slash_appends_video():
    recognizer = FaceRecognizer(source="http://192.168.1.3:8080/")
    assert recognizer.source == "http://192.168.1.3:8080/video"


def test_http_ip_webcam_source_already_has_video():
    recognizer = FaceRecognizer(source="http://192.168.1.3:8080/video")
    assert recognizer.source == "http://192.168.1.3:8080/video"

