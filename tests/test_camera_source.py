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
