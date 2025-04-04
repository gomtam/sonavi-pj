# 음성 인식 및 AI 응답 시스템

이 프로그램은 음성 인식, AI 응답 생성, 텍스트-음성 변환(TTS) 기능을 제공합니다.

## 주요 기능
1. 음성 녹음
   - 마이크를 통한 음성 입력
   - WAV 형식으로 녹음 파일 저장

2. 음성 인식
   - Google Speech Recognition API를 사용한 음성-텍스트 변환
   - 한국어 지원

3. AI 응답 생성
   - OpenAI GPT-3.5 API를 사용한 응답 생성
   - 자연스러운 대화 가능

4. 텍스트-음성 변환 (TTS)
   - pyttsx3를 사용한 음성 출력
   - 속도 및 볼륨 조절 가능

## 설치 방법
1. 필요한 패키지 설치:
   ```bash
   pip install -r requirements.txt
   ```

2. OpenAI API 키 설정:
   - 환경 변수에 OPENAI_API_KEY 설정
   ```bash
   # Windows
   set OPENAI_API_KEY=your_api_key_here
   
   # Linux/Mac
   export OPENAI_API_KEY=your_api_key_here
   ```

## 사용 방법
1. 프로그램 실행:
   ```bash
   python voice_assistant.py
   ```

2. 사용 순서:
   - 프로그램 실행 시 5초 동안 음성을 녹음합니다
   - 녹음된 음성이 텍스트로 변환됩니다
   - AI가 응답을 생성합니다
   - 생성된 응답이 음성으로 재생됩니다
   - 프로그램 종료는 Ctrl+C를 누르면 됩니다

## 주의사항
- 마이크가 정상적으로 연결되어 있어야 합니다
- 인터넷 연결이 필요합니다
- OpenAI API 사용에 따른 비용이 발생할 수 있습니다 