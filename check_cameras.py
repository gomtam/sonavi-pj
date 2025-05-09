import cv2
import time

def check_available_cameras(max_cameras=10):
    """사용 가능한 카메라를 확인합니다."""
    available_cameras = []
    
    print("카메라 검색을 시작합니다...")
    
    for i in range(max_cameras):
        print(f"\n카메라 {i} 확인 중...")
        cap = None
        try:
            # DirectShow 백엔드로 시도
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            
            if cap.isOpened():
                # 카메라 정보 확인
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                fps = cap.get(cv2.CAP_PROP_FPS)
                
                # 프레임 읽기 시도
                ret, frame = cap.read()
                if ret:
                    print(f"카메라 {i} 정보:")
                    print(f"- 해상도: {width}x{height}")
                    print(f"- FPS: {fps}")
                    print(f"- 프레임 읽기 성공")
                    
                    # 카메라 미리보기
                    print("카메라 미리보기 (5초 동안 표시됩니다)...")
                    start_time = time.time()
                    while time.time() - start_time < 5:
                        ret, frame = cap.read()
                        if ret:
                            cv2.imshow(f'Camera {i}', frame)
                            if cv2.waitKey(1) & 0xFF == ord('q'):
                                break
                    
                    available_cameras.append(i)
                else:
                    print(f"카메라 {i}에서 프레임을 읽을 수 없습니다.")
            else:
                print(f"카메라 {i}를 열 수 없습니다.")
                
        except Exception as e:
            print(f"카메라 {i} 확인 중 오류 발생: {e}")
            
        finally:
            if cap is not None:
                cap.release()
            cv2.destroyAllWindows()
    
    return available_cameras

if __name__ == "__main__":
    print("=" * 50)
    print("카메라 검색 프로그램")
    print("=" * 50)
    
    cameras = check_available_cameras()
    
    print("\n" + "=" * 50)
    if cameras:
        print(f"사용 가능한 카메라 ID: {cameras}")
        print("스마트 홈캠 프로그램에서 사용할 카메라 ID를 선택하세요.")
    else:
        print("사용 가능한 카메라가 없습니다.")
        print("다음 사항을 확인해주세요:")
        print("1. 카메라가 컴퓨터에 제대로 연결되어 있는지")
        print("2. 카메라 드라이버가 제대로 설치되어 있는지")
        print("3. 다른 프로그램에서 카메라를 사용하고 있지 않은지")
    
    print("=" * 50)
    input("\n프로그램을 종료하려면 Enter 키를 누르세요...") 