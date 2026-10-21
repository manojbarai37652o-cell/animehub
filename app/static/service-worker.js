// =========================================
// 🛑 BRAVE STYLE SERVICE WORKER: IFRAME AD-BLOCKER
// =========================================

const AD_DOMAINS = [
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "popads.net",
    "propellerads.com",
    "exoclick.com",
    "hilltopads.net",
    "onclickads.net",
    "popcash.net",
    "adcash.com",
    "juicyads.com",
    "mgid.com",
    "taboola.com",
    "outbrain.com",
    "zr.pourrispodzols.com",
    "kq.modalclonism.com"
];

// 🛡️ WHITELIST: हमारी खुद की वेबसाइट के ऐड्स (इन्हें ब्लॉक नहीं करना है)
const WHITELIST_DOMAINS = [
    "bancadeltempoidea.org", // Adsterra Banner
    "nap5k.com",             // Monetag (अगर इस्तेमाल करो तो)
    "n6wxm.com"              // Monetag (अगर इस्तेमाल करो तो)
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    // सिर्फ GET रिक्वेस्ट चेक करें
    if (event.request.method !== 'GET') return;

    const url = event.request.url.toLowerCase();

    // चेक करो कि क्या रिक्वेस्ट किसी ऐड डोमेन पर जा रही है
    const isAd = AD_DOMAINS.some(domain => url.includes(domain));
    
    // चेक करो कि क्या ये हमारा खुद का व्हाइटलिस्टेड ऐड है
    const isWhitelisted = WHITELIST_DOMAINS.some(domain => url.includes(domain));

    if (isAd && !isWhitelisted) {
        // अगर ऐड है और हमारा नहीं है, तो उसे ब्लॉक करके खाली रिस्पॉन्स भेज दो
        console.log('🚫 Ad Blocked by AnimeNest Shield:', url);
        event.respondWith(
            new Response('', {
                status: 204, // No Content
                statusText: 'Blocked',
                headers: new Headers({ 'Content-Type': 'text/plain' })
            })
        );
    } else {
        // अगर ऐड नहीं है (या हमारा अपना है), तो सामान्य रूप से लोड होने दो
        event.respondWith(fetch(event.request));
    }
});