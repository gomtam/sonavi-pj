// 홈캠 메인 JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // 소켓 통신 초기화
    const socket = io();
    
    // 요소 참조
    const cameraFeed = document.getElementById('camera-feed');
    const captureBtn = document.getElementById('capture-btn');
    const notificationArea = document.getElementById('notification-area');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const captureGallery = document.getElementById('capture-gallery');
    const recordBtn = document.getElementById('record-btn');
    const recordingStatus = document.getElementById('recording-status');
    const recordingTime = document.getElementById('recording-time');
    const recordingsList = document.getElementById('recordings-list');
    const trainVoiceBtn = document.getElementById('train-voice-btn');
    
    // 카메라 컨트롤 버튼
    const upBtn = document.getElementById('up-btn');
    const downBtn = document.getElementById('down-btn');
    const leftBtn = document.getElementById('left-btn');
    const rightBtn = document.getElementById('right-btn');
    
    // 녹음 관련 변수
    let mediaRecorder = null;
    let audioChunks = [];
    let recordingInterval = null;
    let recordedAudios = [];
    
    // 소켓 이벤트 핸들러
    socket.on('connect', () => {
        addNotification('서버에 연결되었습니다.');
    });
    
    socket.on('disconnect', () => {
        addNotification('서버 연결이 끊겼습니다. 재연결 중...');
    });
    
    socket.on('notification', (data) => {
        addNotification(data.message);
    });
    
    // 카메라 제어 함수
    function controlCamera(direction) {
        fetch('/control_camera', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ direction: direction }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.status !== 'success') {
                addNotification(`카메라 제어 실패: ${data.message}`);
            }
        })
        .catch(error => {
            addNotification(`카메라 제어 요청 오류: ${error}`);
        });
    }
    
    // 카메라 컨트롤 버튼 이벤트 핸들러
    upBtn.addEventListener('click', () => controlCamera('up'));
    downBtn.addEventListener('click', () => controlCamera('down'));
    leftBtn.addEventListener('click', () => controlCamera('left'));
    rightBtn.addEventListener('click', () => controlCamera('right'));
    
    // 사진 촬영
    captureBtn.addEventListener('click', function() {
        fetch('/capture', {
            method: 'POST',
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                addNotification('사진이 촬영되었습니다.');
                addToGallery(data.path, data.filename);
            } else {
                addNotification(`사진 촬영 실패: ${data.message}`);
            }
        })
        .catch(error => {
            addNotification(`사진 촬영 요청 오류: ${error}`);
        });
    });
    
    // 갤러리에 이미지 추가
    function addToGallery(imagePath, filename) {
        // 갤러리에 '사진 없음' 메시지가 있으면 제거
        const noImagesMsg = captureGallery.querySelector('p.text-muted');
        if (noImagesMsg) {
            captureGallery.removeChild(noImagesMsg);
        }
        
        // 이미지 항목 생성
        const col = document.createElement('div');
        col.className = 'col-4 gallery-item';
        
        const img = document.createElement('img');
        img.src = imagePath;
        img.alt = filename;
        img.title = filename;
        img.addEventListener('click', () => {
            window.open(imagePath, '_blank');
        });
        
        col.appendChild(img);
        
        // 갤러리 시작 부분에 추가
        if (captureGallery.firstChild) {
            captureGallery.insertBefore(col, captureGallery.firstChild);
        } else {
            captureGallery.appendChild(col);
        }
        
        // 최대 9개 이미지만 표시
        const items = captureGallery.querySelectorAll('.gallery-item');
        if (items.length > 9) {
            captureGallery.removeChild(items[items.length - 1]);
        }
    }
    
    // 메시지 전송
    function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;
        
        // 사용자 메시지 표시
        addChatMessage(message, 'user');
        chatInput.value = '';
        
        // 서버에 메시지 전송
        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // 응답 메시지 표시
                addChatMessage(data.response, 'assistant');
            } else {
                addNotification(`채팅 오류: ${data.message}`);
            }
        })
        .catch(error => {
            addNotification(`채팅 요청 오류: ${error}`);
        });
    }
    
    // 채팅 메시지 추가
    function addChatMessage(text, role) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const p = document.createElement('p');
        p.textContent = text;
        
        messageDiv.appendChild(p);
        chatMessages.appendChild(messageDiv);
        
        // 스크롤을 최신 메시지로 이동
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // 알림 추가
    function addNotification(text) {
        const p = document.createElement('p');
        p.textContent = `${getCurrentTime()} ${text}`;
        
        notificationArea.appendChild(p);
        notificationArea.scrollTop = notificationArea.scrollHeight;
    }
    
    // 현재 시간 포맷
    function getCurrentTime() {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        return `[${hours}:${minutes}:${seconds}]`;
    }
    
    // 음성 녹음 시작
    recordBtn.addEventListener('click', function() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            // 녹음 중이면 중지
            stopRecording();
            return;
        }
        
        // 오디오 녹음 시작
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                audioChunks = [];
                mediaRecorder = new MediaRecorder(stream);
                
                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    
                    // 녹음된 오디오 추가
                    addRecordedAudio(audioUrl, audioBlob);
                    
                    // 녹음 상태 업데이트
                    recordingStatus.classList.add('d-none');
                    recordBtn.innerHTML = '<i class="fas fa-microphone"></i> 녹음 시작';
                    
                    // 트랙 중지
                    stream.getTracks().forEach(track => track.stop());
                };
                
                // 녹음 시작
                mediaRecorder.start();
                
                // UI 업데이트
                recordingTime.textContent = '0';
                recordingStatus.classList.remove('d-none');
                recordBtn.innerHTML = '<i class="fas fa-stop"></i> 녹음 중지';
                
                // 녹음 시간 업데이트
                let seconds = 0;
                recordingInterval = setInterval(() => {
                    seconds++;
                    recordingTime.textContent = seconds;
                    
                    // 최대 30초로 제한
                    if (seconds >= 30) {
                        stopRecording();
                    }
                }, 1000);
            })
            .catch(error => {
                addNotification(`마이크 접근 오류: ${error}`);
            });
    });
    
    // 녹음 중지
    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            clearInterval(recordingInterval);
        }
    }
    
    // 녹음된 오디오 추가
    function addRecordedAudio(audioUrl, audioBlob) {
        const recordingItem = document.createElement('div');
        recordingItem.className = 'recording-item';
        
        // 오디오 플레이어
        const audio = document.createElement('audio');
        audio.controls = true;
        audio.src = audioUrl;
        
        // 삭제 버튼
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn btn-sm btn-danger';
        deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
        deleteBtn.addEventListener('click', () => {
            recordingsList.removeChild(recordingItem);
            
            // recordedAudios 배열에서 제거
            const index = recordedAudios.findIndex(item => item.url === audioUrl);
            if (index !== -1) {
                recordedAudios.splice(index, 1);
            }
            
            // 녹음된 오디오가 없으면 학습 버튼 비활성화
            trainVoiceBtn.disabled = recordedAudios.length === 0;
        });
        
        recordingItem.appendChild(audio);
        recordingItem.appendChild(deleteBtn);
        recordingsList.appendChild(recordingItem);
        
        // 녹음된 오디오 저장
        recordedAudios.push({
            url: audioUrl,
            blob: audioBlob
        });
        
        // 녹음된 오디오가 있으면 학습 버튼 활성화
        trainVoiceBtn.disabled = false;
    }
    
    // 음성 학습 시작
    trainVoiceBtn.addEventListener('click', function() {
        if (recordedAudios.length === 0) {
            addNotification('학습할 음성 샘플이 없습니다.');
            return;
        }
        
        // FormData 생성
        const formData = new FormData();
        recordedAudios.forEach((audio, index) => {
            formData.append('samples', audio.blob, `sample_${index}.wav`);
        });
        
        // 서버에 음성 샘플 전송
        fetch('/train_voice', {
            method: 'POST',
            body: formData,
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                addNotification('음성 학습이 완료되었습니다.');
                // 모달 닫기
                bootstrap.Modal.getInstance(document.getElementById('voiceTrainingModal')).hide();
                // 녹음 목록 초기화
                recordingsList.innerHTML = '';
                recordedAudios = [];
                trainVoiceBtn.disabled = true;
            } else {
                addNotification(`음성 학습 실패: ${data.message}`);
            }
        })
        .catch(error => {
            addNotification(`음성 학습 요청 오류: ${error}`);
        });
    });
    
    // 채팅 입력 이벤트 핸들러
    sendBtn.addEventListener('click', sendMessage);
    
    chatInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });
    
    // 페이지 로드 시 초기 알림 추가
    addNotification('홈캠 시스템이 시작되었습니다.');
}); 