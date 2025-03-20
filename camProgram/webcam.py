from flask import Flask, Response, render_template, request
import cv2
import socket
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
camera = cv2.VideoCapture(0)

# 보안 설정
SECRET_KEY = os.urandom(24)
PASSWORD_HASH = generate_password_hash('0130')  # 실제 사용시 이 비밀번호를 변경하세요

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            _, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    if not request.cookies.get('authenticated'):
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>웹캠 로그인</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    text-align: center;
                    background-color: #f5f5f5;
                }
                .login-container {
                    max-width: 400px;
                    margin: 50px auto;
                    padding: 20px;
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                input[type="password"] {
                    width: 100%;
                    padding: 10px;
                    margin: 10px 0;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }
                button {
                    background-color: #4CAF50;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }
                button:hover {
                    background-color: #45a049;
                }
            </style>
        </head>
        <body>
            <div class="login-container">
                <h2>웹캠 접속</h2>
                <form method="POST" action="/login">
                    <input type="password" name="password" placeholder="비밀번호를 입력하세요" required>
                    <br>
                    <button type="submit">접속</button>
                </form>
            </div>
        </body>
        </html>
        '''
    
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>웹캠 스트리밍</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                text-align: center;
                background-color: #f5f5f5;
            }
            h1 {
                color: #333;
            }
            .video-container {
                max-width: 800px;
                margin: 20px auto;
                padding: 20px;
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            img {
                max-width: 100%;
                height: auto;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            .logout-btn {
                background-color: #f44336;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                margin-top: 20px;
            }
            .logout-btn:hover {
                background-color: #da190b;
            }
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

@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password')
    if check_password_hash(PASSWORD_HASH, password):
        response = Response('', status=302)
        response.headers['Location'] = '/'
        response.set_cookie('authenticated', 'true', httponly=True, secure=True)
        return response
    return '잘못된 비밀번호입니다.', 401

@app.route('/logout')
def logout():
    response = Response('', status=302)
    response.headers['Location'] = '/'
    response.delete_cookie('authenticated')
    return response

@app.route('/video_feed')
def video_feed():
    if not request.cookies.get('authenticated'):
        return Response('인증되지 않은 접근입니다.', status=401)
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def get_ip_address():
    # 현재 기기의 IP 주소를 찾기
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 인터넷에 연결되지 않아도 작동
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    ip_address = get_ip_address()
    port = 5000
    print(f"\n웹캠 스트리밍 서버가 시작되었습니다.")
    print(f"로컬에서 접속: http://localhost:{port}")
    print(f"같은 네트워크의 다른 기기에서 접속: http://{ip_address}:{port}")
    print(f"\n외부 접속을 위한 설정:")
    print("1. 공유기/라우터에서 포트 포워딩 설정:")
    print(f"   - 외부 포트: {port}")
    print(f"   - 내부 IP: {ip_address}")
    print(f"   - 내부 포트: {port}")
    print("\n2. 공인 IP 주소 확인:")
    print("   - https://www.whatismyip.com 에서 확인 가능")
    print("\n3. 접속 방법:")
    print(f"   - http://[공인IP]:{port}")
    print("\n4. 보안:")
    print("   - 기본 비밀번호: your_secure_password")
    print("   - 실제 사용시 webcam.py 파일의 PASSWORD_HASH 값을 변경하세요")
    print("\n주의: 외부 접속 시 보안을 위해 반드시 비밀번호를 변경하세요!")
    app.run(host="0.0.0.0", port=port, debug=True)
