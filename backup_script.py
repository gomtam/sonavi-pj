import os
import shutil
import datetime
import time

def create_backup():
    """SoNaVi 스마트홈 카메라 프로그램 파일을 백업합니다 (Firebase FCM 포함)."""
    # 현재 디렉토리 경로
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 백업 디렉토리 경로
    backup_dir = os.path.join(current_dir, 'backups')
    
    # 백업 디렉토리가 없으면 생성
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        print(f"백업 디렉토리가 생성되었습니다: {backup_dir}")
    
    # 현재 시간을 백업 파일명에 포함
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_folder = os.path.join(backup_dir, f'backup_{timestamp}')
    
    # 백업할 파일 목록
    files_to_backup = [
        # 기본 설정 파일들
        'requirements.txt',
        'config.json',
        'config.example.json',
        
        # 메인 프로그램 파일들
        'smart_home_cam_yolov5.py',
        'camera_fix.py',
        'check_cameras.py',
        
        # Firebase 관련 파일들
        'firebase_fcm.py',
        'firebase_config.py',
        'sonavi-home-cctv-bf6e3-firebase-adminsdk-fbsvc-b5de10f65b.json',
        
        # 웹 템플릿 파일들
        'templates/index.html',
        'templates/goodbye.html',
        
        # 정적 파일들
        'static/firebase-messaging-sw.js',
        'static/favicon.ico',
        
        # 기타 중요 파일들
        '.gitignore',
        'README.md'
    ]
    
    try:
        # 백업 폴더 생성
        os.makedirs(backup_folder)
        
        # 파일 복사
        successful_backups = []
        missing_files = []
        
        for file in files_to_backup:
            source_path = os.path.join(current_dir, file)
            if os.path.exists(source_path):
                # 파일이 있는 디렉토리 구조 유지
                relative_path = os.path.dirname(file)
                if relative_path:
                    os.makedirs(os.path.join(backup_folder, relative_path), exist_ok=True)
                
                dest_path = os.path.join(backup_folder, file)
                shutil.copy2(source_path, dest_path)
                successful_backups.append(file)
                print(f"✅ 백업 완료: {file}")
            else:
                missing_files.append(file)
                print(f"⚠️  파일 없음: {file}")
        
        print(f"\n🎉 백업이 성공적으로 완료되었습니다!")
        print(f"📁 백업 위치: {backup_folder}")
        print(f"✅ 백업된 파일: {len(successful_backups)}개")
        if missing_files:
            print(f"⚠️  누락된 파일: {len(missing_files)}개")
        
        # 백업 파일 목록 표시
        print("\n백업된 파일 목록:")
        for root, _, files in os.walk(backup_folder):
            for file in files:
                print(f"- {os.path.join(root, file)}")
        
    except Exception as e:
        print(f"백업 중 오류 발생: {e}")
        # 오류 발생 시 백업 폴더 삭제
        if os.path.exists(backup_folder):
            shutil.rmtree(backup_folder)

def list_backups():
    """백업 목록을 표시합니다."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backup_dir = os.path.join(current_dir, 'backups')
    
    if not os.path.exists(backup_dir):
        print("백업이 존재하지 않습니다.")
        return
    
    backups = sorted([d for d in os.listdir(backup_dir) 
                     if os.path.isdir(os.path.join(backup_dir, d)) and d.startswith('backup_')],
                    reverse=True)
    
    if not backups:
        print("백업이 존재하지 않습니다.")
        return
    
    print("\n백업 목록:")
    for i, backup in enumerate(backups, 1):
        backup_path = os.path.join(backup_dir, backup)
        backup_time = os.path.getmtime(backup_path)
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(backup_time))
        print(f"{i}. {backup} ({time_str})")

if __name__ == "__main__":
    print("=" * 60)
    print("🏠 SoNaVi 스마트홈 카메라 백업 도구 (Firebase FCM 포함)")
    print("=" * 60)
    
    while True:
        print("\n1. 새 백업 생성")
        print("2. 백업 목록 보기")
        print("3. 종료")
        
        choice = input("\n선택하세요 (1-3): ")
        
        if choice == '1':
            create_backup()
        elif choice == '2':
            list_backups()
        elif choice == '3':
            print("프로그램을 종료합니다.")
            break
        else:
            print("잘못된 선택입니다. 다시 선택해주세요.") 