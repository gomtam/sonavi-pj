import cv2
import time
import sys
import os
import threading
import signal

def test_camera_initialization(camera_id, timeout=10, backend=None):
    """
    지정된 타임아웃 내에 카메라가 초기화되는지 테스트합니다.
    
    Args:
        camera_id: 테스트할 카메라 ID
        timeout: 초기화 타임아웃 (초)
        backend: 사용할 OpenCV 백엔드 (기본값: None = 자동 선택)
    
    Returns:
        (성공 여부, 오류 메시지 또는 None)
    """
    print(f"카메라 {camera_id} 초기화 테스트 중...")
    
    cap = None
    start_time = time.time()
    
    # 타임아웃 핸들러
    def timeout_handler():
        nonlocal cap
        if cap is not None:
            cap.release()
            cap = None
        return False, "카메라 초기화 시간 초과"
    
    # 타임아웃 타이머 설정
    timer = threading.Timer(timeout, timeout_handler)
    timer.daemon = True
    timer.start()
    
    try:
        # 백엔드 파라미터 처리
        if backend is not None:
            cap = cv2.VideoCapture(camera_id, backend)
        else:
            cap = cv2.VideoCapture(camera_id)
        
        if not cap.isOpened():
            return False, f"카메라 {camera_id}를 열 수 없습니다."
        
        # 프레임 읽기 시도
        frame_read_success = False
        frame_count = 0
        max_frames = 30  # 최대 30프레임 시도
        
        while frame_count < max_frames:
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                frame_read_success = True
                break
            
            frame_count += 1
            time.sleep(0.1)
            
            # 타임아웃 체크
            if time.time() - start_time > timeout:
                return False, "프레임 읽기 시간 초과"
        
        if not frame_read_success:
            return False, "유효한 프레임을 읽을 수 없습니다."
            
        # 카메라 정보 확인
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        print(f"카메라 {camera_id} 초기화 성공:")
        print(f"- 해상도: {width}x{height}")
        print(f"- FPS: {fps}")
        
        return True, None
        
    except Exception as e:
        return False, f"카메라 초기화 오류: {str(e)}"
    
    finally:
        timer.cancel()  # 타이머 취소
        if cap is not None:
            cap.release()

def find_best_camera():
    """
    가장 안정적인 카메라와 백엔드 조합을 찾습니다.
    
    여러 카메라 ID와 백엔드 조합을 테스트하여 가장 안정적인 조합을 반환합니다.
    
    Returns:
        (최적의 카메라 ID, 최적의 백엔드) 또는 실패 시 (None, None)
    """
    print("최적의 카메라 구성 탐색 중...")
    
    # Windows와 Linux에 따른 백엔드 목록
    if os.name == 'nt':  # Windows
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        backend_names = ["DirectShow", "Media Foundation", "기본값"]
    else:  # Linux/Mac
        backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
        backend_names = ["V4L2", "기본값"]
    
    best_camera = None
    best_backend = None
    
    # 최대 10개의 카메라 ID 테스트
    for camera_id in range(10):
        for idx, backend in enumerate(backends):
            backend_name = backend_names[idx]
            print(f"\n카메라 {camera_id}를 {backend_name} 백엔드로 테스트 중...")
            
            success, error = test_camera_initialization(camera_id, timeout=5, backend=backend)
            
            if success:
                best_camera = camera_id
                best_backend = backend
                print(f"카메라 ID {camera_id}와 {backend_name} 백엔드가 잘 작동합니다!")
                
                # 추가 안정성 테스트: 연속 3회 초기화 시도
                print("안정성 검증을 위한 추가 테스트 시작...")
                stability_score = 0
                
                for test in range(3):
                    print(f"안정성 테스트 {test+1}/3...")
                    success, _ = test_camera_initialization(camera_id, timeout=5, backend=backend)
                    if success:
                        stability_score += 1
                    time.sleep(1)  # 테스트 간 딜레이
                
                print(f"안정성 점수: {stability_score}/3")
                
                if stability_score >= 2:  # 3회 중 2회 이상 성공하면 충분히 안정적
                    return camera_id, backend
    
    # 완벽히 안정적인 조합을 찾지 못했지만 작동하는 조합이 있으면 반환
    if best_camera is not None:
        return best_camera, best_backend
    
    return None, None

