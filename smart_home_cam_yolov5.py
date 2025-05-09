import cv2
import numpy as np
import time
import os
import threading
import queue
import socket
import struct
import pickle
import pyttsx3
import json
from datetime import datetime
from flask import Flask, render_template, Response, request, redirect, url_for
from flask_socketio import SocketIO, emit
from functools import wraps
import base64
import io
from PIL import Image
import signal
import sys
import os
import subprocess
import gc
import torch
from ultralytics import YOLO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key_for_smart_home_cam'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 전역 변수로 프로그램 실행 상태 관리
running = True

# 기본 인증 정보 (기본값)
USERNAME = 'admin'
PASSWORD = 'smarthome'

# 설정 파일에서 인증 정보 로드
def load_auth_config():
    global USERNAME, PASSWORD
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            auth_settings = config.get('auth_settings', {})
            USERNAME = auth_settings.get('username', USERNAME)
            PASSWORD = auth_settings.get('password', PASSWORD)
    except FileNotFoundError:
        print("설정 파일을 찾을 수 없어 기본 인증 정보를 사용합니다.")
    except json.JSONDecodeError:
        print("설정 파일 형식이 잘못되었습니다. 기본 인증 정보를 사용합니다.")

# 기본 인증 데코레이터
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != USERNAME or auth.password != PASSWORD:
            return Response(
                'Could not verify your access level for that URL.\n'
                'You have to login with proper credentials', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated

def signal_handler(sig, frame):
    """시그널 핸들러 - Ctrl+C 감지 시 호출됨"""
    print("\nCtrl+C가 감지되었습니다. 프로그램 종료 중...")
    
    # 모든 정리 작업 수행 후 즉시 종료
    cleanup_and_exit()

def cleanup_and_exit():
    """리소스를 정리하고 프로그램을 강제 종료합니다."""
    print("\n프로그램 종료 중...")
    
    try:
        # 홈캠 인스턴스 정지
        if 'home_cam' in globals() and home_cam is not None:
            home_cam.stop()
            
        # 열린 창 닫기
        cv2.destroyAllWindows()
    except Exception as e:
        print(f"정리 중 오류: {e}")
    
    # 완전히 프로세스 종료 (더 이상의 코드는 실행되지 않음)
    print("프로그램을 종료합니다.")
    os._exit(0)  # 즉시 종료

class SmartHomeCam:
    def __init__(self, camera_id=0, model_type='nano'):
        # 카메라 설정
        self.camera_id = camera_id  # 인스턴스 생성 시 카메라 ID 설정
        self.cap = None
        self.running = True
        self.camera_initialized = False
        
        # YOLO 모델 설정
        self.model_type = model_type  # 'nano', 'small', 'medium', 'large'
        self.model = None
        self.classes = []
        self.colors = np.random.uniform(0, 255, size=(80, 3))
        self.detection_threshold = 0.7
        
        # TTS 설정
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)
        self.tts_engine.setProperty('volume', 1.0)
        self.tts_thread = None
        self.tts_lock = threading.Lock()
        
        # 객체 감지 결과 큐
        self.detection_queue = queue.Queue()
        
        # 마지막 알림 시간
        self.last_notification_time = {}
        
        # 웹 스트리밍을 위한 변수
        self.frame = None
        self.detections = []
        
        # 설정 파일 로드
        self.load_config()
        
    def load_config(self):
        """설정 파일을 로드합니다."""
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.notification_cooldown = config.get('notification_cooldown', 30)
                self.special_objects = config.get('special_objects', ['person', 'dog', 'cat'])
        except FileNotFoundError:
            self.notification_cooldown = 30
            self.special_objects = ['person', 'dog', 'cat']
            
    def initialize_camera(self):
        """카메라를 초기화합니다."""
        try:
            # 기존 카메라가 열려있으면 해제
            if self.cap is not None:
                self.cap.release()
                time.sleep(1)  # 카메라 해제 후 잠시 대기
                
            print(f"카메라 {self.camera_id} 초기화 시도 중...")
            
            # 카메라 초기화 시도 (DirectShow 백엔드 사용)
            self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
            
            if not self.cap.isOpened():
                print(f"카메라 {self.camera_id}를 열 수 없습니다. 다른 카메라를 시도합니다...")
                # 다른 카메라 ID 시도
                for i in range(3):  # 0, 1, 2 시도
                    if i != self.camera_id:
                        print(f"카메라 {i} 시도 중...")
                        self.cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                        if self.cap.isOpened():
                            self.camera_id = i
                            print(f"카메라 {i}로 자동 전환되었습니다.")
                            break
                            
            if not self.cap.isOpened():
                raise Exception("사용 가능한 카메라를 찾을 수 없습니다.")
            
            # 카메라 설정
            print("카메라 설정 중...")
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 버퍼 크기 최소화
            
            # 카메라가 제대로 초기화되었는지 확인
            print("프레임 읽기 테스트 중...")
            for _ in range(5):  # 여러 번 시도
                ret, frame = self.cap.read()
                if ret and frame is not None and frame.size > 0:
                    print("카메라 초기화 성공!")
                    self.camera_initialized = True
                    return True
                time.sleep(0.1)
            
            raise Exception("카메라에서 유효한 프레임을 읽을 수 없습니다.")
                
        except Exception as e:
            print(f"카메라 초기화 오류: {e}")
            if self.cap is not None:
                self.cap.release()
            return False
            
    def load_yolo_model(self):
        """YOLOv5 모델을 로드합니다."""
        try:
            # 모델 종류에 따라 다른 파일 선택
            if self.model_type == 'nano':
                model_path = "object_detection_yolov5/yolov5n.pt"
            elif self.model_type == 'small':
                model_path = "object_detection_yolov5/yolov5s.pt"
            elif self.model_type == 'medium':
                model_path = "object_detection_yolov5/yolov5m.pt"
            elif self.model_type == 'large':
                model_path = "object_detection_yolov5/yolov5l.pt"
            else:
                model_path = "object_detection_yolov5/yolov5n.pt"  # 기본값
                
            # 모델이 없으면 다운로드 안내
            if not os.path.exists(model_path):
                os.makedirs("object_detection_yolov5", exist_ok=True)
                print(f"경고: {model_path} 모델 파일이 없습니다.")
                print("다음 링크에서 모델을 다운로드하세요:")
                print("YOLOv5n: https://github.com/ultralytics/yolov5/releases/download/v6.1/yolov5n.pt")
                print("YOLOv5s: https://github.com/ultralytics/yolov5/releases/download/v6.1/yolov5s.pt")
                print("YOLOv5m: https://github.com/ultralytics/yolov5/releases/download/v6.1/yolov5m.pt")
                print("YOLOv5l: https://github.com/ultralytics/yolov5/releases/download/v6.1/yolov5l.pt")
                print(f"다운로드한 파일을 {model_path}에 저장하세요.")
                return False
                
            print(f"YOLOv5 모델 로드 중: {model_path}")
            self.model = YOLO(model_path)
            self.classes = self.model.names
            print(f"YOLO 모델 로드 완료. {len(self.classes)}개의 클래스 감지 가능")
            return True
            
        except Exception as e:
            print(f"YOLOv5 모델 로드 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def detect_objects(self, frame):
        """YOLOv5를 사용하여 프레임에서 객체를 감지합니다."""
        try:
            if frame is None or frame.size == 0:
                print("빈 프레임입니다. 객체 감지를 건너뜁니다.")
                return []
                
            if self.model is None:
                print("YOLOv5 모델이 로드되지 않았습니다.")
                return []
            
            # YOLOv5로 객체 감지 수행
            results = self.model(frame, conf=self.detection_threshold)
            
            # 결과 파싱
            detections = []
            
            # 최신 ultralytics 버전에 맞게 결과 처리 방식 변경
            for result in results:
                # 각 결과의 박스, 클래스, 신뢰도 값 가져오기
                boxes = result.boxes
                
                for box in boxes:
                    # 박스 좌표 가져오기 (x1, y1, x2, y2)
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    
                    # 정수형으로 변환
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    
                    # 클래스 인덱스와 이름
                    class_id = int(box.cls)
                    label = self.model.names[class_id]
                    confidence = float(box.conf)
                    
                    # 시각화를 위한 좌표 계산 (x, y, w, h 형식으로 변환)
                    x = x1
                    y = y1
                    w = x2 - x1
                    h = y2 - y1
                    
                    # 감지 결과 저장
                    detections.append((label, confidence, (x, y, w, h)))
                
            return detections
            
        except Exception as e:
            print(f"객체 감지 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return []

    def process_notifications(self, detections):
        """감지된 객체에 대한 알림을 처리합니다."""
        if not detections:
            return
            
        current_time = time.time()
        
        for label, confidence, _ in detections:
            if label in self.special_objects:
                if label not in self.last_notification_time or \
                   (current_time - self.last_notification_time[label]) > self.notification_cooldown:
                    
                    message = f"{label}가 감지되었습니다."
                    
                    # TTS를 별도 스레드에서 실행하여 카메라가 멈추지 않도록 함
                    if self.tts_thread is None or not self.tts_thread.is_alive():
                        self.tts_thread = threading.Thread(target=self._speak_message, args=(message,))
                        self.tts_thread.daemon = True
                        self.tts_thread.start()
                    
                    self.last_notification_time[label] = current_time
                    
    def _speak_message(self, message):
        """TTS 엔진을 사용하여 메시지를 말합니다. (별도 스레드에서 실행)"""
        if not self.tts_engine:
            print(f"음성 알림 (TTS 엔진 사용 불가): {message}")
            return
            
        try:
            with self.tts_lock:
                # 혹시 모를 오류를 대비해 실행 시간 제한
                start_time = time.time()
                self.tts_engine.say(message)
                self.tts_engine.runAndWait()
                
                # TTS 실행이 너무 오래 걸리면 로그 출력
                duration = time.time() - start_time
                if duration > 3:
                    print(f"경고: TTS 실행이 {duration:.1f}초로 너무 오래 걸렸습니다.")
        except Exception as e:
            print(f"음성 출력 중 오류 발생: {e}")
            
            # TTS 엔진이 멈춘 경우 재초기화 시도
            try:
                print("TTS 엔진 재초기화 시도...")
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 150)
                self.tts_engine.setProperty('volume', 1.0)
            except Exception as init_error:
                print(f"TTS 엔진 재초기화 실패: {init_error}")
                self.tts_engine = None
    
    def stop(self):
        """카메라와 프로그램을 정상적으로 종료합니다."""
        print("카메라 종료 중...")
        self.running = False
        
        # 카메라 자원 해제
        if self.cap is not None:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None
            
        # 메모리 자원 정리
        self.frame = None
        self.detections = []
        
        print("카메라 종료 완료")
        
    def process_frame(self):
        """프레임을 처리하고 웹으로 전송합니다."""
        retry_count = 0
        max_retries = 3
        frame_count = 0
        last_successful_frame_time = time.time()
        last_detection_time = time.time()
        detection_interval = 0.08  # 객체 감지 간격 (초)
        
        # 메모리 관리를 위한 변수
        gc_interval = 500  # 500프레임마다 가비지 컬렉션 수행
        gc_counter = 0
        
        print("프레임 처리 스레드 시작됨...")
        
        while self.running:
            try:
                # 카메라가 없거나 열려있지 않으면 재초기화
                if not self.cap or not self.cap.isOpened():
                    print("카메라가 열려있지 않습니다. 재초기화 중...")
                    if not self.initialize_camera():
                        print("카메라 초기화 실패, 2초 후 재시도")
                        time.sleep(2)
                        continue
                    retry_count = 0
                    time.sleep(0.5)
                    continue
                
                # 프레임 읽기
                ret, frame = self.cap.read()
                
                # 유효하지 않은 프레임인 경우
                if not ret or frame is None or frame.size == 0 or np.all(frame == 0):
                    retry_count += 1
                    print(f"유효하지 않은 프레임: 재시도 {retry_count}/{max_retries}")
                    
                    # 너무 오랜 시간 동안 유효한 프레임이 없으면 카메라 재초기화
                    current_time = time.time()
                    if current_time - last_successful_frame_time > 5:  # 5초 이상 프레임이 없으면
                        print("장시간 유효한 프레임이 없습니다. 카메라 재초기화 중...")
                        if self.cap is not None:
                            self.cap.release()
                            self.cap = None
                            self.camera_initialized = False
                        
                        # 재초기화 시도
                        if not self.initialize_camera():
                            print("카메라 재초기화 실패")
                            time.sleep(2)
                            continue
                            
                        retry_count = 0
                        last_successful_frame_time = current_time
                    
                    # 최대 재시도 횟수 초과 시 잠시 대기
                    if retry_count >= max_retries:
                        print("최대 재시도 횟수 초과. 잠시 대기 후 계속...")
                        time.sleep(1)
                        retry_count = 0
                    
                    time.sleep(0.1)
                    continue
                
                # 성공적으로 프레임을 읽은 경우
                retry_count = 0
                last_successful_frame_time = time.time()
                frame_count += 1
                gc_counter += 1
                
                # 객체 감지는 일정 간격으로만 수행
                current_time = time.time()
                perform_detection = current_time - last_detection_time >= detection_interval

                # 작업용 프레임 복사
                display_frame = frame.copy()

                if perform_detection:
                    try:
                        # 객체 감지 수행
                        detections = self.detect_objects(frame)
                        last_detection_time = current_time
                        
                        # 프레임에 박스 그리기
                        for label, confidence, (x, y, w, h) in detections:
                            try:
                                # 색상 인덱스 확인 및 안전하게 색상 얻기
                                class_idx = list(self.model.names.values()).index(label) if label in self.model.names.values() else 0
                                color = self.colors[class_idx % len(self.colors)].tolist()
                                
                                # 사각형 및 텍스트 그리기
                                cv2.rectangle(display_frame, (x, y), (x + w, y + h), color, 2)
                                text = f"{label}: {confidence:.2f}"
                                cv2.putText(display_frame, text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                            except Exception as e:
                                print(f"프레임에 박스 그리기 중 오류: {e}")

                        # 알림 처리
                        if detections:
                            self.process_notifications(detections)
                        
                        # 결과 저장
                        self.detections = detections
                    except Exception as e:
                        print(f"객체 감지 중 오류 발생: {e}")
                
                # 프레임 저장 (화면 표시용 프레임 사용)
                self.frame = display_frame
                
                try:
                    # 웹소켓을 통해 프레임 전송
                    # 프레임 크기 줄이기 (해상도 감소)
                    small_frame = cv2.resize(display_frame, (480, 360))
                    # 품질 감소 (압축률 증가)
                    _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                    frame_base64 = base64.b64encode(buffer).decode('utf-8')
                    
                    # 감지된 객체 정보 전송
                    detection_info = [{"label": label, "confidence": float(confidence)} 
                                    for label, confidence, _ in self.detections]
                    
                    # 'broadcast' 파라미터 없이 emit 호출
                    socketio.emit('frame', {
                        'image': frame_base64,
                        'detections': detection_info
                    })
                    
                    # 메모리 관리: 참조 해제
                    del buffer
                    del frame_base64
                    del small_frame
                    
                except Exception as e:
                    print(f"프레임 전송 중 오류 발생: {e}")
                
                # 메모리 관리 (주기적 GC)
                if gc_counter >= gc_interval:
                    gc_counter = 0
                    gc.collect()  # 가비지 컬렉션 강제 실행
                
                # 약 30fps로 제한 (너무 많은 프레임은 전송 부하 유발)
                time.sleep(0.033)
                
            except Exception as e:
                print(f"프레임 처리 중 오류 발생: {e}")
                # 'broadcast' 파라미터 없이 emit 호출
                socketio.emit('camera_error', str(e))
                time.sleep(1)
                
                retry_count += 1
                if retry_count >= max_retries:
                    print("치명적인 오류 발생. 카메라 재초기화 중...")
                    if self.cap is not None:
                        self.cap.release()
                        self.cap = None
                        self.camera_initialized = False
                    try:
                        self.initialize_camera()
                        retry_count = 0
                    except Exception as init_error:
                        print(f"카메라 재초기화 실패: {init_error}")
                        time.sleep(5)  # 잠시 대기 후 다시 시도

    def start(self):
        """카메라 시스템을 시작합니다."""
        try:
            # 기존 카메라가 있으면 완전히 해제
            if self.cap is not None:
                self.cap.release()
                self.cap = None
                time.sleep(1)  # 리소스 해제를 위한 대기
                
            self.running = True
            
            # 카메라 초기화
            if not self.initialize_camera():
                print("카메라 초기화 실패!")
                return False
                
            # YOLOv5 모델 로드
            if not self.load_yolo_model():
                print("모델 로드 실패!")
                return False
            
            # 프레임 처리 스레드 시작
            print("프레임 처리 스레드 시작...")
            frame_thread = threading.Thread(target=self.process_frame)
            frame_thread.daemon = True
            frame_thread.start()
            
            print("카메라 시스템 시작 완료")
            return True
            
        except Exception as e:
            print(f"카메라 시스템 시작 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return False

@app.route('/')
@requires_auth
def index():
    """웹 인터페이스 메인 페이지를 제공합니다."""
    return render_template('index.html')

@app.route('/restart', methods=['POST'])
@requires_auth
def restart():
    """카메라를 다시 시작하고 메인 페이지로 이동합니다."""
    try:
        # 먼저 카메라 정지
        home_cam.stop()
        time.sleep(1)  # 1초 대기
        
        # 카메라 다시 시작
        success = home_cam.start()
        
        # 초기 연결 실패 시 추가 시도
        if not success:
            print("초기 카메라 연결 실패, 3초 후 재시도...")
            time.sleep(3)  # 3초 대기
            success = home_cam.start()
            
            # 두 번째 시도도 실패하면 5초 더 대기 후 마지막 시도
            if not success:
                print("두 번째 카메라 연결 실패, 5초 후 마지막 시도...")
                time.sleep(5)
                success = home_cam.start()
        
        if success:
            return '카메라가 다시 시작되었습니다.'
        else:
            return '카메라 재시작 실패', 500
    except Exception as e:
        return f"카메라 재시작 중 오류: {str(e)}", 500

@app.route('/shutdown', methods=['POST'])
@requires_auth
def shutdown():
    """카메라를 정지하고 goodbye 페이지로 이동합니다."""
    try:
        # 카메라만 정지
        home_cam.stop()
        return '카메라가 정지되었습니다.'
    except Exception as e:
        return f"카메라 정지 중 오류: {str(e)}", 500

@app.route('/goodbye')
@requires_auth
def goodbye():
    """종료 페이지를 표시합니다."""
    return render_template('goodbye.html')

# 웹소켓 이벤트
@socketio.on('connect')
def handle_connect():
    print('클라이언트가 연결되었습니다')

@socketio.on('disconnect')
def handle_disconnect():
    print('클라이언트가 연결을 끊었습니다')

if __name__ == "__main__":
    # SIGINT (Ctrl+C) 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # 인증 정보 로드
        load_auth_config()
        
        # 관련 폴더 생성
        os.makedirs("object_detection_yolov5", exist_ok=True)
        os.makedirs("templates", exist_ok=True)
        
        # index.html 파일이 없을 경우에만 생성
        if not os.path.exists("templates/index.html"):
            print("templates/index.html 파일이 없어 새로 생성합니다.")
            with open("templates/index.html", "w", encoding="utf-8") as f:
                f.write("""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YOLOv5 스마트홈 카메라</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f2f5;
            color: #333;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
        }
        .camera-feed {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-bottom: 20px;
        }
        #video-feed {
            width: 100%;
            max-width: 640px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .controls {
            margin-top: 20px;
            display: flex;
            justify-content: center;
            gap: 10px;
        }
        button {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #45a049;
        }
        button.danger {
            background-color: #f44336;
        }
        button.danger:hover {
            background-color: #d32f2f;
        }
        .detections {
            margin-top: 20px;
            border-top: 1px solid #eee;
            padding-top: 20px;
        }
        .detection-item {
            background-color: #f9f9f9;
            border-radius: 4px;
            padding: 10px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
        }
        .confidence {
            color: #666;
            font-weight: bold;
        }
        .status {
            margin-top: 10px;
            padding: 10px;
            background-color: #e8f5e9;
            border-radius: 4px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>YOLOv5 스마트홈 카메라</h1>
        
        <div class="camera-feed">
            <img id="video-feed" src="" alt="카메라 스트림">
            <div class="status" id="status">연결 중...</div>
        </div>
        
        <div class="controls">
            <button id="restart-btn">카메라 재시작</button>
            <button id="shutdown-btn" class="danger">프로그램 종료</button>
        </div>
        
        <div class="detections">
            <h2>감지된 객체</h2>
            <div id="detection-list">감지 중...</div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // 소켓 연결 설정
            const socket = io({
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionAttempts: 10
            });
            
            const videoFeed = document.getElementById('video-feed');
            const detectionList = document.getElementById('detection-list');
            const status = document.getElementById('status');
            const restartBtn = document.getElementById('restart-btn');
            const shutdownBtn = document.getElementById('shutdown-btn');
            
            // 페이지 로드 시 연결 중 표시
            status.textContent = '연결 중...';
            status.style.backgroundColor = '#fff9c4';
            
            // 소켓 연결
            socket.on('connect', () => {
                console.log('서버에 연결됨');
                status.textContent = '연결됨';
                status.style.backgroundColor = '#e8f5e9';
            });
            
            // 소켓 연결 끊김
            socket.on('disconnect', () => {
                console.log('서버와 연결 끊김');
                status.textContent = '연결 끊김 - 재연결 중...';
                status.style.backgroundColor = '#ffebee';
            });
            
            // 에러 처리
            socket.on('error', (error) => {
                console.error('Socket 오류:', error);
                status.textContent = '연결 오류: ' + error;
                status.style.backgroundColor = '#ffebee';
            });
            
            // 재연결 시도
            socket.on('reconnecting', (attemptNumber) => {
                console.log(`재연결 시도 ${attemptNumber}회`);
                status.textContent = `재연결 시도 중 (${attemptNumber}회)`;
                status.style.backgroundColor = '#fff9c4';
            });
            
            // 재연결 성공
            socket.on('reconnect', () => {
                console.log('재연결 성공');
                status.textContent = '재연결 성공';
                status.style.backgroundColor = '#e8f5e9';
            });
            
            // 카메라 프레임 수신
            socket.on('frame', (data) => {
                try {
                    // 이미지 로딩 확인
                    if (data.image) {
                        videoFeed.src = 'data:image/jpeg;base64,' + data.image;
                        
                        // 이미지 로딩 오류 시 처리
                        videoFeed.onerror = function() {
                            console.error('이미지 로딩 오류');
                            videoFeed.src = ''; // 이미지 초기화
                        };
                    }
                    
                    // 감지 정보 업데이트
                    if (data.detections && Array.isArray(data.detections)) {
                        if (data.detections.length > 0) {
                            let html = '';
                            data.detections.forEach(detection => {
                                if (detection && detection.label) {
                                    html += `
                                        <div class="detection-item">
                                            <span>${detection.label}</span>
                                            <span class="confidence">${(detection.confidence * 100).toFixed(1)}%</span>
                                        </div>
                                    `;
                                }
                            });
                            detectionList.innerHTML = html || '감지된 객체가 없습니다.';
                        } else {
                            detectionList.innerHTML = '감지된 객체가 없습니다.';
                        }
                    }
                } catch (e) {
                    console.error('프레임 처리 중 오류:', e);
                }
            });
            
            // 카메라 오류
            socket.on('camera_error', (errorMsg) => {
                console.error('카메라 오류:', errorMsg);
                status.textContent = '오류: ' + errorMsg;
                status.style.backgroundColor = '#ffebee';
            });
            
            // 재시작 버튼
            restartBtn.addEventListener('click', () => {
                status.textContent = '카메라 재시작 중...';
                status.style.backgroundColor = '#fff9c4';
                
                fetch('/restart', { method: 'POST' })
                    .then(response => response.text())
                    .then(data => {
                        status.textContent = data;
                        status.style.backgroundColor = '#e8f5e9';
                    })
                    .catch(error => {
                        console.error('재시작 오류:', error);
                        status.textContent = '재시작 요청 오류: ' + error;
                        status.style.backgroundColor = '#ffebee';
                    });
            });
            
            // 종료 버튼
            shutdownBtn.addEventListener('click', () => {
                if (confirm('정말 프로그램을 종료하시겠습니까?')) {
                    status.textContent = '프로그램 종료 중...';
                    status.style.backgroundColor = '#ffebee';
                    
                    fetch('/shutdown', { method: 'POST' })
                        .then(response => {
                            if (response.ok) {
                                window.location.href = '/goodbye';
                            }
                        })
                        .catch(error => {
                            console.error('종료 오류:', error);
                            status.textContent = '종료 요청 오류: ' + error;
                        });
                }
            });
        });
    </script>
</body>
</html>""")
        
        # 스마트 홈캠 인스턴스 생성 및 시작
        print("YOLOv5 스마트홈 카메라 시스템 시작 중...")
        home_cam = SmartHomeCam(camera_id=1, model_type='nano')
        if not home_cam.start():
            print("카메라 시스템 시작 실패. 프로그램 종료.")
            sys.exit(1)
        
        print("=" * 50)
        print("YOLOv5 스마트홈 카메라 시스템이 시작되었습니다")
        print("웹 인터페이스: http://localhost:5000")
        print("종료하려면 Ctrl+C를 누르세요")
        print("=" * 50)
        
        # Flask 앱 직접 실행
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
        
    except KeyboardInterrupt:
        # Ctrl+C가 감지되면 이 부분이 실행됨
        cleanup_and_exit()
    except Exception as e:
        print(f"프로그램 실행 중 오류 발생: {e}")
        cleanup_and_exit() 