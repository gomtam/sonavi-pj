import os
import numpy as np
import pygame
import tempfile
from gtts import gTTS
import threading
from transformers import AutoProcessor, AutoModel

class TTSEngine:
    def __init__(self, custom_voice_dir='models/voice'):
        # 음성 출력을 위한 pygame 초기화
        pygame.mixer.init()
        
        # 커스텀 목소리 모델 디렉토리
        self.custom_voice_dir = custom_voice_dir
        os.makedirs(custom_voice_dir, exist_ok=True)
        
        # 기본 TTS 엔진 (gTTS)
        self.default_tts_engine = 'gtts'
        
        # 음성 변환용 모델 (HuBERT 또는 다른 음성 변환 모델)
        self.voice_conversion_model = None
        self.voice_processor = None
        self.custom_voice_embeddings = None
        
        # 사용자 정의 음성 모델 존재 여부 확인
        self.has_custom_voice = self._load_custom_voice()

    def _load_custom_voice(self):
        """사용자 정의 음성 모델 로드"""
        try:
            # HuBERT 모델 로드 (실제 구현 시 활성화)
            # self.voice_processor = AutoProcessor.from_pretrained("facebook/hubert-base-ls960")
            # self.voice_conversion_model = AutoModel.from_pretrained("facebook/hubert-base-ls960")
            
            # 사용자 목소리 임베딩 로드 (실제 구현 시 활성화)
            embedding_path = os.path.join(self.custom_voice_dir, 'voice_embedding.npy')
            if os.path.exists(embedding_path):
                self.custom_voice_embeddings = np.load(embedding_path)
                return True
            return False
        except Exception as e:
            print(f"커스텀 음성 모델 로드 실패: {e}")
            return False

    def speak(self, text, lang='ko'):
        """텍스트를 음성으로 변환하여 재생"""
        if not text:
            return False
        
        # 텍스트가 너무 길면 분할 처리
        if len(text) > 500:
            sentences = [s.strip() for s in text.split('.') if s.strip()]
            for sentence in sentences:
                self.speak(sentence, lang)
            return True
        
        try:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_filename = temp_file.name
            
            # gTTS로 음성 파일 생성
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(temp_filename)
            
            # 사용자 정의 음성이 있다면 변환 처리
            if self.has_custom_voice and self.voice_conversion_model:
                self._apply_voice_conversion(temp_filename)
            
            # 생성된 음성 파일 재생
            pygame.mixer.music.load(temp_filename)
            pygame.mixer.music.play()
            
            # 음성 재생이 끝날 때까지 대기
            while pygame.mixer.music.get_busy():
                pygame.time.delay(100)
            
            # 임시 파일 삭제
            os.unlink(temp_filename)
            return True
        except Exception as e:
            print(f"음성 변환 및 재생 실패: {e}")
            # 임시 파일 삭제 시도
            try:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
            except:
                pass
            return False

    def _apply_voice_conversion(self, audio_file):
        """음성 변환 적용 (사용자 목소리로 변환)"""
        # 음성 변환 모델 적용 코드
        # 실제 구현은 해당 모델의 API에 따라 달라질 수 있음
        print("사용자 음성으로 변환 중...")
        # 모델 적용 코드 (실제 구현 필요)
        pass

    def train_voice(self, voice_samples):
        """사용자 목소리 학습"""
        try:
            print("사용자 목소리 학습 시작...")
            
            # 샘플 저장 디렉토리
            samples_dir = os.path.join(self.custom_voice_dir, 'samples')
            os.makedirs(samples_dir, exist_ok=True)
            
            # 샘플 파일 저장
            file_paths = []
            for i, sample in enumerate(voice_samples):
                file_path = os.path.join(samples_dir, f'sample_{i}.wav')
                sample.save(file_path)
                file_paths.append(file_path)
            
            # 목소리 특성 추출 및 임베딩 생성
            self._extract_voice_features(file_paths)
            
            # 성공 여부 반환
            return self.has_custom_voice
        except Exception as e:
            print(f"목소리 학습 실패: {e}")
            return False

    def _extract_voice_features(self, file_paths):
        """음성 파일에서 목소리 특성 추출"""
        print("목소리 특성 추출 중...")
        
        # 실제 구현 시 적절한 음성 특성 추출 알고리즘 필요
        # 음성 데이터 로드 및 전처리
        # 임베딩 추출 및 저장
        
        # 예시 코드 (실제 구현 필요)
        embedding = np.random.rand(512)  # 임의의 임베딩 (예시)
        embedding_path = os.path.join(self.custom_voice_dir, 'voice_embedding.npy')
        np.save(embedding_path, embedding)
        
        # 모델 업데이트
        self.custom_voice_embeddings = embedding
        self.has_custom_voice = True
        
        print("목소리 특성 추출 완료")
        return True 