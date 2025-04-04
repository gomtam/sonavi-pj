from flask import Flask, render_template, Response, request, jsonify
from flask_socketio import SocketIO
import cv2
import numpy as np
import threading
import time
import os
from datetime import datetime
from modules.camera import Camera
from modules.audio_detector import AudioDetector
from modules.tts_engine import TTSEngine
from modules.ai_chat import AIChat

app = Flask(__name__)
socketio = SocketIO(app)
camera = None
audio_detector = None
tts_engine = None
ai_chat = None

# 이미지 저장 디렉토리
CAPTURE_DIR = os.path.join('static', 'captures')
os.makedirs(CAPTURE_DIR, exist_ok=True)

# 초기화 함수
def init_modules():
    global audio_detector, tts_engine, ai_chat
    # camera = Camera()  # Camera 모듈은 사용하지 않음
    
    # 오디오 감지기 초기화
    try:
        audio_detector = AudioDetector(door_sound_callback)
        # 모듈 스레드 시작
        threading.Thread(target=audio_detector.start_monitoring, daemon=True).start()
    except Exception as e:
        print(f"오디오 감지기 초기화 오류: {e}")
        audio_detector = None
    
    # TTS 엔진 초기화
    try:
        tts_engine = TTSEngine()
    except Exception as e:
        print(f"TTS 엔진 초기화 오류: {e}")
        tts_engine = None
    
    # AI 채팅 초기화
    try:
        ai_chat = AIChat()
    except Exception as e:
        print(f"AI 채팅 초기화 오류: {e}")
        ai_chat = None

# 문 소리 감지 콜백
def door_sound_callback(sound_type):
    message = ""
    if sound_type == "open":
        message = "안녕하세요! 어서오세요!"
    elif sound_type == "close":
        message = "안녕히 가세요! 다음에 또 만나요!"
    
    tts_engine.speak(message)
    socketio.emit('notification', {'message': message})

# 라우트: 메인 페이지
@app.route('/')
def index():
    return render_template('index.html')

