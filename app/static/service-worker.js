// =========================================
// 🛑 BRAVE STYLE SERVICE WORKER: HIGH-TECH STEALTH MODE
// =========================================

// ये सारे बड़े ऐड नेटवर्क्स हैं
const AD_DOMAINS = [
    "doubleclick.net", "googleadservices.com", "googlesyndication.com",
    "popads.net", "propellerads.com", "exoclick.com", "hilltopads.net",
    "onclickads.net", "popcash.net", "adcash.com", "juicyads.com",
    "mgid.com", "taboola.com", "outbrain.com", "adsterra.com",
    "profitablecpmrate.com", "adf.ly", "shorte.st", "clkmon.com"
];

const WHITELIST_DOMAINS = [
    "bancadeltempoidea.org", "nap5k.com", "n6wxm.com"
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    // 🛡️ 1. NAVIGATION TRAP (अंपायर को धोखा देने का तरीका)
    if (event.request.mode === 'navigate') {
        const url = new URL(event.request.url);
        
        // अगर रीडायरेक्ट हमारी वेबसाइट (animenest) से बाहर हो रहा है
        if (url.origin !== self.location.origin) {
            console.log('🛡️ Stealth Trap: Redirect intercepted to', url.href);
            
            // हम रीडायरेक्ट को रोक कर वापस उसी पेज पर भेज देंगे
            const safeUrl = event.request.referrer && event.request.referrer.startsWith(self.location.origin) 
                            ? event.request.referrer 
                            : self.location.origin;
            
            event.respondWith(Response.redirect(safeUrl, 302));
            return;
        }
    }

    // 🛡️ 2. AD SPOOFING (नकली ऐड भेजना ताकि उसे शक न हो)
    if (event.request.method !== 'GET') return;

    const url = event.request.url.toLowerCase();
    const isAd = AD_DOMAINS.some(domain => url.includes(domain));
    const isWhitelisted = WHITELIST_DOMAINS.some(domain => url.includes(domain));

    if (isAd && !isWhitelisted) {
        const fakeAdScript = `
            console.log("Ad Rendered Successfully");
            window.adBlockDetected = false; // अंपायर को लगेगा सब ठीक है
        `;
        event.respondWith(
            new Response(fakeAdScript, {
                status: 200,
                headers: new Headers({ 'Content-Type': 'application/javascript' })
            })
        );
    } else {
        event.respondWith(fetch(event.request));
    }
});