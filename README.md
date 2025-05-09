# YOLOv5 스마트홈 카메라 시스템

이 프로젝트는 YOLOv5를 사용하여 실시간 객체 감지를 수행하는 스마트홈 카메라 시스템입니다.

## 주요 기능

- 실시간 객체 감지 (YOLOv5n 모델 사용)
- 웹 인터페이스를 통한 카메라 스트리밍
- 감지된 객체에 대한 실시간 알림
- 음성 알림 시스템 (TTS)
- 웹소켓을 통한 실시간 데이터 전송
- 외부 네트워크에서 원격 접속 지원

## 설치 방법

1. 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

2. json 파일 설정 방법:
- config.example.json을 config.json으로 복사
- auth_settings의 username과 password를 원하는 값으로 변경

3. YOLOv5 모델 다운로드:
- [YOLOv5n 모델](https://github.com/ultralytics/yolov5/releases/download/v6.1/yolov5n.pt)
- 다운로드한 파일을 `object_detection_yolov5` 폴더에 저장

## 실행 방법

```bash
python smart_home_cam_yolov5.py
```

실행 후 웹 브라우저에서 `http://localhost:5000`으로 접속하세요.

## 설정

`config.json` 파일에서 다음 설정을 변경할 수 있습니다:

- `notification_cooldown`: 알림 간격 (초)
- `confidence_threshold`: 객체 감지 신뢰도 임계값 (0.0 ~ 1.0)
- `special_objects`: 특별 감시 대상 객체 목록
- `tts_settings`: 음성 알림 설정
- `streaming_settings`: 스트리밍 서버 설정
- `auth_settings`: 인증 설정 (사용자 이름과 비밀번호)

## 외부 네트워크에서 접속하기

### 기본 인증 설정

외부 접속을 위해 기본적인 보안 인증이 구현되어 있습니다. 기본 인증 정보(예시)는 다음과 같습니다:
- 사용자 이름: admin
- 비밀번호: 0000

이 정보는 `config.json` 파일의 `auth_settings` 섹션에서 변경할 수 있습니다.

### 포트 포워딩 설정

1. **내부 IP 주소 확인**
   - 윈도우에서 명령 프롬프트를 열고 `ipconfig` 명령어 실행
   - Wi-Fi 또는 이더넷 어댑터의 IPv4 주소 확인

2. **공유기 관리 페이지 접속**
   - 웹 브라우저에서 공유기의 게이트웨이 주소로 접속 (일반적으로 192.168.0.1 또는 192.168.1.1)
   - 공유기 관리자 계정으로 로그인

3. **포트 포워딩 설정**
   - 포트 포워딩/가상 서버 설정 메뉴 찾기
   - 새 규칙 추가:
     - 내부 IP 주소: 위에서 확인한 IP 주소
     - 내부 포트: 5000
     - 외부 포트: 5000
     - 프로토콜: TCP 또는 TCP/UDP

### DDNS 설정 (동적 IP 주소 해결)

대부분의 가정용 인터넷은 IP 주소가 주기적으로 변경됩니다. DDNS 서비스를 사용하여 이 문제를 해결할 수 있습니다:

1. **DDNS 서비스 가입**
   - [No-IP](https://www.noip.com/), [DuckDNS](https://www.duckdns.org/), 또는 [Dynu](https://www.dynu.com/) 같은 서비스 이용
   - 계정 생성 및 고유한 도메인 이름 등록 (예: yourhome.ddns.net)

2. **DDNS 클라이언트 설정**
   - No-IP 제공 클라이언트 설치 (또는 공유기가 DDNS를 지원하는 경우 관리 페이지에서 설정)
   - 계정 정보 입력 및 설정 완료

3. **외부에서 접속**
   - 모바일 데이터나 다른 Wi-Fi 네트워크에서 웹 브라우저 열기
   - 등록한 DDNS 주소와 포트 번호로 접속 (예: `http://yourhome.ddns.net:5000`)
   - 인증 창이 나타나면 설정한 사용자 이름과 비밀번호 입력

### 예시 설정

본 프로젝트에서는 다음과 같은 설정을 통해 외부 접속을 구현했습니다:
- 포트 포워딩: 내부 IP의 5000번 포트를 외부 5000번 포트로 연결
- DDNS 서비스: No-IP 사용 (sonavi.ddns.net 도메인 설정)
- 접속 주소: sonavi.ddns.net:5000

### 보안 주의사항

1. **강력한 비밀번호 사용**: 기본 비밀번호를 변경하여 보안 강화
2. **정기적인 비밀번호 변경**: 주기적으로 인증 정보 업데이트
3. **불필요할 때는 포트 포워딩 비활성화**: 외부 접속이 필요하지 않을 때는 포트 포워딩 규칙 비활성화
4. **가능하면 HTTPS 설정**: 보안 강화를 위해 SSL/TLS 인증서 설치 고려

## 감지 가능한 객체

YOLOv5n 모델은 COCO 데이터셋 기반으로 80개의 객체를 감지할 수 있습니다:
- 사람 (person)
- 차량 (car, truck, bus)
- 동물 (dog, cat, bird 등)
- 가전제품 (tv, laptop, cell phone 등)
- 가구 (chair, couch, bed 등)
- 기타 다양한 객체

## 시스템 요구사항

- Python 3.7 이상
- 웹캠 또는 IP 카메라
- 인터넷 연결
- 최소 2GB RAM (YOLOv5n 모델 사용 시)
- CUDA 지원 GPU (선택사항, CPU에서도 동작 가능)

## 주의사항

1. 카메라 접근 권한이 필요합니다.
2. 처음 실행 시 YOLOv5 모델 다운로드가 필요할 수 있습니다.
3. GPU 사용 시 CUDA와 cuDNN이 설치되어 있어야 합니다.
4. YOLOv5n은 가장 가벼운 모델이지만, 정확도는 다른 모델보다 낮을 수 있습니다.
5. 외부 접속을 허용할 경우 보안에 주의하세요.

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

## 기여

버그 리포트나 기능 제안은 이슈 트래커를 이용해 주세요. 