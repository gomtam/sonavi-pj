import pyaudio
import numpy as np
import threading
import time
import librosa
from sklearn.metrics.pairwise import cosine_similarity

class AudioDetector:
    def __init__(self, door_sound_callback, threshold=0.7):
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        self.CHUNK = 4096
        self.door_sound_callback = door_sound_callback
        self.threshold = threshold
        self.running = False
        
        # 문 열림/닫힘 소리 샘플 로드
        # 실제 사용 시 문 소리 샘플 파일 필요
        self.door_open_features = []
        self.door_close_features = []
        
        # 샘플 파일 로드 (실제 구현 시 파일 경로 지정 필요)
        try:
            # self.load_door_sound_samples()
            pass  # 실제 구현 시 주석 해제
        except Exception as e:
            print(f"문 소리 샘플 로드 실패: {e}")
            print("기본 음성 감지 기능만 활성화됩니다.")

    def load_door_sound_samples(self):
        """문 소리 샘플 로드"""
        # 실제 사용 시 샘플 파일 경로 설정 필요
        door_open_path = 'samples/door_open.wav'
        door_close_path = 'samples/door_close.wav'
        
        # 샘플 파일에서 특성 추출
        self.door_open_features = self._extract_audio_features(door_open_path)
        self.door_close_features = self._extract_audio_features(door_close_path)

    def _extract_audio_features(self, file_path):
        """오디오 파일에서 특성 추출"""
        y, sr = librosa.load(file_path, sr=self.RATE)
        # MFCC 특성 추출
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        # 평균값 계산
        return np.mean(mfccs, axis=1)

    def start_monitoring(self):
        """소리 모니터링 시작"""
        if self.running:
            return
        
        self.running = True
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )
        
        print("음성 감지 시작...")
        
        # 소리 감지 루프
        try:
            self._monitoring_loop()
        except Exception as e:
            print(f"음성 감지 오류: {e}")
        finally:
            self.stop_monitoring()

    def _monitoring_loop(self):
        """소리 모니터링 루프"""
        cooldown = 0  # 반복 감지 방지용 쿨다운
        
        while self.running:
            if cooldown > 0:
                cooldown -= 1
                time.sleep(0.1)
                continue
                
            # 오디오 데이터 읽기
            data = self.stream.read(self.CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            
            # 소리 크기 확인 (기본 감지 방법)
            volume = np.abs(audio_data).mean()
            if volume > 1000:  # 소리 크기 임계값
                # 특성 추출
                features = self._extract_features_from_buffer(audio_data)
                
                # 문 열림/닫힘 소리 감지
                if len(self.door_open_features) > 0 and len(self.door_close_features) > 0:
                    # 열림 소리 유사도
                    open_similarity = cosine_similarity([features], [self.door_open_features])[0][0]
                    # 닫힘 소리 유사도
                    close_similarity = cosine_similarity([features], [self.door_close_features])[0][0]
                    
                    if open_similarity > self.threshold:
                        print(f"문 열림 소리 감지! (유사도: {open_similarity:.2f})")
                        self.door_sound_callback("open")
                        cooldown = 30  # 3초 쿨다운
                    elif close_similarity > self.threshold:
                        print(f"문 닫힘 소리 감지! (유사도: {close_similarity:.2f})")
                        self.door_sound_callback("close")
                        cooldown = 30  # 3초 쿨다운
                else:
                    # 샘플이 없는 경우 볼륨만으로 감지
                    print(f"큰 소리 감지! (볼륨: {volume})")
                    self.door_sound_callback("unknown")
                    cooldown = 30  # 3초 쿨다운
            
            time.sleep(0.1)

    def _extract_features_from_buffer(self, audio_data):
        """오디오 버퍼에서 특성 추출"""
        # 데이터 정규화
        audio_data = audio_data / 32768.0
        
        # MFCC 특성 추출
        mfccs = librosa.feature.mfcc(y=audio_data, sr=self.RATE, n_mfcc=13)
        
        # 평균값 계산
        return np.mean(mfccs, axis=1)

    def stop_monitoring(self):
        """소리 모니터링 중지"""
        self.running = False
        if hasattr(self, 'stream') and self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, 'audio') and self.audio:
            self.audio.terminate()
        print("음성 감지 중지") 