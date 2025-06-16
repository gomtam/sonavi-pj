import cv2
import numpy as np
import time
import os
import threading
import queue
import socket
import struct
import pickle
import json
import requests
from datetime import datetime
from flask import Flask, render_template, Response, request, redirect, url_for, jsonify
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
from twilio.rest import Client
from firebase_fcm import FirebaseFCM
import piexif
import re

# 스냅샷과 녹화를 위한 디렉토리 설정
SNAPSHOTS_DIR = "snapshots"
RECORDINGS_DIR = "recordings"

# 디렉토리가 없으면 생성
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
os.makedirs(RECORDINGS_DIR, exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'smart_home_secret_key_2024!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 전역 변수로 프로그램 실행 상태 관리
running = True

# DuckDNS 인스턴스
duckdns_updater = None

# Twilio SMS 인스턴스
twilio_sms = None

# Firebase FCM 인스턴스
firebase_fcm = None

# Cloudflare Tunnel 인스턴스
cloudflare_tunnel = None

# 기본 인증 정보 (기본값)
USERNAME = 'admin'
PASSWORD = 'smarthome'

class DuckDNSUpdater:
    """DuckDNS 자동 업데이트 클래스"""
    
    def __init__(self):
        self.enabled = False
        self.domain = ""
        self.token = ""
        self.update_interval = 300  # 5분
        self.current_ip = ""
        self.update_thread = None
        self.running = False
        self.load_config()
        
    def load_config(self):
        """config.json에서 DuckDNS 설정을 로드합니다."""
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                duckdns_settings = config.get('duckdns_settings', {})
                self.enabled = duckdns_settings.get('enabled', False)
                self.domain = duckdns_settings.get('domain', '')
                self.token = duckdns_settings.get('token', '')
                self.update_interval = duckdns_settings.get('update_interval', 300)
                
                if self.enabled and (not self.domain or not self.token):
                    print("경고: DuckDNS가 활성화되어 있지만 도메인 또는 토큰이 설정되지 않았습니다.")
                    self.enabled = False
                    
        except FileNotFoundError:
            print("설정 파일을 찾을 수 없습니다. DuckDNS 기능이 비활성화됩니다.")
        except json.JSONDecodeError:
            print("설정 파일 형식이 잘못되었습니다. DuckDNS 기능이 비활성화됩니다.")
            
    def get_public_ip(self):
        """현재 공인 IP 주소를 가져옵니다."""
        try:
            # 여러 서비스를 시도하여 안정성 확보
            services = [
                'https://ipv4.icanhazip.com',
                'https://api.ipify.org',
                'https://checkip.amazonaws.com'
            ]
            
            for service in services:
                try:
                    response = requests.get(service, timeout=10)
                    if response.status_code == 200:
                        ip = response.text.strip()
                        # IP 주소 형식 검증
                        parts = ip.split('.')
                        if len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts):
                            return ip
                except Exception:
                    continue
                    
            return None
            
        except Exception as e:
            print(f"공인 IP 주소 확인 중 오류: {e}")
            return None
            
    def update_duckdns(self, ip=None):
        """DuckDNS에 IP 주소를 업데이트합니다."""
        try:
            if not self.enabled:
                return False, "DuckDNS가 비활성화되어 있습니다."
                
            if ip is None:
                ip = self.get_public_ip()
                
            if not ip:
                return False, "공인 IP 주소를 가져올 수 없습니다."
                
            # DuckDNS API 호출
            url = f"https://www.duckdns.org/update?domains={self.domain}&token={self.token}&ip={ip}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                if response.text.strip() == 'OK':
                    self.current_ip = ip
                    print(f"DuckDNS 업데이트 성공: {self.domain}.duckdns.org -> {ip}")
                    return True, f"성공: {ip}"
                else:
                    return False, f"DuckDNS 응답 오류: {response.text}"
            else:
                return False, f"HTTP 오류: {response.status_code}"
                
        except Exception as e:
            print(f"DuckDNS 업데이트 중 오류: {e}")
            return False, str(e)
            
    def start_auto_update(self):
        """자동 업데이트를 시작합니다."""
        if not self.enabled:
            print("DuckDNS가 비활성화되어 있습니다.")
            return
            
        print(f"DuckDNS 자동 업데이트 시작: {self.domain}.duckdns.org ({self.update_interval}초 간격)")
        
        # 즉시 한 번 업데이트
        success, result = self.update_duckdns()
        if success:
            print(f"초기 DuckDNS 업데이트 완료: {result}")
        else:
            print(f"초기 DuckDNS 업데이트 실패: {result}")
        
        self.running = True
        self.update_thread = threading.Thread(target=self._update_worker)
        self.update_thread.daemon = True
        self.update_thread.start()
        
    def _update_worker(self):
        """백그라운드에서 주기적으로 IP를 업데이트합니다."""
        while self.running:
            try:
                time.sleep(self.update_interval)
                
                if not self.running:
                    break
                    
                new_ip = self.get_public_ip()
                if new_ip and new_ip != self.current_ip:
                    success, result = self.update_duckdns(new_ip)
                    if success:
                        print(f"IP 변경 감지 및 업데이트: {self.current_ip} -> {new_ip}")
                    else:
                        print(f"IP 업데이트 실패: {result}")
                        
            except Exception as e:
                print(f"DuckDNS 자동 업데이트 오류: {e}")
                
    def stop(self):
        """자동 업데이트를 중지합니다."""
        self.running = False
        if self.update_thread and self.update_thread.is_alive():
            print("DuckDNS 자동 업데이트 중지 중...")
            self.update_thread.join(timeout=5)
            print("DuckDNS 자동 업데이트 중지 완료")

