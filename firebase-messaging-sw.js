// Import scripts if needed (Firebase 8.x)
importScripts('https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/8.10.1/firebase-messaging.js');

// Initialize Firebase in the service worker
firebase.initializeApp({
  apiKey: "AIzaSyB6KdzZT0gl7XJMB-TO79ttgU5EgKF8Sqc",
  authDomain: "quakevision-f80bc.firebaseapp.com",
  projectId: "quakevision-f80bc",
  messagingSenderId: "1066517075530",
  appId: "1:1066517075530:web:7de5ef97e48d4a5fccf8b3",
});

// Retrieve an instance of Firebase Messaging
const messaging = firebase.messaging();

// Optional: handle background messages
messaging.onBackgroundMessage(function(payload) {
  console.log('[firebase-messaging-sw.js] Received background message ', payload);
  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/firebase-logo.png' // optional
  };
  self.registration.showNotification(notificationTitle, notificationOptions);
});
