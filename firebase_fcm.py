import firebase_admin
from firebase_admin import credentials, messaging
import time
from datetime import datetime
import os
import json

class FirebaseFCM:
    def __init__(self):
        self.app = None
        self.last_notification_time = 0
        self.cooldown_minutes = 5
        self.device_tokens = set()  # 웹 브라우저 토큰들 저장
        self.tokens_file = "fcm_tokens.json"  # 토큰 저장 파일
        self.load_tokens()  # 저장된 토큰 로드
        self.initialize_firebase()
        
    def load_tokens(self):
        """저장된 토큰들을 파일에서 로드"""
        try:
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 데이터 구조가 올바른지 확인
                    if isinstance(data, dict) and 'all' in data:
                        # 'all' 키의 값이 리스트인지 확인
                        if isinstance(data['all'], list):
                            # 유효한 토큰만 필터링 (길이가 충분한 문자열)
                            valid_tokens = [token for token in data['all'] if isinstance(token, str) and len(token) > 50]
                            self.device_tokens = set(valid_tokens)
                            print(f"✅ 저장된 FCM 토큰 로드 완료: {len(valid_tokens)}개 토큰")
                        else:
                            print("⚠️ 토큰 데이터 형식 오류 - 새로 시작")
                            self.device_tokens = set()
                    else:
                        print("⚠️ 토큰 파일 형식 오류 - 새로 시작")
                        self.device_tokens = set()
                        
                    if self.device_tokens:
                        print(f"🔍 로드된 토큰 미리보기:")
                        for i, token in enumerate(list(self.device_tokens)[:3]):
                            print(f"   토큰 {i+1}: {token[:30]}...")
        except Exception as e:
            print(f"⚠️ 토큰 로드 중 오류 (새로 시작): {e}")
            self.device_tokens = set()
    
    def save_tokens(self):
        """토큰들을 파일에 저장"""
        try:
            # 기존 데이터 로드
            data = {}
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # 현재 토큰들을 'all' 키에 저장 (도메인 구분 나중에 추가 가능)
            data['all'] = list(self.device_tokens)
            data['last_updated'] = datetime.now().isoformat()
            
            with open(self.tokens_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 FCM 토큰 저장 완료: {len(self.device_tokens)}개 토큰")
            
        except Exception as e:
            print(f"❌ 토큰 저장 중 오류: {e}")
        
    def initialize_firebase(self):
        """Firebase Admin SDK 초기화"""
        try:
            # 서비스 계정 키 파일 경로
            service_account_path = "sonavi-home-cctv-bf6e3-firebase-adminsdk-fbsvc-b5de10f65b.json"
            
            if not os.path.exists(service_account_path):
                print(f"❌ Firebase 서비스 계정 키 파일을 찾을 수 없습니다: {service_account_path}")
                return False
            
            # Firebase Admin SDK 초기화 (이미 초기화되어 있지 않은 경우만)
            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account_path)
                self.app = firebase_admin.initialize_app(cred)
                print("✅ Firebase Admin SDK 초기화 완료")
            else:
                self.app = firebase_admin.get_app()
                print("✅ Firebase Admin SDK 이미 초기화됨")
            
            return True
            
        except Exception as e:
            print(f"❌ Firebase Admin SDK 초기화 실패: {e}")
            return False
        
    def add_device_token(self, token):
        """웹 브라우저에서 받은 FCM 토큰 추가"""
        # 토큰이 이미 존재하는지 확인
        is_new_token = token not in self.device_tokens
        
        self.device_tokens.add(token)
        
        if is_new_token:
            print(f"✅ 새 FCM 토큰 등록됨: {token[:30]}...")
            # 파일에 저장
            self.save_tokens()
        else:
            print(f"🔄 기존 FCM 토큰 확인됨: {token[:30]}...")
        
    def remove_device_token(self, token):
        """토큰 제거"""
        if token in self.device_tokens:
            self.device_tokens.discard(token)
            print(f"🗑️ 무효한 토큰 제거됨: {token[:30]}...")
            # 파일에서도 제거
            self.save_tokens()
            
    def get_token_info(self):
        """현재 토큰 정보 반환"""
        return {
            'total_tokens': len(self.device_tokens),
            'tokens_preview': [token[:30] + '...' for token in list(self.device_tokens)[:5]]
        }
    
    def can_send_notification(self):
        """쿨다운 체크 (5분)"""
        current_time = time.time()
        if current_time - self.last_notification_time >= (self.cooldown_minutes * 60):
            return True
        return False
    
    def send_notification(self, title, body, image_url=None, click_url=None):
        """FCM 푸시 알림 발송 (Firebase Admin SDK 사용)"""
        print(f"🔍 FCM 알림 발송 시작: {title}")
        
        if not self.app:
            print("⚠️ Firebase Admin SDK가 초기화되지 않았습니다.")
            return False
            
        if not self.device_tokens:
            print("⚠️ 등록된 디바이스 토큰이 없습니다.")
            print(f"현재 토큰 개수: {len(self.device_tokens)}")
            return False
            
        print(f"🔍 등록된 토큰 개수: {len(self.device_tokens)}")
        for i, token in enumerate(self.device_tokens):
            print(f"토큰 {i+1}: {token[:30]}...")
            
        if not self.can_send_notification():
            remaining = self.cooldown_minutes * 60 - (time.time() - self.last_notification_time)
            print(f"⏰ 쿨다운 중: {int(remaining)}초 후 알림 가능")
            return False
            
        success_count = 0
        
        # 등록된 모든 토큰에 알림 발송
        for token in list(self.device_tokens):
            try:
                print(f"🔍 토큰으로 메시지 전송 시도: {token[:30]}...")
                
                # FCM 메시지 구성
                notification = messaging.Notification(
                    title=title,
                    body=body,
                    image=image_url
                )
                
                # 웹 푸시 설정
                webpush_config = messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(
                        title=title,
                        body=body,
                        icon="/static/favicon.ico",
                        badge="/static/favicon.ico",
                        image=image_url,
                        tag="sonavi-detection"
                    ),
                    data={
                        "click_action": click_url or "https://sonavi.duckdns.org:5000",
                        "url": click_url or "https://sonavi.duckdns.org:5000",
                        "timestamp": str(int(time.time()))
                    },
                    fcm_options=messaging.WebpushFCMOptions(
                        link="https://sonavi.duckdns.org:5000"
                    )
                )
                
                # 메시지 생성
                message = messaging.Message(
                    notification=notification,
                    webpush=webpush_config,
                    token=token
                )
                
                print("🔍 Firebase Admin SDK로 메시지 전송 중...")
                
                # FCM API 호출 (Firebase Admin SDK)
                response = messaging.send(message)
                
                print(f"🔍 Firebase 응답: {response}")
                
                if response:
                    success_count += 1
                    print(f"✅ FCM 알림 발송 성공: {token[:20]}... (ID: {response})")
                else:
                    print(f"❌ FCM 알림 발송 실패: {token[:20]}...")
                    
            except messaging.UnregisteredError as e:
                print(f"❌ 등록되지 않은 토큰 제거: {token[:20]}... - {e}")
                self.remove_device_token(token)
            except messaging.SenderIdMismatchError as e:
                print(f"❌ 토큰 ID 불일치로 제거: {token[:20]}... - {e}")
                self.remove_device_token(token)
            except Exception as e:
                print(f"❌ FCM 발송 중 상세 오류: {type(e).__name__}: {e}")
                import traceback
                print(f"🔍 전체 오류 스택:")
                traceback.print_exc()
                
        if success_count > 0:
            self.last_notification_time = time.time()
            print(f"📱 FCM 알림 발송 완료: {success_count}개 디바이스")
            return True
        
        print(f"❌ FCM 알림 발송 실패: 성공한 디바이스 0개")
        return False
    
    def send_detection_alert(self, detected_objects, confidence, duckdns_url):
        """객체 감지 알림 발송"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 감지된 객체들을 문자열로 변환
        objects_str = ", ".join([f"{obj['name']}({obj['confidence']*100:.1f}%)" 
                                for obj in detected_objects])
        
        title = "🚨 SoNaVi 카메라 감지 알림"
        body = f"{current_time}\n감지된 객체: {objects_str}"
        
        return self.send_notification(
            title=title,
            body=body,
            click_url=duckdns_url
        )
    
    def test_notification(self, ignore_cooldown=True):
        """테스트 알림 발송"""
        if ignore_cooldown:
            # 테스트용: 쿨다운 무시
            original_time = self.last_notification_time
            self.last_notification_time = 0
            
            result = self.send_notification(
                title="🧪 SoNaVi 테스트 알림",
                body=f"테스트 시간: {datetime.now().strftime('%H:%M:%S')}",
                click_url="https://sonavi.duckdns.org:5000"
            )
            
            # 원래 시간 복원 (실제 감지 알림에는 쿨다운 유지)
            if not result:
                self.last_notification_time = original_time
                
            return result
        else:
            return self.send_notification(
                title="🧪 SoNaVi 테스트 알림",
                body=f"테스트 시간: {datetime.now().strftime('%H:%M:%S')}",
                click_url="https://sonavi.duckdns.org:5000"
            )

    def cleanup_tokens_except_local(self):
        """로컬 토큰을 제외한 모든 토큰 정리"""
        if not self.device_tokens:
            print("🔍 정리할 토큰이 없습니다.")
            return
            
        print(f"🧹 토큰 정리 시작 - 현재 {len(self.device_tokens)}개 토큰")
        
        # 로컬에서 접속하는 토큰들을 식별하기 위해 유효성 검사
        valid_tokens = set()
        invalid_tokens = set()
        
        for token in list(self.device_tokens):
            try:
                # Firebase의 dry_run 기능으로 토큰 유효성 검사
                message = messaging.Message(
                    notification=messaging.Notification(
                        title="토큰 유효성 검사",
                        body="이 메시지는 전송되지 않습니다."
                    ),
                    token=token
                )
                
                # dry_run=True로 실제 전송하지 않고 토큰만 검증
                response = messaging.send(message, dry_run=True)
                if response:
                    valid_tokens.add(token)
                    print(f"✅ 유효한 토큰: {token[:30]}...")
                
            except Exception as e:
                invalid_tokens.add(token)
                print(f"❌ 무효한 토큰 발견: {token[:30]}... - {e}")
        
        # 무효한 토큰들 제거
        self.device_tokens = valid_tokens
        
        print(f"🧹 토큰 정리 완료:")
        print(f"   - 유효한 토큰: {len(valid_tokens)}개")
        print(f"   - 제거된 토큰: {len(invalid_tokens)}개")
        
        # 결과 저장
        self.save_tokens()
        
    def startup_token_management(self):
        """프로그램 시작 시 토큰 관리"""
        print("🚀 프로그램 시작 - 토큰 관리 시작")
        
        # 1. 기존 토큰 정리 (로컬 토큰 제외하고 무효한 토큰들 정리)
        self.cleanup_tokens_except_local()
        
        # 2. Cloudflare 사용 시에만 새 토큰 자동 생성 대기 설정
        print("⏳ 새 토큰 등록 대기 중...")
        
    def shutdown_token_management(self):
        """프로그램 종료 시 토큰 관리 (Cloudflare 토큰만 정리)"""
        print("🛑 프로그램 종료 - Cloudflare 토큰 정리")
        
        # 현재는 토큰을 유지 (로컬 토큰은 계속 사용하고, 
        # Cloudflare 토큰은 다음 시작 시 자동으로 새로 생성됨)
        print("💾 로컬 토큰은 유지됩니다.")
        
    def limit_token_count(self, max_tokens=5):
        """토큰 개수 제한 (최대 5개로 제한)"""
        if len(self.device_tokens) > max_tokens:
            # 가장 오래된 토큰들을 제거 (리스트로 변환 후 처음 것들 제거)
            tokens_list = list(self.device_tokens)
            tokens_to_remove = tokens_list[:-max_tokens]  # 최신 max_tokens개만 유지
            
            for token in tokens_to_remove:
                self.device_tokens.discard(token)
                print(f"🗑️ 오래된 토큰 제거: {token[:30]}...")
            
            print(f"📊 토큰 개수 제한: {len(tokens_to_remove)}개 제거, {len(self.device_tokens)}개 유지")
            self.save_tokens() 