import cv2
import numpy as np
import threading
import time

class Camera:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None
        self.frame = None
        self.lock = threading.Lock()
        self.running = False
        self.current_angle_x = 90  # 초기 각도: 가운데
        self.current_angle_y = 90  # 초기 각도: 가운데
        
        # 서보 모터 제어를 위한 설정
        # 실제 하드웨어 연결 시 GPIO 제어 코드 추가 필요
        self.servo_x = None
        self.servo_y = None
        
        # 스트리밍 시작
        self.start_streaming()

    def start_streaming(self):
        """카메라 스트리밍 시작"""
        if self.running:
            return
        
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            raise ValueError("카메라를 열 수 없습니다. 카메라가 연결되어 있는지 확인하세요.")
        
        # 해상도 설정
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.running = True
        self.thread = threading.Thread(target=self._update_frame, daemon=True)
        self.thread.start()
        
        # 초기 카메라 위치 설정
        self._set_camera_position(self.current_angle_x, self.current_angle_y)

    def _update_frame(self):
        """프레임 업데이트 스레드"""
        while self.running:
            success, frame = self.cap.read()
            if success:
                with self.lock:
                    self.frame = frame
            time.sleep(0.03)  # ~30 FPS

    def stop_streaming(self):
        """카메라 스트리밍 중지"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()

    def get_frame(self):
        """현재 프레임 반환"""
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def move(self, direction):
        """카메라 방향 이동
        direction: 'up', 'down', 'left', 'right'
        """
        angle_change = 10  # 각도 변화량
        
        if direction == 'up' and self.current_angle_y > 0:
            self.current_angle_y = max(0, self.current_angle_y - angle_change)
        elif direction == 'down' and self.current_angle_y < 180:
            self.current_angle_y = min(180, self.current_angle_y + angle_change)
        elif direction == 'left' and self.current_angle_x < 180:
            self.current_angle_x = min(180, self.current_angle_x + angle_change)
        elif direction == 'right' and self.current_angle_x > 0:
            self.current_angle_x = max(0, self.current_angle_x - angle_change)
        
        self._set_camera_position(self.current_angle_x, self.current_angle_y)
        return True

    def _set_camera_position(self, angle_x, angle_y):
        """카메라 위치 설정
        실제 하드웨어 연결 시 서보 모터 제어 코드 구현 필요
        """
        print(f"카메라 위치 설정: X={angle_x}, Y={angle_y}")
        # 예시: 라즈베리파이 GPIO 제어 코드
        # if self.servo_x:
        #     self.servo_x.angle = angle_x
        # if self.servo_y:
        #     self.servo_y.angle = angle_y

    def __del__(self):
        self.stop_streaming() 