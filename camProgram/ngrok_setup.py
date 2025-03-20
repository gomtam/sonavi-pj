from pyngrok import ngrok, conf
import logging

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ngrok 인증 토큰 설정 (이 부분을 수정하세요)
NGROK_AUTH_TOKEN = "2uXP7dCg3XzJugznmHYGaen1WUO_5EyJXhEoh5vdmqkoi9fgz"  # 여기에 대시보드에서 복사한 토큰을 붙여넣으세요
# 예시: NGROK_AUTH_TOKEN = "2LcMjEMwQPj2aFh9B5qTEomnHBz_..."
# 대시보드의 'Your Authtoken' 페이지에서 'Copy' 버튼을 클릭하여 복사한 후 큰따옴표 안에 붙여넣으세요

def setup_ngrok():
    """ngrok 연결을 테스트합니다"""
    print("\n===== ngrok 설정 테스트 =====")
    try:
        # 토큰 설정
        if not NGROK_AUTH_TOKEN:
            print("오류: 인증 토큰이 비어 있습니다.")
            print("1. https://dashboard.ngrok.com/get-started/your-authtoken 에서 토큰 복사")
            print("2. 이 파일의 NGROK_AUTH_TOKEN 변수에 붙여넣기")
            print("3. 파일 저장 후 다시 실행")
            return
            
        # 토큰 설정
        conf.get_default().auth_token = NGROK_AUTH_TOKEN
        print(f"인증 토큰 설정 완료: {NGROK_AUTH_TOKEN[:5]}...")
        
        # 기존 터널 모두 닫기
        tunnels = ngrok.get_tunnels()
        for tunnel in tunnels:
            print(f"기존 터널 닫기: {tunnel.public_url}")
            ngrok.disconnect(tunnel.public_url)
        
        # 새 터널 생성
        port = 5000
        print(f"포트 {port}에 ngrok 터널 생성 중...")
        tunnel = ngrok.connect(port, "http")
        public_url = tunnel.public_url
        print(f"\n성공! ngrok 터널이 생성되었습니다.")
        print(f"터널 URL: {public_url}")
        print(f"이 URL로 외부에서 웹캠 서버에 접속할 수 있습니다.\n")
        
        # 사용 방법 안내
        print("웹캠 서버 사용 방법:")
        print("1. python camProgram\\webcam_fixed.py 실행")
        print("2. 외부에서 위 URL로 접속")
        print("3. 비밀번호 'admin'으로 로그인\n")
        
        # 서버 종료 방법
        print("웹캠 서버 종료 방법:")
        print("1. Ctrl+C로 터미널에서 서버 중지")
        print("2. 다시 이 스크립트를 실행하여 새 터널 생성\n")
        
        # 계속 유지
        input("아무 키나 누르면 ngrok 연결을 종료합니다...")
        
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        # 모든 터널 닫기
        for tunnel in ngrok.get_tunnels():
            ngrok.disconnect(tunnel.public_url)
        print("모든 ngrok 터널이 종료되었습니다.")

if __name__ == "__main__":
    setup_ngrok() 