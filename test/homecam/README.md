# 홈캠 (HomeCam)

파이썬 기반의 스마트 홈 카메라 시스템

## 기능

- 웹 브라우저에서 실시간 카메라 스트리밍
- 카메라 각도 조정
- 사진 촬영 및 저장
- 음성 안내 기능
- 커스텀 음성 학습
- 문 열림/닫힘 소리 감지
- AI 챗봇 대화 기능

## 요구사항

- Python 3.7 이상
- 웹캠
- 마이크
- 스피커

## 설치 방법

1. 저장소 복제
```
git clone https://github.com/yourusername/homecam.git
cd homecam
```

2. 필요한 패키지 설치
```
pip install -r requirements.txt
```

3. 애플리케이션 실행
```
python app.py
```

4. 웹 브라우저에서 접속
```
http://localhost:5000
```

## 하드웨어 설정 (선택사항)

### 카메라 각도 조절을 위한 서보모터 연결 (라즈베리파이)

라즈베리파이를 사용하는 경우 서보모터를 이용하여 카메라 각도를 실제로 조절할 수 있습니다:

1. 서보모터를 라즈베리파이 GPIO에 연결
2. modules/camera.py 파일에서 _set_camera_position 메서드의 주석을 해제하고 코드 수정

## 디렉토리 구조

```
homecam/
├── app.py                 # 메인 애플리케이션 파일
├── requirements.txt       # 필요한 패키지 목록
├── static/                # 정적 파일 (CSS, JS, 이미지)
│   ├── css/               # CSS 파일
│   ├── js/                # JavaScript 파일
│   └── captures/          # 촬영된 이미지 저장 폴더
├── templates/             # 웹 템플릿 파일
│   └── index.html         # 메인 페이지 템플릿
└── modules/               # 기능별 모듈
    ├── __init__.py        
    ├── camera.py          # 카메라 제어 모듈
    ├── audio_detector.py  # 오디오 감지 모듈
    ├── tts_engine.py      # 음성 합성 모듈
    └── ai_chat.py         # AI 채팅 모듈
```

## 확장 가능성

- 얼굴 인식 통합
- 움직임 감지 알림
- 모바일 앱 연동
- 클라우드 저장소 연동
- 날씨 정보 제공
- 다국어 지원

## 라이센스

MIT License 