# 비디오 스트림 생성
def generate_frames():
    # 공유 카메라 객체 생성
    print("카메라 스트림 초기화 중...")
    camera_index = 0  # 기본 카메라 인덱스 (설정에서 변경 가능하게 만들 수 있음)
    
    # 다양한 백엔드로 시도
    camera_opened = False
    cap = None
    
    for api in [cv2.CAP_ANY, cv2.CAP_DSHOW, cv2.CAP_MSMF]:
        try:
            cap = cv2.VideoCapture(camera_index, api)
            if cap.isOpened():
                # 카메라 설정
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                api_name = {cv2.CAP_ANY: "ANY", cv2.CAP_DSHOW: "DSHOW", cv2.CAP_MSMF: "MSMF"}
                print(f"카메라 {camera_index}가 {api_name.get(api, 'UNKNOWN')} 백엔드로 열렸습니다!")
                camera_opened = True
                break
        except Exception as e:
            print(f"백엔드 {api} 시도 중 오류: {e}")
            if cap:
                cap.release()
                cap = None
    
    if not camera_opened:
        print("어떤 백엔드로도 카메라를 열 수 없습니다.")
        cap = None
    
    # 프레임 전송 루프
    frame_count = 0
    while True:
        try:
            if cap is not None and cap.isOpened():
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    # 가끔씩만 가로세로 크기 조정 (성능 향상)
                    if frame_count % 10 == 0:
                        frame = cv2.resize(frame, (640, 480))
                    
                    # JPEG로 인코딩
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                    
                    frame_count += 1
                else:
                    # 읽기 실패 시 카메라 재초기화 
                    print("프레임을 읽지 못했습니다. 카메라 재초기화...")
                    if cap:
                        cap.release()
                    
                    # 동일한 백엔드로 재시도
                    cap = cv2.VideoCapture(camera_index)
                    
                    # 실패하면 오류 프레임 표시
                    empty_frame = np.zeros((480, 640, 3), np.uint8)
                    cv2.putText(empty_frame, "Camera Error - Reconnecting", (100, 240), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    ret, buffer = cv2.imencode('.jpg', empty_frame)
                    if ret:
                        yield (b'--frame\r\n'
                              b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            else:
                # 카메라를 열 수 없는 경우
                empty_frame = np.zeros((480, 640, 3), np.uint8)
                cv2.putText(empty_frame, "Cannot Open Camera", (120, 240), 
                          cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                ret, buffer = cv2.imencode('.jpg', empty_frame)
                if ret:
                    yield (b'--frame\r\n'
                          b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                
                # 잠시 기다린 후 카메라 다시 열기 시도
                time.sleep(1)
                for api in [cv2.CAP_ANY, cv2.CAP_DSHOW, cv2.CAP_MSMF]:
                    try:
                        new_cap = cv2.VideoCapture(camera_index, api)
                        if new_cap.isOpened():
                            cap = new_cap
                            print("카메라에 다시 연결되었습니다!")
                            break
                        else:
                            new_cap.release()
                    except:
                        pass
        
        except Exception as e:
            print(f"스트리밍 오류: {e}")
            # 오류 발생 시 빈 프레임 생성
            empty_frame = np.zeros((480, 640, 3), np.uint8)
            cv2.putText(empty_frame, f"Error", (200, 240), 
                      cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            ret, buffer = cv2.imencode('.jpg', empty_frame)
            if ret:
                yield (b'--frame\r\n'
                      b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        # 각 프레임 간 딜레이
        time.sleep(0.05)  # 20 FPS

# 라우트: 비디오 스트림
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# 라우트: 카메라 제어
@app.route('/control_camera', methods=['POST'])
def control_camera():
    direction = request.json.get('direction')
    if direction:
        # 카메라 이동 메시지만 표시 (실제 서보모터가 없는 경우)
        print(f"카메라 이동 요청: {direction}")
        return jsonify({"status": "success", "message": f"카메라 {direction} 방향 이동 명령 처리됨"})
    return jsonify({"status": "error", "message": "잘못된 요청입니다"})

# 라우트: 사진 캡처
@app.route('/capture', methods=['POST'])
def capture():
    try:
        # request.json이 None인 경우 빈 딕셔너리로 처리
        req_data = request.json if request.json is not None else {}
        camera_index = req_data.get('camera_index', 0)  # 기본값은 0
        
        # 여러 백엔드 시도
        cap = None
        for api in [cv2.CAP_ANY, cv2.CAP_DSHOW, cv2.CAP_MSMF]:
            try:
                cap = cv2.VideoCapture(camera_index, api)
                if cap.isOpened():
                    api_name = {cv2.CAP_ANY: "ANY", cv2.CAP_DSHOW: "DSHOW", cv2.CAP_MSMF: "MSMF"}
                    print(f"캡처: 카메라 {camera_index}가 {api_name.get(api, 'UNKNOWN')} 백엔드로 열렸습니다!")
                    break
                else:
                    cap.release()
                    cap = None
            except Exception as e:
                print(f"캡처 중 백엔드 {api} 시도 중 오류: {e}")
                if cap:
                    cap.release()
                    cap = None
        
        if cap is not None and cap.isOpened():
            # 카메라에서 프레임 읽기
            ret, frame = cap.read()
            cap.release()
            
            if ret and frame is not None:
                # 타임스탬프로 파일 이름 생성
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"capture_{timestamp}.jpg"
                filepath = os.path.join(CAPTURE_DIR, filename)
                
                # 이미지 저장
                cv2.imwrite(filepath, frame)
                
                return jsonify({
                    "status": "success", 
                    "filename": filename,
                    "path": filepath.replace('\\', '/')
                })
            else:
                return jsonify({"status": "error", "message": "카메라에서 이미지를 읽을 수 없습니다"})
        else:
            return jsonify({"status": "error", "message": f"카메라 인덱스 {camera_index}를 열 수 없습니다"})
            
    except Exception as e:
        import traceback
        print(f"캡처 중 오류 발생: {str(e)}")
        print(traceback.format_exc())  # 자세한 오류 추적 정보 출력
        return jsonify({"status": "error", "message": f"오류: {str(e)}"})

# 라우트: AI 채팅
@app.route('/chat', methods=['POST'])
def chat():
    message = request.json.get('message')
    if message and ai_chat:
        response = ai_chat.get_response(message)
        tts_engine.speak(response)
        return jsonify({"status": "success", "response": response})
    return jsonify({"status": "error", "message": "Invalid request"})

# 라우트: 음성 학습
@app.route('/train_voice', methods=['POST'])
def train_voice():
    voice_samples = request.files.getlist('samples')
    if voice_samples and tts_engine:
        result = tts_engine.train_voice(voice_samples)
        return jsonify({"status": "success" if result else "error"})
    return jsonify({"status": "error", "message": "No voice samples provided"})

# 소켓 이벤트 핸들러
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    init_modules()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True) 