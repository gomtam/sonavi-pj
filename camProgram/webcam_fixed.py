from flask import Flask, Response, render_template, request, make_response, redirect
import cv2
import socket
import os
import logging
import requests
from werkzeug.security import generate_password_hash, check_password_hash
import subprocess
import sys
import time
from pyngrok import ngrok, conf

# ngrok 인증 토큰 설정
NGROK_AUTH_TOKEN = "2uXP7dCg3XzJugznmHYGaen1WUO_5EyJXhEoh5vdmqkoi9fgz"  # 이미 테스트 완료된 토큰
# 토큰은 아래와 같은 형식입니다: 2LcMjEMwQPj2aFh9B5qTEomnHBz_...
# 대시보드에서 'Copy' 버튼을 클릭하여 복사한 후 큰따옴표 안에 붙여넣으세요

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)
camera = cv2.VideoCapture(0)

# 보안 설정 - 쉬운 비밀번호 사용
DEFAULT_PASSWORD = "0130"  # 기본 비밀번호
PASSWORD_HASH = generate_password_hash(DEFAULT_PASSWORD)

def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        return response.json()['ip']
    except Exception as e:
        logger.error(f"공인 IP 확인 중 오류: {e}")
        return None

def check_port_forwarding(port):
    try:
        # 외부에서 포트 접근 가능 여부 확인
        try:
            response = requests.get(f'https://portchecker.co/check', params={
                'port': port,
                'ip': get_public_ip()
            }, timeout=10)
            if 'open' in response.text.lower():
                return True
        except Exception as e:
            logger.error(f"외부 포트 체크 서비스 접속 오류: {e}")
        
        # 로컬 포트 확인
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except Exception as e:
        logger.error(f"포트 확인 중 오류: {e}")
        return False

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            logger.error("카메라에서 프레임을 읽는데 실패했습니다.")
            break
        else:
            try:
                _, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            except Exception as e:
                logger.error(f"프레임 변환 중 오류 발생: {e}")
                break