class TwilioSMS:
    """Twilio SMS 발송 클래스"""
    
    def __init__(self):
        self.enabled = False
        self.account_sid = ""
        self.auth_token = ""
        self.from_number = ""
        self.to_number = ""
        self.send_on_detection = True
        self.detection_cooldown = 300  # 5분
        self.client = None
        self.last_sms_time = {}
        self.load_config()
        
    def load_config(self):
        """config.json에서 Twilio 설정을 로드합니다."""
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                twilio_settings = config.get('twilio_settings', {})
                self.enabled = twilio_settings.get('enabled', False)
                self.account_sid = twilio_settings.get('account_sid', '')
                self.auth_token = twilio_settings.get('auth_token', '')
                self.from_number = twilio_settings.get('from_number', '')
                self.to_number = twilio_settings.get('to_number', '')
                self.send_on_detection = twilio_settings.get('send_on_detection', True)
                self.detection_cooldown = twilio_settings.get('detection_cooldown', 300)
                
                if self.enabled:
                    if not all([self.account_sid, self.auth_token, self.from_number, self.to_number]):
                        print("경고: Twilio가 활성화되어 있지만 필수 정보가 누락되었습니다.")
                        self.enabled = False
                    else:
                        try:
                            self.client = Client(self.account_sid, self.auth_token)
                            print(f"Twilio SMS 클라이언트 초기화 완료: {self.from_number} → {self.to_number}")
                        except Exception as e:
                            print(f"Twilio 클라이언트 초기화 실패: {e}")
                            self.enabled = False
                            
        except FileNotFoundError:
            print("설정 파일을 찾을 수 없습니다. Twilio SMS 기능이 비활성화됩니다.")
        except json.JSONDecodeError:
            print("설정 파일 형식이 잘못되었습니다. Twilio SMS 기능이 비활성화됩니다.")
            
    def send_sms(self, message):
        """SMS를 발송합니다."""
        if not self.enabled:
            return False, "Twilio SMS가 비활성화되어 있습니다."
            
        if not self.client:
            return False, "Twilio 클라이언트가 초기화되지 않았습니다."
            
        try:
            message_obj = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=self.to_number
            )
            
            print(f"SMS 발송 성공: {message_obj.sid}")
            return True, message_obj.sid
            
        except Exception as e:
            print(f"SMS 발송 실패: {e}")
            return False, str(e)
            
    def send_detection_alert(self, detected_object, confidence):
        """객체 감지 시 알림 SMS를 발송합니다."""
        if not self.enabled or not self.send_on_detection:
            return False, "감지 알림이 비활성화되어 있습니다."
            
        current_time = time.time()
        
        # 쿨다운 체크
        if detected_object in self.last_sms_time:
            time_diff = current_time - self.last_sms_time[detected_object]
            if time_diff < self.detection_cooldown:
                remaining_time = int(self.detection_cooldown - time_diff)
                return False, f"쿨다운 중입니다. {remaining_time}초 후 재시도 가능합니다."
                
        # SMS 메시지 작성
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"🏠 스마트홈 카메라 알림\n\n감지된 객체: {detected_object}\n신뢰도: {confidence:.1%}\n시간: {current_time_str}\n\n확인: http://sonavi.duckdns.org:5000"
        
        # SMS 발송
        success, result = self.send_sms(message)
        
        if success:
            self.last_sms_time[detected_object] = current_time
            print(f"감지 알림 SMS 발송 완료: {detected_object} ({confidence:.1%})")
            return True, result
        else:
            return False, result
            
    def send_test_sms(self):
        """테스트 SMS를 발송합니다."""
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"🧪 스마트홈 카메라 테스트\n\n시간: {current_time_str}\n상태: 정상 작동 중\n\nTwilio SMS 연결 테스트 완료!"
        
        return self.send_sms(message)

