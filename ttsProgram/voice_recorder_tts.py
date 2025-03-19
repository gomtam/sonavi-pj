import os
import wave
import pyaudio
import pyttsx3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VoiceRecorderTTS:
    def __init__(self, root):
        self.root = root
        self.root.title("음성 녹음 및 TTS 프로그램")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # PyAudio 객체 초기화
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.recording_thread = None
        self.sample_rate = 44100
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paInt16
        
        # 사용 가능한 오디오 장치 목록
        self.audio_devices = self.get_audio_devices()
        
        # TTS 엔진 초기화
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 150)
            logger.info("TTS 엔진 초기화 성공")
        except Exception as e:
            logger.error(f"TTS 엔진 초기화 오류: {e}")
            messagebox.showerror("오류", f"TTS 엔진 초기화에 실패했습니다: {e}")
        
        # 녹음 파일 저장 디렉토리
        self.recordings_dir = "recordings"
        if not os.path.exists(self.recordings_dir):
            os.makedirs(self.recordings_dir)
            logger.info(f"녹음 디렉토리 생성: {self.recordings_dir}")
        
        # 저장된 녹음 파일 목록
        self.recordings = []
        
        # UI 구성
        self.setup_ui()
        
        # 녹음 목록 업데이트 (UI 구성 후 호출)
        self.update_recordings_list()
    
    def get_audio_devices(self):
        """사용 가능한 오디오 장치 목록을 반환합니다."""
        devices = []
        try:
            info = self.audio.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount')
            
            for i in range(num_devices):
                device_info = self.audio.get_device_info_by_host_api_device_index(0, i)
                device_name = device_info.get('name')
                max_input_channels = device_info.get('maxInputChannels')
                
                if max_input_channels > 0:  # 입력 장치인 경우
                    devices.append((i, device_name))
            
            logger.info(f"사용 가능한 오디오 입력 장치: {devices}")
            return devices
        except Exception as e:
            logger.error(f"오디오 장치 목록 조회 오류: {e}")
            return []
    
    def setup_ui(self):
        # 탭 구성
        self.tab_control = ttk.Notebook(self.root)
        
        # 녹음 탭
        self.recording_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.recording_tab, text="음성 녹음")
        
        # TTS 탭
        self.tts_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tts_tab, text="텍스트 음성 변환")
        
        # 녹음 목록 탭
        self.recordings_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.recordings_tab, text="녹음 목록")
        
        # 설정 탭 추가
        self.settings_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.settings_tab, text="설정")
        
        self.tab_control.pack(expand=1, fill="both")
        
        # 녹음 탭 구성
        self.setup_recording_tab()
        
        # TTS 탭 구성
        self.setup_tts_tab()
        
        # 녹음 목록 탭 구성
        self.setup_recordings_tab()
        
        # 설정 탭 구성
        self.setup_settings_tab()
    
    def setup_recording_tab(self):
        # 녹음 상태 표시
        self.recording_status = tk.Label(self.recording_tab, text="녹음 준비 완료", font=("Arial", 12))
        self.recording_status.pack(pady=10)
        
        # 녹음 시간 표시
        self.recording_time = tk.Label(self.recording_tab, text="00:00", font=("Arial", 36))
        self.recording_time.pack(pady=20)
        
        # 버튼 프레임
        btn_frame = tk.Frame(self.recording_tab)
        btn_frame.pack(pady=20)
        
        # 녹음 시작/중지 버튼
        self.record_btn = tk.Button(btn_frame, text="녹음 시작", command=self.toggle_recording, bg="#3498db", fg="white", font=("Arial", 12), padx=10, pady=5)
        self.record_btn.pack(side=tk.LEFT, padx=10)
        
        # 테스트 버튼 추가
        self.test_btn = tk.Button(btn_frame, text="마이크 테스트", command=self.test_microphone, bg="#2ecc71", fg="white", font=("Arial", 12), padx=10, pady=5)
        self.test_btn.pack(side=tk.LEFT, padx=10)
        
        # 녹음 파일 이름 입력
        name_frame = tk.Frame(self.recording_tab)
        name_frame.pack(pady=20)
        
        tk.Label(name_frame, text="녹음 파일 이름:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        self.file_name_entry = tk.Entry(name_frame, width=30)
        self.file_name_entry.pack(side=tk.LEFT, padx=5)
        self.file_name_entry.insert(0, f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # 오디오 레벨 표시
        level_frame = tk.Frame(self.recording_tab)
        level_frame.pack(pady=10, fill=tk.X, padx=50)
        
        tk.Label(level_frame, text="오디오 레벨:", font=("Arial", 10)).pack(anchor="w")
        self.level_bar = ttk.Progressbar(level_frame, orient="horizontal", length=500, mode="determinate")
        self.level_bar.pack(fill=tk.X, pady=5)
        
        # 디버그 정보 표시
        debug_frame = tk.Frame(self.recording_tab)
        debug_frame.pack(pady=10, fill=tk.X, padx=50)
        
        self.debug_info = tk.Text(debug_frame, height=5, width=60, font=("Consolas", 9))
        self.debug_info.pack(fill=tk.X)
        self.debug_info.config(state=tk.DISABLED)
    
    def setup_tts_tab(self):
        # TTS 입력 텍스트
        tk.Label(self.tts_tab, text="변환할 텍스트:", font=("Arial", 10)).pack(anchor="w", padx=10, pady=5)
        
        # 텍스트 입력 영역
        self.tts_text = tk.Text(self.tts_tab, height=10, width=60)
        self.tts_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        # 음성 설정 프레임
        settings_frame = tk.Frame(self.tts_tab)
        settings_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 음성 속도 설정
        tk.Label(settings_frame, text="음성 속도:").pack(side=tk.LEFT, padx=5)
        self.rate_var = tk.IntVar(value=150)
        rate_scale = tk.Scale(settings_frame, from_=50, to=300, orient=tk.HORIZONTAL, variable=self.rate_var, length=200)
        rate_scale.pack(side=tk.LEFT, padx=5)
        
        # 음성 변환 버튼
        self.speak_btn = tk.Button(self.tts_tab, text="텍스트 읽기", command=self.speak_text, bg="#3498db", fg="white", font=("Arial", 12), padx=10, pady=5)
        self.speak_btn.pack(pady=10)
    
    def setup_recordings_tab(self):
        # 녹음 목록 프레임
        list_frame = tk.Frame(self.recordings_tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 녹음 목록 스크롤바
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 녹음 목록 표시
        self.recordings_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Arial", 10), height=15)
        self.recordings_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.recordings_listbox.yview)
        
        # 녹음 파일 관리 버튼 프레임
        btn_frame = tk.Frame(self.recordings_tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 재생 버튼
        self.play_btn = tk.Button(btn_frame, text="재생", command=self.play_recording, bg="#2ecc71", fg="white", font=("Arial", 10), padx=10, pady=5)
        self.play_btn.pack(side=tk.LEFT, padx=5)
        
        # 삭제 버튼
        self.delete_btn = tk.Button(btn_frame, text="삭제", command=self.delete_recording, bg="#e74c3c", fg="white", font=("Arial", 10), padx=10, pady=5)
        self.delete_btn.pack(side=tk.LEFT, padx=5)
        
        # 새로고침 버튼
        self.refresh_btn = tk.Button(btn_frame, text="새로고침", command=self.update_recordings_list, bg="#3498db", fg="white", font=("Arial", 10), padx=10, pady=5)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
    
    def setup_settings_tab(self):
        """설정 탭 UI 구성"""
        # 오디오 장치 선택
        device_frame = tk.LabelFrame(self.settings_tab, text="오디오 입력 장치 선택", padx=10, pady=10)
        device_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 사용 가능한 장치 목록
        self.device_var = tk.StringVar()
        if self.audio_devices:
            self.device_var.set(f"{self.audio_devices[0][0]}: {self.audio_devices[0][1]}")
        
        for idx, (device_id, device_name) in enumerate(self.audio_devices):
            rb = tk.Radiobutton(device_frame, text=f"{device_id}: {device_name}", variable=self.device_var, value=f"{device_id}: {device_name}")
            rb.pack(anchor=tk.W, pady=2)
        
        # 장치 정보
        info_frame = tk.LabelFrame(self.settings_tab, text="시스템 정보", padx=10, pady=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # PyAudio 정보
        try:
            # PyAudio 버전 정보
            version_info = f"PyAudio 버전: {pyaudio.__version__}\n"
            # 기본 장치 정보 가져오기
            default_input = self.audio.get_default_input_device_info().get('name', '알 수 없음')
            default_output = self.audio.get_default_output_device_info().get('name', '알 수 없음')
            audio_info = f"{version_info}기본 입력 장치: {default_input}\n기본 출력 장치: {default_output}"
        except Exception as e:
            audio_info = f"시스템 정보를 가져올 수 없습니다: {e}"
            logger.error(f"시스템 정보 조회 오류: {e}")
        
        info_label = tk.Label(info_frame, text=audio_info, justify=tk.LEFT)
        info_label.pack(anchor=tk.W, pady=5)
        
        # 장치 목록 새로고침 버튼
        refresh_btn = tk.Button(info_frame, text="장치 목록 새로고침", command=self.refresh_audio_devices)
        refresh_btn.pack(anchor=tk.W, pady=5)
    
    def refresh_audio_devices(self):
        """오디오 장치 목록을 새로고침합니다."""
        self.audio_devices = self.get_audio_devices()
        # 설정 탭 다시 구성
        for widget in self.settings_tab.winfo_children():
            widget.destroy()
        self.setup_settings_tab()
        messagebox.showinfo("알림", "오디오 장치 목록이 새로고침되었습니다.")
    
    def get_selected_device_id(self):
        """선택된 오디오 장치 ID를 반환합니다."""
        if not self.audio_devices:
            return None
        
        try:
            selected = self.device_var.get()
            device_id = int(selected.split(':')[0])
            return device_id
        except Exception as e:
            logger.error(f"장치 ID 파싱 오류: {e}")
            # 기본 입력 장치 사용
            return None
    
    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def test_microphone(self):
        """마이크 테스트를 수행합니다."""
        if self.is_recording:
            messagebox.showwarning("경고", "녹음 중에는 마이크 테스트를 할 수 없습니다.")
            return
        
        self.update_debug_info("마이크 테스트 시작...")
        
        # 선택된 장치 ID 가져오기
        device_id = self.get_selected_device_id()
        
        try:
            test_stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=self.chunk_size
            )
            
            self.update_debug_info("마이크 연결 성공! 5초간 오디오 레벨을 측정합니다...")
            
            # 5초 동안 오디오 레벨 측정
            for i in range(50):  # 5초 (50 * 0.1초)
                if test_stream.is_active():
                    try:
                        data = test_stream.read(self.chunk_size)
                        level = self.get_audio_level(data)
                        self.level_bar['value'] = level
                        self.root.update()
                        time.sleep(0.1)
                    except Exception as e:
                        self.update_debug_info(f"데이터 읽기 오류: {e}")
                else:
                    self.update_debug_info("스트림이 활성화되지 않았습니다.")
                    break
            
            self.update_debug_info("마이크 테스트 완료!")
            test_stream.stop_stream()
            test_stream.close()
            
        except Exception as e:
            self.update_debug_info(f"마이크 테스트 오류: {e}")
            messagebox.showerror("오류", f"마이크 테스트 중 오류가 발생했습니다: {e}")
    
    def get_audio_level(self, data):
        """오디오 데이터의 레벨(볼륨)을 반환합니다."""
        try:
            # 부호 있는 16비트 정수로 변환
            import array
            import audioop
            
            # 오디오 데이터의 RMS(Root Mean Square) 값 계산
            rms = audioop.rms(data, 2)  # 2는 샘플당 바이트 수 (16비트 = 2바이트)
            
            # 로그 스케일로 변환 (0-100)
            level = min(100, max(0, int(20 * (rms / 32768))))
            return level
        except Exception as e:
            logger.error(f"오디오 레벨 계산 오류: {e}")
            return 0
    
    def update_debug_info(self, message):
        """디버그 정보를 업데이트합니다."""
        self.debug_info.config(state=tk.NORMAL)
        self.debug_info.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.debug_info.see(tk.END)
        self.debug_info.config(state=tk.DISABLED)
        logger.info(message)
    
    def start_recording(self):
        # 선택된 장치 ID 가져오기
        device_id = self.get_selected_device_id()
        
        try:
            self.is_recording = True
            self.frames = []
            self.record_btn.config(text="녹음 중지", bg="#e74c3c")
            self.recording_status.config(text="녹음 중...")
            
            self.update_debug_info("녹음 시작 중...")
            
            # 녹음 스레드 시작
            self.recording_thread = threading.Thread(target=self.record_audio, args=(device_id,))
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
            # 타이머 시작
            self.start_time = time.time()
            self.update_timer()
            
        except Exception as e:
            self.is_recording = False
            self.record_btn.config(text="녹음 시작", bg="#3498db")
            self.recording_status.config(text="녹음 오류")
            self.update_debug_info(f"녹음 시작 오류: {e}")
            messagebox.showerror("오류", f"녹음을 시작할 수 없습니다: {e}")
    
    def update_timer(self):
        if self.is_recording:
            elapsed = time.time() - self.start_time
            mins, secs = divmod(int(elapsed), 60)
            self.recording_time.config(text=f"{mins:02d}:{secs:02d}")
            self.root.after(1000, self.update_timer)
    
    def record_audio(self, device_id=None):
        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=self.chunk_size
            )
            
            self.update_debug_info(f"녹음 스트림 생성 성공 (장치 ID: {device_id if device_id is not None else '기본'})")
            
            silent_chunks = 0
            while self.is_recording:
                try:
                    data = self.stream.read(self.chunk_size)
                    self.frames.append(data)
                    
                    # 오디오 레벨 표시
                    level = self.get_audio_level(data)
                    self.level_bar['value'] = level
                    
                    # 무음 감지 (너무 오랫동안 무음이면 경고)
                    if level < 5:
                        silent_chunks += 1
                        if silent_chunks >= 50:  # 약 5초 동안 무음
                            self.update_debug_info("주의: 오디오 입력이 감지되지 않습니다. 마이크가 제대로 연결되어 있는지 확인하세요.")
                            silent_chunks = 0
                    else:
                        silent_chunks = 0
                    
                except Exception as e:
                    self.update_debug_info(f"녹음 중 오류: {e}")
                    break
            
        except Exception as e:
            self.update_debug_info(f"녹음 스트림 생성 오류: {e}")
            messagebox.showerror("오류", f"녹음 스트림을 생성할 수 없습니다: {e}")
            self.is_recording = False
            self.record_btn.config(text="녹음 시작", bg="#3498db")
            self.recording_status.config(text="녹음 준비 완료")
    
    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            self.record_btn.config(text="녹음 시작", bg="#3498db")
            self.recording_status.config(text="녹음 완료")
            
            self.update_debug_info("녹음 중지 중...")
            
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                    self.stream = None
                    self.update_debug_info("스트림 닫기 성공")
                except Exception as e:
                    self.update_debug_info(f"스트림 닫기 오류: {e}")
            
            # 녹음된 프레임이 있는지 확인
            if not self.frames:
                self.update_debug_info("녹음된 데이터가 없습니다!")
                messagebox.showwarning("경고", "녹음된 데이터가 없습니다. 마이크가 제대로 연결되어 있는지 확인하세요.")
                return
            
            # 녹음 파일 저장
            file_name = self.file_name_entry.get() or f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            file_path = os.path.join(self.recordings_dir, f"{file_name}.wav")
            
            try:
                with wave.open(file_path, 'wb') as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(self.audio.get_sample_size(self.format))
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(b''.join(self.frames))
                
                self.update_debug_info(f"녹음 파일 저장 성공: {file_path}")
                
                # 녹음 목록 업데이트
                self.update_recordings_list()
                
                # 파일 이름 리셋
                self.file_name_entry.delete(0, tk.END)
                self.file_name_entry.insert(0, f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                
            except Exception as e:
                self.update_debug_info(f"파일 저장 오류: {e}")
                messagebox.showerror("오류", f"녹음 파일을 저장할 수 없습니다: {e}")
    
    def speak_text(self):
        text = self.tts_text.get("1.0", tk.END).strip()
        if text:
            # 음성 속도 설정
            self.engine.setProperty('rate', self.rate_var.get())
            
            # 언어 설정 (한국어)
            korean_voice = None
            for voice in self.engine.getProperty('voices'):
                if 'korean' in voice.name.lower():
                    korean_voice = voice.id
                    break
            
            if korean_voice:
                self.engine.setProperty('voice', korean_voice)
                self.update_debug_info(f"한국어 음성 설정: {korean_voice}")
            else:
                self.update_debug_info("한국어 음성을 찾을 수 없습니다. 기본 음성을 사용합니다.")
            
            # 음성 합성 시작
            self.speak_btn.config(state=tk.DISABLED, text="읽는 중...")
            
            def speak():
                try:
                    self.engine.say(text)
                    self.engine.runAndWait()
                    self.update_debug_info("텍스트 읽기 완료")
                except Exception as e:
                    self.update_debug_info(f"텍스트 읽기 오류: {e}")
                finally:
                    self.root.after(0, lambda: self.speak_btn.config(state=tk.NORMAL, text="텍스트 읽기"))
            
            threading.Thread(target=speak).start()
        else:
            messagebox.showwarning("경고", "텍스트를 입력해주세요.")
    
    def update_recordings_list(self):
        self.recordings_listbox.delete(0, tk.END)
        self.recordings = []
        
        try:
            for file in os.listdir(self.recordings_dir):
                if file.endswith(".wav"):
                    self.recordings.append(file)
                    self.recordings_listbox.insert(tk.END, file)
            
            self.update_debug_info(f"녹음 목록 업데이트: {len(self.recordings)}개 파일 발견")
        except Exception as e:
            self.update_debug_info(f"녹음 목록 업데이트 오류: {e}")
    
    def play_recording(self):
        selection = self.recordings_listbox.curselection()
        if selection:
            file_name = self.recordings[selection[0]]
            file_path = os.path.join(self.recordings_dir, file_name)
            
            self.update_debug_info(f"녹음 파일 재생 중: {file_name}")
            
            # PyAudio를 사용하여 오디오 재생
            def play_audio():
                try:
                    wf = wave.open(file_path, 'rb')
                    stream = self.audio.open(
                        format=self.audio.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True
                    )
                    
                    data = wf.readframes(self.chunk_size)
                    while data:
                        stream.write(data)
                        data = wf.readframes(self.chunk_size)
                    
                    stream.stop_stream()
                    stream.close()
                    wf.close()
                    self.update_debug_info("녹음 파일 재생 완료")
                except Exception as e:
                    self.update_debug_info(f"녹음 파일 재생 오류: {e}")
            
            threading.Thread(target=play_audio).start()
        else:
            messagebox.showwarning("경고", "재생할 녹음 파일을 선택해주세요.")
    
    def delete_recording(self):
        selection = self.recordings_listbox.curselection()
        if selection:
            file_name = self.recordings[selection[0]]
            file_path = os.path.join(self.recordings_dir, file_name)
            
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self.update_recordings_list()
                    self.update_debug_info(f"녹음 파일 삭제: {file_name}")
                except Exception as e:
                    self.update_debug_info(f"녹음 파일 삭제 오류: {e}")
        else:
            messagebox.showwarning("경고", "삭제할 녹음 파일을 선택해주세요.")
    
    def on_closing(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        
        self.audio.terminate()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceRecorderTTS(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop() 