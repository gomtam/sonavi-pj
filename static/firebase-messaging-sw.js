// Firebase Messaging Service Worker

// Firebase SDK import
importScripts('https://www.gstatic.com/firebasejs/9.15.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.15.0/firebase-messaging-compat.js');

// Firebase 설정
const firebaseConfig = {
    apiKey: "AIzaSyBoSjqjyHo6Yr-IHHuslSJ_AGVZG3QXJdU",
    authDomain: "sonavi-home-cctv-bf6e3.firebaseapp.com", 
    projectId: "sonavi-home-cctv-bf6e3",
    storageBucket: "sonavi-home-cctv-bf6e3.firebasestorage.app",
    messagingSenderId: "568007893096",
    appId: "1:568007893096:web:8b7ddfde89fe4cc6b8ede8"
};

// Firebase 초기화
firebase.initializeApp(firebaseConfig);

// Firebase Messaging 인스턴스 생성
const messaging = firebase.messaging();

// 백그라운드 메시지 처리
messaging.onBackgroundMessage((payload) => {
    console.log('📨 백그라운드 메시지 수신:', payload);
    
    const notificationTitle = payload.notification?.title || '🏠 SoNaVi 스마트홈';
    const notificationOptions = {
        body: payload.notification?.body || '새로운 알림이 있습니다.',
        icon: '/static/icon-192x192.png',
        badge: '/static/icon-192x192.png',
        tag: 'sonavi-notification',
        data: payload.data,
        actions: [
            {
                action: 'view',
                title: '확인하기'
            },
            {
                action: 'dismiss',
                title: '닫기'
            }
        ],
        requireInteraction: true,
        silent: false
    };
    
    // 알림 표시
    self.registration.showNotification(notificationTitle, notificationOptions);
});

// 알림 클릭 처리
self.addEventListener('notificationclick', (event) => {
    console.log('🔔 알림 클릭됨:', event);
    
    event.notification.close();
    
    if (event.action === 'view' || event.action === '') {
        // 메인 페이지로 이동
        event.waitUntil(
            clients.matchAll({ type: 'window' }).then((clientList) => {
                // 이미 열린 탭이 있으면 포커스
                for (const client of clientList) {
                    if (client.url.includes(location.origin) && 'focus' in client) {
                        return client.focus();
                    }
                }
                // 없으면 새 탭 열기
                if (clients.openWindow) {
                    return clients.openWindow('/');
                }
            })
        );
    }
});

// 알림 닫기 처리
self.addEventListener('notificationclose', (event) => {
    console.log('🚫 알림 닫힘:', event);
});

console.log('✅ Firebase Messaging Service Worker 로드 완료'); 