def safe_camera_restart(camera_id, backend=None):
    """
    카메라를 안전하게 재시작합니다.
    
    Args:
        camera_id: 재시작할 카메라 ID
        backend: 사용할 OpenCV 백엔드
    
    Returns:
        성공 여부
    """
    print(f"카메라 {camera_id} 안전 재시작 중...")
    
    # 시그널 핸들러 설정 (타임아웃 관리용)
    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)
    
    # 재시작 타임아웃 설정
    restart_timeout = 10  # 10초
    restart_completed = threading.Event()
    restart_successful = [False]  # 리스트로 래핑하여 콜백에서 수정 가능하게 함
    
    def restart_timeout_handler():
        if not restart_completed.is_set():
            print("재시작 시간 초과. 프로그램을 정상 종료합니다.")
            # 원래 시그널 핸들러 복원
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)
            
            # 메인 스레드에게 종료 신호 보내기
            if os.name == 'nt':  # Windows
                # Windows에서는 KeyboardInterrupt를 발생시키기 위한 대안적 방법
                os.kill(os.getpid(), signal.CTRL_C_EVENT)
            else:
                os.kill(os.getpid(), signal.SIGINT)
    
    # 타임아웃 타이머 설정
    timer = threading.Timer(restart_timeout, restart_timeout_handler)
    timer.daemon = True
    timer.start()
    
    try:
        # 1. 카메라 초기화 테스트
        success, error = test_camera_initialization(camera_id, timeout=5, backend=backend)
        
        if not success:
            print(f"카메라 초기화 실패: {error}")
            return False
        
        # 2. 카메라 열기 및 간단한 작업 수행
        try:
            if backend is not None:
                cap = cv2.VideoCapture(camera_id, backend)
            else:
                cap = cv2.VideoCapture(camera_id)
                
            if not cap.isOpened():
                print(f"카메라 {camera_id}를 열 수 없습니다.")
                return False
            
            # 간단한 프레임 읽기 루프
            for _ in range(10):  # 10 프레임 읽기
                ret, frame = cap.read()
                if not ret:
                    print("프레임 읽기 실패")
                    return False
                time.sleep(0.1)
            
            # 3. 카메라 자원 안전하게 해제
            cap.release()
            cv2.destroyAllWindows()
            
            print(f"카메라 {camera_id} 재시작 성공!")
            restart_successful[0] = True
            return True
            
        except Exception as e:
            print(f"카메라 재시작 중 오류: {str(e)}")
            return False
            
        finally:
            if 'cap' in locals() and cap is not None:
                cap.release()
            cv2.destroyAllWindows()
    
    finally:
        restart_completed.set()
        timer.cancel()  # 타이머 취소
        
        # 원래 시그널 핸들러 복원
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGTERM, original_sigterm)
    
    return restart_successful[0]

def fix_camera_issues():
    """
    카메라 문제를 자동으로 진단하고 해결합니다.
    """
    print("=" * 50)
    print("카메라 문제 해결 도구")
    print("=" * 50)
    
    # 1. 최적의 카메라 구성 찾기
    print("\n1. 최적의 카메라 구성 찾는 중...")
    best_camera_id, best_backend = find_best_camera()
    
    if best_camera_id is None:
        print("\n사용 가능한 카메라를 찾을 수 없습니다.")
        print("다음 사항을 확인해주세요:")
        print("1. 카메라가 컴퓨터에 제대로 연결되어 있는지")
        print("2. 카메라 드라이버가 제대로 설치되어 있는지")
        print("3. 다른 프로그램에서 카메라를 사용하고 있지 않은지")
        return None, None
    
    # 백엔드 이름 출력
    backend_name = "DirectShow" if best_backend == cv2.CAP_DSHOW else \
                  "Media Foundation" if best_backend == cv2.CAP_MSMF else \
                  "V4L2" if best_backend == cv2.CAP_V4L2 else "기본값"
    
    print(f"\n최적의 카메라 구성을 찾았습니다:")
    print(f"- 카메라 ID: {best_camera_id}")
    print(f"- 백엔드: {backend_name}")
    
    # 2. 카메라 안전 재시작 테스트
    print("\n2. 카메라 안전 재시작 테스트...")
    restart_success = safe_camera_restart(best_camera_id, best_backend)
    
    if restart_success:
        print("\n카메라 재시작 테스트 성공!")
    else:
        print("\n카메라 재시작 테스트 실패.")
        print("카메라는 작동하지만 재시작 기능에 문제가 있을 수 있습니다.")
    
    print("\n권장 설정:")
    print(f"camera_id = {best_camera_id}")
    if best_backend is not None:
        print(f"backend = {best_backend} ({backend_name})")
    
    return best_camera_id, best_backend

if __name__ == "__main__":
    try:
        best_camera_id, best_backend = fix_camera_issues()
        
        if best_camera_id is not None:
            print("\n=" * 50)
            print("이 설정을 스마트홈 카메라 프로그램에 적용하시겠습니까? (y/n):", end=" ")
            choice = input().strip().lower()
            
            if choice == 'y':
                print("설정을 적용하는 방법:")
                print("1. SmartHomeCam 클래스 초기화 시 다음 인자를 전달하세요:")
                print(f"   camera_id={best_camera_id}")
                print("2. initialize_camera 메서드에서 다음 백엔드를 우선적으로 사용하세요:")
                backend_name = "DirectShow" if best_backend == cv2.CAP_DSHOW else \
                              "Media Foundation" if best_backend == cv2.CAP_MSMF else \
                              "V4L2" if best_backend == cv2.CAP_V4L2 else "기본값"
                print(f"   {backend_name} (코드: {best_backend})")
        
        print("\n=" * 50)
        print("프로그램 종료")
        
    except KeyboardInterrupt:
        print("\n\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n오류 발생: {str(e)}")
    finally:
        cv2.destroyAllWindows() 