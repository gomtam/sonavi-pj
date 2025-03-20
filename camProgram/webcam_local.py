from flask import Flask, Response, render_template
import cv2
import socket

app = Flask(__name__)
camera = cv2.VideoCapture(0)

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
    # 간단한 HTML 페이지를 반환하여 웹캠 스트림을 표시
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
            }
            h1 {
                color: #333;
            }
            .video-container {
                margin-top: 20px;
            }
            img {
                max-width: 100%;
                height: auto;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <h1>웹캠 실시간 스트리밍</h1>
        <div class="video-container">
            <img src="/video_feed" alt="웹캠 스트림">
        </div>
    </body>
    </html>
    '''

@app.route('/video_feed')
def video_feed():
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
    print(f"같은 네트워크의 다른 기기에서 접속: http://{ip_address}:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=True) 