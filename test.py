import cv2

for i in range(5):
    cap = cv2.VideoCapture(i)
    ok, frame = cap.read()
    print(f"Camera {i}: Opened={cap.isOpened()} Frame={ok}")
    cap.release()