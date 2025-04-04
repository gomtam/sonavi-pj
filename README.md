# 음성 인식 및 웹캠 스트리밍 프로젝트

## 프로젝트 구조
```
.
├── camProgram/              # 웹캠 스트리밍 관련 파일
│   ├── webcam_fixed.py     # ngrok을 사용한 원격 웹캠 스트리밍 서버
│   └── ngrok_setup.py      # ngrok 설정 도구
│
└── ttsProgram/             # 음성 인식 및 TTS 관련 파일
    ├── voice_recorder_tts.py  # 음성 녹음 및 TTS 기능
    └── recordings/           # 녹음 파일 저장 디렉토리
```

## 기능
1. 원격 웹캠 스트리밍
   - ngrok을 사용한 외부 네트워크 접속 지원
   - 비밀번호 보안 기능
   - 실시간 웹캠 스트리밍

2. 음성 인식 및 TTS
   - 음성 녹음 기능
   - 음성을 텍스트로 변환
   - AI 응답 생성
   - TTS를 통한 음성 출력

## 사용 방법
1. 웹캠 스트리밍
   ```bash
   python camProgram/webcam_fixed.py
   ```

2. 음성 인식 및 TTS
   ```bash
   python ttsProgram/voice_recorder_tts.py
   ```

## 요구사항
- Python 3.8 이상
- 필요한 패키지는 각 디렉토리의 requirements.txt 참조