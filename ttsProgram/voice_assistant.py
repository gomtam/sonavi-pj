import speech_recognition as sr
import pyttsx3
import openai
import os
import time
from datetime import datetime
import wave
import pyaudio
import json

class VoiceAssistant:
    def __init__(self):
        # 음성 인식 초기화
        self.recognizer = sr.Recognizer()
        
        # TTS 엔진 초기화
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)  # 말하기 속도
        self.engine.setProperty('volume', 1.0)  # 볼륨
        
        # 녹음 설정
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        
        # OpenAI API 설정
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수를 설정해주세요.")
        openai.api_key = self.openai_api_key
        
        # 녹음 파일 저장 디렉토리
        self.recordings_dir = "recordings"
        if not os.path.exists(self.recordings_dir):
            os.makedirs(self.recordings_dir)

    def record_audio(self, duration=5):
        """음성을 녹음합니다."""
        p = pyaudio.PyAudio()
        stream = p.open(format=self.FORMAT,
                       channels=self.CHANNELS,
                       rate=self.RATE,
                       input=True,
                       frames_per_buffer=self.CHUNK)
        
        print(f"{duration}초 동안 녹음을 시작합니다...")
        frames = []
        
        for i in range(0, int(self.RATE / self.CHUNK * duration)):
            data = stream.read(self.CHUNK)
            frames.append(data)
        
        print("녹음이 완료되었습니다.")
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        return frames

    def save_audio(self, frames, filename=None):
        """녹음된 음성을 파일로 저장합니다."""
        if filename is None:
            filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        
        filepath = os.path.join(self.recordings_dir, filename)
        
        wf = wave.open(filepath, 'wb')
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(pyaudio.PyAudio().get_sample_size(self.FORMAT))
        wf.setframerate(self.RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        return filepath

    def speech_to_text(self, audio_file):
        """음성을 텍스트로 변환합니다."""
        with sr.AudioFile(audio_file) as source:
            audio = self.recognizer.record(source)
            try:
                text = self.recognizer.recognize_google(audio, language='ko-KR')
                print(f"인식된 텍스트: {text}")
                return text
            except sr.UnknownValueError:
                print("음성을 인식할 수 없습니다.")
                return None
            except sr.RequestError as e:
                print(f"Google Speech Recognition 서비스 오류: {e}")
                return None

    def get_ai_response(self, text):
        """OpenAI API를 사용하여 AI 응답을 생성합니다."""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 친절하고 도움이 되는 AI 어시스턴트입니다."},
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"AI 응답 생성 중 오류 발생: {e}")
            return "죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다."

    def text_to_speech(self, text):
        """텍스트를 음성으로 변환하여 재생합니다."""
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"TTS 변환 중 오류 발생: {e}")

    def run(self):
        """음성 어시스턴트를 실행합니다."""
        print("음성 어시스턴트가 시작되었습니다. (종료하려면 Ctrl+C를 누르세요)")
        
        while True:
            try:
                # 음성 녹음
                frames = self.record_audio()
                audio_file = self.save_audio(frames)
                
                # 음성을 텍스트로 변환
                text = self.speech_to_text(audio_file)
                if text:
                    # AI 응답 생성
                    response = self.get_ai_response(text)
                    print(f"AI 응답: {response}")
                    
                    # 응답을 음성으로 변환하여 재생
                    self.text_to_speech(response)
                
                time.sleep(1)  # 다음 녹음 전 잠시 대기
                
            except KeyboardInterrupt:
                print("\n프로그램을 종료합니다.")
                break
            except Exception as e:
                print(f"오류 발생: {e}")
                continue

if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.run() 