def get_ip_address():
    # 현재 기기의 IP 주소를 찾기
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 인터넷에 연결되지 않아도 작동
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception as e:
        logger.error(f"IP 주소 확인 중 오류: {e}")
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# 메인 페이지 템플릿
def get_login_template(local_ip, public_ip, port_status):
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>웹캠 로그인</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                text-align: center;
                background-color: #f5f5f5;
            }}
            .login-container {{
                max-width: 400px;
                margin: 50px auto;
                padding: 20px;
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            input[type="password"] {{
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                border: 1px solid #ddd;
                border-radius: 4px;
            }}
            button {{
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }}
            button:hover {{
                background-color: #45a049;
            }}
            .info {{
                margin-top: 20px;
                color: #666;
                font-size: 0.9em;
            }}
        </style>
    </head>
    <body>
        <div class="login-container">
            <h2>웹캠 접속</h2>
            <form method="POST" action="/login">
                <input type="password" name="password" placeholder="비밀번호를 입력하세요" required>
                <br>
                <button type="submit">로그인</button>
            </form>
            <div class="info">
                <p>카메라 보안 접속</p>
            </div>
        </div>
    </body>
    </html>
    '''

def get_streaming_template(local_ip, public_ip, port_status):
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>웹캠 스트리밍</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                text-align: center;
                background-color: #f5f5f5;
            }}
            h1 {{
                color: #333;
            }}
            .video-container {{
                max-width: 800px;
                margin: 20px auto;
                padding: 20px;
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            img {{
                max-width: 100%;
                height: auto;
                border: 1px solid #ddd;
                border-radius: 4px;
            }}
            .logout-btn {{
                background-color: #f44336;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                margin-top: 20px;
            }}
            .logout-btn:hover {{
                background-color: #da190b;
            }}
        </style>
    </head>
    <body>
        <h1>웹캠 실시간 스트리밍</h1>
        <div class="video-container">
            <img src="/video_feed" alt="웹캠 스트림">
        </div>
        <a href="/logout" class="logout-btn">로그아웃</a>
    </body>
    </html>
    '''

@app.route('/')
def index():
    """메인 페이지 - 인증 확인 후 로그인 또는 스트리밍 페이지 표시"""
    if not request.cookies.get('authenticated'):
        # 로그인 페이지 표시
        local_ip = get_ip_address()
        public_ip = get_public_ip() or "확인 불가"
        port_status = "열림" if check_port_forwarding(5000) else "닫힘"
        return get_login_template(local_ip, public_ip, port_status)
    
    # 스트리밍 페이지 표시
    local_ip = get_ip_address()
    public_ip = get_public_ip() or "확인 불가"
    port_status = "열림" if check_port_forwarding(5000) else "닫힘"
    return get_streaming_template(local_ip, public_ip, port_status)

@app.route('/login', methods=['POST'])
def login():
    """로그인 처리"""
    password = request.form.get('password')
    
    if password == DEFAULT_PASSWORD:
        # 인증 성공
        resp = make_response(redirect('/'))
        resp.set_cookie('authenticated', 'true')
        return resp
    
    # 인증 실패
    local_ip = get_ip_address()
    public_ip = get_public_ip() or "확인 불가"
    port_status = "열림" if check_port_forwarding(5000) else "닫힘"
    return get_login_template(local_ip, public_ip, port_status) + '<p style="color: red;">비밀번호가 올바르지 않습니다.</p>'

@app.route('/logout')
def logout():
    """로그아웃 처리"""
    resp = make_response(redirect('/'))
    resp.delete_cookie('authenticated')
    return resp

@app.route('/video_feed')
def video_feed():
    """비디오 스트림 제공"""
    if not request.cookies.get('authenticated'):
        return redirect('/')
    
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/test')
def test():
    """서버 작동 테스트 페이지"""
    return "서버가 정상 작동 중입니다."

def setup_ngrok(port):
    """ngrok 터널링 서비스를 설정하고 URL을 반환합니다"""
    try:
        # ngrok 토큰 설정
        if NGROK_AUTH_TOKEN:
            conf.get_default().auth_token = NGROK_AUTH_TOKEN
            
        # ngrok 터널 생성
        try:
            # 기존 터널 모두 닫기
            for tunnel in ngrok.get_tunnels():
                ngrok.disconnect(tunnel.public_url)
                
            # 새 터널 생성
            ngrok_tunnel = ngrok.connect(port, "http")
            public_url = ngrok_tunnel.public_url
            logger.info(f"ngrok 터널 생성 완료: {public_url}")
            return public_url
        except Exception as e:
            logger.error(f"ngrok 터널 생성 실패: {e}")
            print(f"\nngrok 연결 오류: {e}")
            print("\n인증 토큰 설정 방법:")
            print("1. NGROK_AUTH_TOKEN 변수에 인증 토큰을 직접 입력하세요")
            print("   예: NGROK_AUTH_TOKEN = \"1a2b3c4d5e6f7g8h9i0j\"")
            print("2. 파일을 저장한 후 다시 실행하세요")
            return None
    except Exception as e:
        logger.error(f"ngrok 설정 중 오류: {e}")
        return None

if __name__ == "__main__":
    ip_address = get_ip_address()
    public_ip = get_public_ip()
    port = 5000
    port_status = "열림" if check_port_forwarding(port) else "닫힘"
    
    # ngrok 터널 설정
    ngrok_url = setup_ngrok(port)
    
    print("\n======== 웹캠 스트리밍 서버 ========")
    
    # 로컬 접속 정보
    print("\n[로컬 접속]")
    print(f"로컬: http://localhost:{port}")
    print(f"같은 네트워크: http://{ip_address}:{port}")
    
    # 외부 접속 정보
    print("\n[외부 접속]")
    if ngrok_url:
        print(f"ngrok URL: {ngrok_url} (외부 네트워크에서 접속 가능)")
    else:
        print("ngrok 연결 실패 - 토큰 설정을 확인하세요")
    
    # 접속 방법
    print("\n[접속 방법]")
    print("1. 브라우저에서 위 URL 중 하나로 접속")
    print("2. 로그인 화면에서 비밀번호 입력하기")
    print("3. 웹캠 스트리밍 시작")
    
    # 보안 정보
    print("\n[보안 정보]")
    print(f"기본 비밀번호: {DEFAULT_PASSWORD}")
    
    # 실행 정보
    print("\n======== 서버 실행 중 ========")
    
    # 디버그 모드 사용, 모든 인터페이스에서 수신
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True) 