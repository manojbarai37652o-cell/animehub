// =========================================
// 🛑 SERVICE WORKER: IFRAME AD-BLOCKER
// =========================================

const AD_DOMAINS = [
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "popads.net",
    "propellerads.com",
    "adsterra.com",
    "exoclick.com",
    "hilltopads.net",
    "onclickads.net",
    "zr.pourrispodzols.com",
    "kq.modalclonism.com"
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    const url = event.request.url.toLowerCase();

    // चेक करो कि क्या रिक्वेस्ट किसी ऐड डोमेन पर जा रही है
    const isAd = AD_DOMAINS.some(domain => url.includes(domain));

    if (isAd) {
        // अगर ऐड है, तो उसे ब्लॉक करके खाली रिस्पॉन्स भेज दो
        console.log('🚫 Ad Blocked:', url);
        event.respondWith(
            new Response('', {
                status: 200,
                statusText: 'OK',
                headers: new Headers({ 'Content-Type': 'text/plain' })
            })
        );
    } else {
        // अगर ऐड नहीं है, तो सामान्य रूप से लोड होने दो
        event.respondWith(fetch(event.request));
    }
});