class CloudflareTunnel:
    def __init__(self):
        self.process = None
        self.tunnel_url = None
        self.enabled = True
        self.executable_path = "cloudflared.exe"
        
    def check_cloudflared(self):
        """cloudflared 실행 파일이 있는지 확인"""
        try:
            result = subprocess.run([self.executable_path, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
            
    def start_tunnel(self, local_port=5000):
        """Cloudflare Tunnel 시작 및 URL 추출"""
        if not self.check_cloudflared():
            print()
            print("❌ cloudflared.exe를 찾을 수 없습니다.")
            print("   📥 다운로드: https://github.com/cloudflare/cloudflared/releases")
            print("   📁 위치: 프로그램과 같은 폴더에 cloudflared.exe 파일을 저장하세요")
            print("   ⚠️ Cloudflare Tunnel 기능이 비활성화됩니다.")
            print()
            self.enabled = False
            return None
            
        try:
            print("🌐 Cloudflare Tunnel 시작 중...")
            
            # cloudflared 실행
            cmd = [self.executable_path, 'tunnel', '--url', f'http://localhost:{local_port}']
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # URL 추출을 위한 별도 스레드
            url_thread = threading.Thread(target=self._extract_url, daemon=True)
            url_thread.start()
            
            # URL 추출을 위해 최대 30초 대기
            for _ in range(30):
                if self.tunnel_url:
                    return self.tunnel_url
                time.sleep(1)
            
            print("⚠️ Cloudflare Tunnel URL을 추출하는데 시간이 걸리고 있습니다...")
            return None
            
        except Exception as e:
            print(f"❌ Cloudflare Tunnel 시작 실패: {e}")
            self.enabled = False
            return None
    
    def _extract_url(self):
        """터널 프로세스 출력에서 URL 추출"""
        try:
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    print(f"Cloudflare: {line.strip()}")
                    
                    # URL 패턴 찾기
                    url_match = re.search(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', line)
                    if url_match:
                        self.tunnel_url = url_match.group(0)
                        print()
                        print("🎉" + "=" * 50)
                        print(f"  Cloudflare Tunnel 준비 완료!")
                        print(f"  📍 외부 접속 URL: {self.tunnel_url}")
                        print(f"  🔗 어디서든 접속 가능합니다!")
                        print("=" * 52)
                        print()
                        break
                        
        except Exception as e:
            print(f"❌ URL 추출 중 오류: {e}")
    
    def stop(self):
        """터널 중지"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                print("🔴 Cloudflare Tunnel이 중지되었습니다.")
            except:
                self.process.kill()
                print("🔴 Cloudflare Tunnel이 강제 종료되었습니다.")

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
    global duckdns_updater, cloudflare_tunnel, firebase_fcm
    print("\n프로그램 종료 중...")
    
    try:
        # Firebase FCM 토큰 정리 (프로그램 종료 시)
        if 'firebase_fcm' in globals() and firebase_fcm is not None:
            firebase_fcm.shutdown_token_management()
        
        # DuckDNS 자동 업데이트 중지
        if duckdns_updater:
            duckdns_updater.stop()
        
        # 홈캠 인스턴스 정지
        if 'home_cam' in globals() and home_cam is not None:
            home_cam.stop()
            
        # 열린 창 닫기
        cv2.destroyAllWindows()
        
        # Cloudflare Tunnel 중지
        if cloudflare_tunnel:
            cloudflare_tunnel.stop()
        
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
        
        # 객체 감지 결과 큐
        self.detection_queue = queue.Queue()
        
        # 마지막 알림 시간
        self.last_notification_time = {}
        
        # 웹 스트리밍을 위한 변수
        self.frame = None
        self.detections = []
        
        # 녹화 관련 변수
        self.is_recording = False
        self.video_writer = None
        self.recording_start_time = None
        self.recording_thread = None
        self.recording_frames = queue.Queue(maxsize=300)  # 최대 300프레임 버퍼 (약 10초)
        
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
        global twilio_sms, firebase_fcm, duckdns_updater
        
        if not detections:
            return
            
        current_time = time.time()
        
        for label, confidence, _ in detections:
            if label in self.special_objects:
                if label not in self.last_notification_time or \
                   (current_time - self.last_notification_time[label]) > self.notification_cooldown:
                    
                    # Firebase FCM 알림 발송 (우선순위)
                    if firebase_fcm:
                        try:
                            # DuckDNS URL 생성
                            duckdns_url = "http://localhost:5000"
                            if duckdns_updater and duckdns_updater.enabled and duckdns_updater.domain:
                                duckdns_url = f"http://{duckdns_updater.domain}.duckdns.org:5000"
                            
                            # 감지된 객체 정보 구성
                            detected_objects = [{'name': label, 'confidence': confidence}]
                            
                            # FCM 알림 발송 (새로운 설정으로 재시도)
                            try:
                                success = firebase_fcm.send_detection_alert(
                                    detected_objects, 
                                    confidence,
                                    duckdns_url
                                )
                                
                                if success:
                                    print(f"📱 FCM 알림 발송 완료: {label} ({confidence:.1f}%)")
                                else:
                                    print(f"⚠️ FCM 알림 발송 실패 (토큰 없거나 쿨다운): {label}")
                            except Exception as fcm_error:
                                print(f"FCM 발송 중 오류: {fcm_error}")
                
                            # 콘솔 출력
                            print(f"🔔 감지 알림: {label} ({confidence:.1f}%)")
                                
                        except Exception as e:
                            print(f"FCM 발송 중 오류: {e}")
            
                    # Twilio SMS 알림 발송 (백업용)
                    if twilio_sms and twilio_sms.enabled:
                        success, result = twilio_sms.send_detection_alert(label, confidence)
                        if success:
                            print(f"📱 SMS 알림 발송 성공: {label}")
                        else:
                            print(f"❌ SMS 알림 발송 실패: {result}")
                    
                    # 감지 시간 기록
                    self.last_notification_time[label] = current_time

    
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
                
                # 녹화 중이면 프레임 추가
                if self.is_recording:
                    try:
                        # 큐가 가득 차면 오래된 프레임 제거
                        if self.recording_frames.full():
                            try:
                                self.recording_frames.get_nowait()
                            except queue.Empty:
                                pass
                        # 새 프레임 추가
                        self.recording_frames.put(frame.copy())
                    except Exception as e:
                        print(f"녹화 프레임 추가 중 오류: {e}")
                
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

    def save_snapshot(self, image_data):
        """Base64 이미지 데이터를 받아 스냅샷으로 저장합니다."""
        try:
            # 현재 시간을 기반으로 파일명 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{SNAPSHOTS_DIR}/snapshot_{timestamp}.jpg"
            
            # Base64 이미지 데이터를 디코딩하여 이미지로 변환
            image_bytes = base64.b64decode(image_data)
            
            # numpy 배열로 변환하여 OpenCV 이미지로 처리
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return False, "이미지 디코딩 실패"
            
            # 이미지 저장
            cv2.imwrite(filename, img)
            
            print(f"스냅샷 저장 완료: {filename}")
            return True, filename
            
        except Exception as e:
            print(f"스냅샷 저장 중 오류 발생: {e}")
            return False, str(e)
    
    def start_recording(self):
        """비디오 녹화를 시작합니다."""
        if self.is_recording:
            return False, "이미 녹화 중입니다."
            
        try:
            # 현재 시간 기록
            self.recording_start_time = datetime.now()
            timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")
            filename = f"{RECORDINGS_DIR}/recording_{timestamp}.mp4"
            
            # 비디오 작성기 초기화 (대기)
            self.is_recording = True
            
            # 별도 스레드에서 녹화 작업 시작
            self.recording_thread = threading.Thread(target=self._recording_worker, args=(filename,))
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
            print(f"녹화 시작: {filename}")
            return True, filename
            
        except Exception as e:
            self.is_recording = False
            print(f"녹화 시작 중 오류 발생: {e}")
            return False, str(e)
            
    def stop_recording(self):
        """비디오 녹화를 중지합니다."""
        if not self.is_recording:
            return False, "녹화 중이 아닙니다."
            
        try:
            # 녹화 중지 플래그 설정
            self.is_recording = False
            
            # 녹화 스레드가 종료될 때까지 대기
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=10)  # 최대 10초 대기
                
            print("녹화 중지 완료")
            
            # 저장된 파일명 생성
            timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")
            filename = f"{RECORDINGS_DIR}/recording_{timestamp}.mp4"
            
            return True, filename
            
        except Exception as e:
            print(f"녹화 중지 중 오류 발생: {e}")
            return False, str(e)
            
    def _recording_worker(self, filename):
        """별도 스레드에서 실행되어 녹화를 처리합니다."""
        print(f"녹화 작업자 스레드 시작: {filename}")
        
        video_writer = None
        frame_size = None
        
        try:
            # 첫 번째 프레임을 기다립니다 (최대 5초)
            first_frame = None
            wait_start = time.time()
            
            while time.time() - wait_start < 5:
                if not self.recording_frames.empty():
                    first_frame = self.recording_frames.get()
                    break
                time.sleep(0.1)
                
            if first_frame is None:
                print("녹화를 위한 프레임을 가져올 수 없습니다.")
                self.is_recording = False
                return
                
            # 프레임 크기 가져오기
            frame_size = (first_frame.shape[1], first_frame.shape[0])
            
            # 비디오 작성기 초기화
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # MP4 코덱
            video_writer = cv2.VideoWriter(filename, fourcc, 30.0, frame_size)
            
            # 첫 번째 프레임 쓰기
            video_writer.write(first_frame)
            
            # 녹화 루프
            while self.is_recording:
                try:
                    # 큐에서 프레임 가져오기 (최대 0.1초 대기)
                    frame = self.recording_frames.get(timeout=0.1)
                    
                    # 프레임 저장
                    if frame is not None and frame.size > 0:
                        video_writer.write(frame)
                except queue.Empty:
                    # 큐가 비어있으면 계속 진행
                    pass
                except Exception as e:
                    print(f"프레임 쓰기 중 오류: {e}")
                    
            # 남은 프레임 모두 처리
            while not self.recording_frames.empty():
                try:
                    frame = self.recording_frames.get_nowait()
                    if frame is not None and frame.size > 0:
                        video_writer.write(frame)
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"녹화 작업자 오류: {e}")
        finally:
            # 비디오 작성기 정리
            if video_writer:
                video_writer.release()
                print(f"녹화 파일 저장 완료: {filename}")
                
            # 녹화 큐 비우기
            while not self.recording_frames.empty():
                try:
                    self.recording_frames.get_nowait()
                except:
                    pass

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
    from firebase_config import VAPID_KEY
    return render_template('index.html', vapid_key=VAPID_KEY)

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

@app.route('/firebase-messaging-sw.js')
def firebase_sw():
    """Firebase Service Worker 파일 제공"""
    from flask import Response
    try:
        with open('static/firebase-messaging-sw.js', 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content, mimetype='application/javascript')
    except FileNotFoundError:
        return Response('console.log("Service Worker file not found");', mimetype='application/javascript'), 404

@app.route('/favicon.ico')
def favicon():
    """Favicon 파일 제공"""
    return app.send_static_file('favicon.ico')

# 스냅샷 및 녹화 API 경로 추가
@app.route('/snapshot', methods=['POST'])
@requires_auth
def snapshot():
    """현재 카메라 화면을 스냅샷으로 저장합니다."""
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'success': False, 'error': '이미지 데이터가 없습니다.'}), 400
        
        # Base64 이미지 데이터를 저장
        success, result = home_cam.save_snapshot(data['image'])
        
        if success:
            # 성공적으로 저장됨
            return jsonify({'success': True, 'filename': result})
        else:
            # 오류 발생
            return jsonify({'success': False, 'error': result}), 500
    
    except Exception as e:
        print(f"스냅샷 저장 처리 중 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/record/start', methods=['POST'])
@requires_auth
def start_recording():
    """비디오 녹화를 시작합니다."""
    try:
        success, result = home_cam.start_recording()
        
        if success:
            return jsonify({'success': True, 'filename': result})
        else:
            return jsonify({'success': False, 'error': result}), 400
    
    except Exception as e:
        print(f"녹화 시작 처리 중 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/record/stop', methods=['POST'])
@requires_auth
def stop_recording():
    """비디오 녹화를 중지합니다."""
    try:
        success, result = home_cam.stop_recording()
        
        if success:
            return jsonify({'success': True, 'filename': result})
        else:
            return jsonify({'success': False, 'error': result}), 400
    
    except Exception as e:
        print(f"녹화 중지 처리 중 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/test-sms', methods=['POST'])
@requires_auth
def test_sms():
    """Twilio SMS 테스트를 수행합니다."""
    global twilio_sms
    
    try:
        if not twilio_sms:
            return jsonify({'success': False, 'error': 'Twilio SMS가 초기화되지 않았습니다.'}), 500
            
        success, result = twilio_sms.send_test_sms()
        
        if success:
            return jsonify({'success': True, 'message_sid': result})
        else:
            return jsonify({'success': False, 'error': result}), 400
    
    except Exception as e:
        print(f"SMS 테스트 중 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/fcm/register', methods=['POST'])
@requires_auth
def register_fcm_token():
    """FCM 토큰 등록"""
    global firebase_fcm
    
    print("🔍 /fcm/register 엔드포인트 호출됨")
    
    if not firebase_fcm:
        print("❌ Firebase FCM이 초기화되지 않았습니다.")
        return jsonify({
            'success': False,
            'error': 'Firebase FCM이 초기화되지 않았습니다.'
        })
    
    try:
        data = request.get_json()
        print(f"🔍 받은 데이터: {data}")
        
        token = data.get('token') if data else None
        
        if not token:
            print("❌ FCM 토큰이 제공되지 않았습니다.")
            return jsonify({
                'success': False,
                'error': 'FCM 토큰이 제공되지 않았습니다.'
            })
        
        print(f"🔍 받은 FCM 토큰 길이: {len(token)} 문자")
        print(f"🔍 토큰 앞 20자: {token[:20]}...")
        
        # 기존 토큰 개수 확인
        before_count = len(firebase_fcm.device_tokens)
        print(f"🔍 토큰 등록 전 개수: {before_count}")
        
        firebase_fcm.add_device_token(token)
        
        # 등록 후 토큰 개수 확인
        after_count = len(firebase_fcm.device_tokens)
        print(f"🔍 토큰 등록 후 개수: {after_count}")
        
        print("✅ FCM 토큰이 성공적으로 등록되었습니다!")
        
        return jsonify({
            'success': True,
            'message': f'FCM 토큰이 성공적으로 등록되었습니다. (총 {after_count}개 토큰)'
        })
        
    except Exception as e:
        print(f"❌ FCM 토큰 등록 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'FCM 토큰 등록 중 오류: {str(e)}'
        })

@app.route('/fcm/tokens', methods=['GET'])
@requires_auth
def get_fcm_tokens():
    """현재 등록된 FCM 토큰 정보 조회"""
    global firebase_fcm
    
    if not firebase_fcm:
        return jsonify({
            'success': False,
            'error': 'Firebase FCM이 초기화되지 않았습니다.'
        })
    
    try:
        token_info = firebase_fcm.get_token_info()
        return jsonify({
            'success': True,
            'data': token_info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'토큰 정보 조회 중 오류: {str(e)}'
        })

@app.route('/test-fcm', methods=['POST'])
@requires_auth
def test_fcm():
    """FCM 테스트 알림 전송"""
    global firebase_fcm
    
    print("🔍 /test-fcm 엔드포인트 호출됨")
    
    if not firebase_fcm:
        print("❌ Firebase FCM이 초기화되지 않았습니다.")
        return jsonify({
            'success': False,
            'error': 'Firebase FCM이 초기화되지 않았습니다.'
        })
    
    # 토큰 정보 상세 출력
    token_info = firebase_fcm.get_token_info()
    print(f"🔍 현재 등록된 토큰 수: {token_info['total_tokens']}")
    print(f"🔍 토큰 미리보기: {token_info['tokens_preview']}")
    
    try:
        success = firebase_fcm.test_notification()
        
        print(f"🔍 FCM 전송 결과: {success}")
        
        return jsonify({
            'success': success,
            'message': f'FCM 테스트 알림이 발송되었습니다. (등록된 토큰: {token_info["total_tokens"]}개)' if success else f'FCM 테스트 알림 발송에 실패했습니다. (등록된 토큰: {token_info["total_tokens"]}개)',
            'token_count': token_info['total_tokens']
        })
        
    except Exception as e:
        print(f"❌ /test-fcm 예외 발생: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'FCM 테스트 알림 전송 중 오류: {str(e)}'
        })

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
            flex-wrap: wrap;
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
        button.notification {
            background-color: #2196F3;
        }
        button.notification:hover {
            background-color: #1976D2;
        }
        button.test {
            background-color: #FF9800;
        }
        button.test:hover {
            background-color: #F57C00;
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
        .notification-status {
            margin-top: 20px;
            padding: 10px;
            border-radius: 4px;
            text-align: center;
            font-weight: bold;
        }
        .notification-enabled {
            background-color: #e8f5e9;
            color: #2e7d32;
        }
        .notification-disabled {
            background-color: #ffebee;
            color: #c62828;
        }
        .notification-pending {
            background-color: #fff3e0;
            color: #ef6c00;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏠 YOLOv5 스마트홈 카메라 🎥</h1>
        
        <div class="camera-feed">
            <img id="video-feed" src="" alt="카메라 스트림">
            <div class="status" id="status">연결 중...</div>
        </div>
        
        <div class="controls">
            <button id="restart-btn">카메라 재시작</button>
            <button id="shutdown-btn" class="danger">프로그램 종료</button>
            <button id="enable-notifications-btn" class="notification">알림 권한 요청</button>
            <button id="test-fcm-btn" class="test">푸시 알림 테스트</button>
        </div>
        
        <div id="notification-status" class="notification-status notification-disabled">
            📱 푸시 알림: 비활성화
        </div>
        
        <div id="token-info" style="margin-top: 10px; padding: 8px; background-color: #f5f5f5; border-radius: 4px; font-size: 12px; color: #666;">
            🔑 등록된 토큰: 확인 중...
        </div>
        
        <div class="detections">
            <h2>감지된 객체</h2>
            <div id="detection-list">감지 중...</div>
        </div>
    </div>

    <!-- Firebase SDK -->
    <script src="https://www.gstatic.com/firebasejs/9.15.0/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/9.15.0/firebase-messaging-compat.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    
    <script>
        // Firebase 설정
        const firebaseConfig = {
            apiKey: "AIzaSyBoSjqjyHo6Yr-IHHuslSJ_AGVZG3QXJdU",
            authDomain: "sonavi-home-cctv-bf6e3.firebaseapp.com", 
            projectId: "sonavi-home-cctv-bf6e3",
            storageBucket: "sonavi-home-cctv-bf6e3.firebasestorage.app",
            messagingSenderId: "568007893096",
            appId: "1:568007893096:web:8b7ddfde89fe4cc6b8ede8"
        };
        
        // Firebase 초기화
        firebase.initializeApp(firebaseConfig);
        const messaging = firebase.messaging();
        
        // VAPID 키 설정
        const vapidKey = "{{ vapid_key }}";
        
        let fcmToken = null;
        let notificationStatus = 'disabled';
        
        // 상태 업데이트 함수들
        function updateNotificationStatus(status, message) {
            const statusDiv = document.getElementById('notification-status');
            const enableBtn = document.getElementById('enable-notifications-btn');
            
            notificationStatus = status;
            statusDiv.className = `notification-status notification-${status}`;
            
            switch(status) {
                case 'enabled':
                    statusDiv.innerHTML = '📱 푸시 알림: 활성화 ✅';
                    enableBtn.textContent = '알림 비활성화';
                    enableBtn.className = 'button danger';
                    break;
                case 'disabled':
                    statusDiv.innerHTML = '📱 푸시 알림: 비활성화 ❌';
                    enableBtn.textContent = '알림 권한 요청';
                    enableBtn.className = 'button notification';
                    break;
                case 'pending':
                    statusDiv.innerHTML = '📱 푸시 알림: 권한 요청 중... ⏳';
                    enableBtn.textContent = '요청 중...';
                    enableBtn.disabled = true;
                    break;
            }
            
            if (message) {
                console.log(`알림 상태: ${message}`);
            }
        }
        
        // FCM 토큰 등록
        async function registerFCMToken(token) {
            try {
                const response = await fetch('/fcm/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ token: token })
                });
                
                const result = await response.json();
                if (result.success) {
                    console.log('✅ FCM 토큰 등록 성공:', result.message);
                    updateNotificationStatus('enabled', 'FCM 토큰 등록 완료');
                    updateTokenInfo(); // 토큰 정보 즉시 업데이트
                    return true;
                } else {
                    console.error('❌ FCM 토큰 등록 실패:', result.error);
                    updateNotificationStatus('disabled', `토큰 등록 실패: ${result.error}`);
                    return false;
                }
            } catch (error) {
                console.error('❌ FCM 토큰 등록 요청 오류:', error);
                updateNotificationStatus('disabled', `요청 오류: ${error.message}`);
                return false;
            }
        }
        
        // 알림 권한 요청 및 토큰 생성
        async function requestNotificationPermission() {
            try {
                console.log('🔔 알림 권한 요청 중...');
                updateNotificationStatus('pending');
                
                // 현재 권한 상태 확인
                console.log('현재 알림 권한 상태:', Notification.permission);
                
                // 알림 권한 요청
                const permission = await Notification.requestPermission();
                console.log('알림 권한 응답:', permission);
                
                if (permission === 'granted') {
                    console.log('✅ 알림 권한 승인됨');
                    
                    // Service Worker 등록
                    if ('serviceWorker' in navigator) {
                        console.log('🔧 Service Worker 등록 중...');
                        const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
                        console.log('✅ Service Worker 등록 완료:', registration);
                    } else {
                        console.warn('⚠️ 이 브라우저는 Service Worker를 지원하지 않습니다');
                    }
                    
                    // FCM 토큰 생성
                    console.log('🔑 FCM 토큰 생성 중...');
                    console.log('사용할 VAPID 키:', vapidKey);
                    
                    const token = await messaging.getToken({ 
                        vapidKey: vapidKey,
                        serviceWorkerRegistration: await navigator.serviceWorker.ready
                    });
                    
                    if (token) {
                        console.log('✅ FCM 토큰 생성 완료!');
                        console.log('토큰 길이:', token.length, '문자');
                        console.log('토큰 앞 20자:', token.substring(0, 20) + '...');
                        fcmToken = token;
                        
                        // 서버에 토큰 등록
                        console.log('🌐 서버에 토큰 등록 중...');
                        const registered = await registerFCMToken(token);
                        
                        if (registered) {
                            console.log('🎉 모든 설정 완료! 푸시 알림을 받을 수 있습니다.');
                            
                            // 토큰 갱신 감지
                            messaging.onTokenRefresh(async () => {
                                console.log('🔄 FCM 토큰 갱신됨');
                                const refreshedToken = await messaging.getToken({ vapidKey: vapidKey });
                                if (refreshedToken) {
                                    fcmToken = refreshedToken;
                                    await registerFCMToken(refreshedToken);
                                }
                            });
                            
                            // 포그라운드 메시지 수신
                            messaging.onMessage((payload) => {
                                console.log('📨 포그라운드 메시지 수신:', payload);
                                
                                // 브라우저 알림 표시
                                if (payload.notification) {
                                    new Notification(payload.notification.title, {
                                        body: payload.notification.body,
                                        icon: '/static/icon-192x192.png'
                                    });
                                }
                            });
                        }
                    } else {
                        throw new Error('FCM 토큰이 생성되지 않았습니다. VAPID 키를 확인해주세요.');
                    }
                } else if (permission === 'denied') {
                    throw new Error('알림 권한이 거부되었습니다. 브라우저 설정에서 알림을 허용해주세요.');
                } else {
                    throw new Error(`알림 권한이 기본값입니다: ${permission}`);
                }
            } catch (error) {
                console.error('❌ 알림 권한 요청 오류:', error);
                console.error('오류 상세:', error.message);
                updateNotificationStatus('disabled', `오류: ${error.message}`);
                
                // 사용자에게 친화적인 메시지 표시
                alert(`푸시 알림 설정 오류:\n${error.message}\n\n브라우저 설정에서 알림을 허용한 후 다시 시도해주세요.`);
            }
        }
        
        // 알림 비활성화
        async function disableNotifications() {
            try {
                if (fcmToken) {
                    await messaging.deleteToken();
                    fcmToken = null;
                }
                updateNotificationStatus('disabled', '알림이 비활성화되었습니다');
            } catch (error) {
                console.error('❌ 알림 비활성화 오류:', error);
            }
        }
        
        // 토큰 정보 업데이트
        async function updateTokenInfo() {
            try {
                const response = await fetch('/fcm/tokens');
                const result = await response.json();
                
                const tokenInfoDiv = document.getElementById('token-info');
                
                if (result.success) {
                    const data = result.data;
                    tokenInfoDiv.innerHTML = `🔑 등록된 토큰: ${data.total_tokens}개 | 로드시간: ${new Date().toLocaleTimeString()}`;
                    
                    if (data.total_tokens > 0) {
                        tokenInfoDiv.style.backgroundColor = '#e8f5e9';
                        tokenInfoDiv.style.color = '#2e7d32';
                    } else {
                        tokenInfoDiv.style.backgroundColor = '#ffebee';
                        tokenInfoDiv.style.color = '#c62828';
                    }
                } else {
                    tokenInfoDiv.innerHTML = `🔑 토큰 정보 오류: ${result.error}`;
                    tokenInfoDiv.style.backgroundColor = '#ffebee';
                    tokenInfoDiv.style.color = '#c62828';
                }
            } catch (error) {
                console.error('토큰 정보 업데이트 오류:', error);
            }
        }
        
        // FCM 테스트
        async function testFCM() {
            try {
                if (notificationStatus !== 'enabled') {
                    alert('먼저 알림 권한을 허용해주세요!');
                    return;
                }
                
                console.log('🧪 FCM 테스트 알림 발송 중...');
                
                const response = await fetch('/test-fcm', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });
                
                const result = await response.json();
                
                if (result.success) {
                    console.log('✅ FCM 테스트 성공:', result.message);
                    alert(`푸시 알림 테스트가 발송되었습니다! 📱\n등록된 토큰: ${result.token_count}개`);
                } else {
                    console.error('❌ FCM 테스트 실패:', result.error);
                    alert(`푸시 알림 테스트 실패: ${result.error}`);
                }
                
                // 테스트 후 토큰 정보 업데이트
                updateTokenInfo();
                
            } catch (error) {
                console.error('❌ FCM 테스트 요청 오류:', error);
                alert(`요청 오류: ${error.message}`);
            }
        }
        
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
            const enableNotificationsBtn = document.getElementById('enable-notifications-btn');
            const testFcmBtn = document.getElementById('test-fcm-btn');
            
            // 초기 알림 상태 확인
            if (Notification.permission === 'granted') {
                requestNotificationPermission();
            }
            
            // 토큰 정보 초기 로드 및 주기적 업데이트
            updateTokenInfo();
            setInterval(updateTokenInfo, 10000); // 10초마다 업데이트
            
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
            
            // 알림 권한 버튼
            enableNotificationsBtn.addEventListener('click', () => {
                if (notificationStatus === 'enabled') {
                    disableNotifications();
                } else {
                    requestNotificationPermission();
                }
            });
            
            // FCM 테스트 버튼
            testFcmBtn.addEventListener('click', testFCM);
        });
    </script>
</body>
</html>""")
        
        # Signal handler 설정 (Ctrl+C 처리)
        signal.signal(signal.SIGINT, signal_handler)
        
        # 인증 설정 로드
        load_auth_config()
        
        # DuckDNS 자동 업데이트 시작
        duckdns_updater = DuckDNSUpdater()
        duckdns_updater.start_auto_update()
        
        # Twilio SMS 시스템 시작
        twilio_sms = TwilioSMS()
        
        # Firebase FCM 시스템 시작
        firebase_fcm = FirebaseFCM()
        
        # 프로그램 시작 시 토큰 관리
        firebase_fcm.startup_token_management()
        
        # Cloudflare Tunnel 시작
        cloudflare_tunnel = CloudflareTunnel()
        cloudflare_tunnel.start_tunnel()
        
        # 스마트 홈캠 인스턴스 생성 및 시작
        print("YOLOv5 스마트홈 카메라 시스템 시작 중...")
        home_cam = SmartHomeCam(camera_id=1, model_type='nano')
        if not home_cam.start():
            print("카메라 시스템 시작 실패. 프로그램 종료.")
            sys.exit(1)
        
        print("=" * 60)
        print("🏠 YOLOv5 스마트홈 카메라 시스템이 시작되었습니다! 🎥")
        print("=" * 60)
        print()
        print("📱 접속 방법:")
        print(f"   로컬 접속: http://localhost:5000")
        
        # DuckDNS 정보 표시
        if duckdns_updater.enabled and duckdns_updater.current_ip:
            print(f"   DuckDNS 접속: http://{duckdns_updater.domain}.duckdns.org:5000")
        
        # Cloudflare Tunnel 정보 표시
        if cloudflare_tunnel and cloudflare_tunnel.tunnel_url:
            print(f"   🌐 Cloudflare Tunnel: {cloudflare_tunnel.tunnel_url}")
            print("      (✅ 어디서든 접속 가능)")
        elif cloudflare_tunnel and cloudflare_tunnel.enabled:
            print("   🌐 Cloudflare Tunnel: 시작 중...")
        else:
            print("   🌐 Cloudflare Tunnel: 비활성화")
        
        print()
        print("🔐 로그인 정보:")
        print(f"   사용자명: {USERNAME}")
        print(f"   비밀번호: {PASSWORD}")
        print()
        print("⚠️  종료하려면 Ctrl+C를 누르세요")
        print("=" * 60)
        
        # Flask 앱 직접 실행
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
        
    except KeyboardInterrupt:
        # Ctrl+C가 감지되면 이 부분이 실행됨
        cleanup_and_exit()
    except Exception as e:
        print(f"프로그램 실행 중 오류 발생: {e}")
        cleanup_and_exit() 