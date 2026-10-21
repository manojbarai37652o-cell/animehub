// =========================================
// 🛑 BRAVE STYLE SERVICE WORKER: AD SPOOFER & BLOCKER
// =========================================

// ये सारे बड़े ऐड नेटवर्क्स हैं जो वीडियो के अंदर ऐड दिखाते हैं
const AD_DOMAINS = [
    "doubleclick.net", "googleadservices.com", "googlesyndication.com",
    "popads.net", "propellerads.com", "exoclick.com", "hilltopads.net",
    "onclickads.net", "popcash.net", "adcash.com", "juicyads.com",
    "mgid.com", "taboola.com", "outbrain.com", "adsterra.com",
    "profitablecpmrate.com", "adf.ly", "shorte.st", "clkmon.com",
    "tsyndicate.com", "trafficjunky.com", "adnium.com"
];

// 🛡️ WHITELIST: हमारी खुद की वेबसाइट के ऐड्स (इन्हें ब्लॉक नहीं करना है)
const WHITELIST_DOMAINS = [
    "bancadeltempoidea.org", // Adsterra Banner
    "nap5k.com",             // Monetag
    "n6wxm.com"              // Monetag
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    const url = event.request.url.toLowerCase();
    const isAd = AD_DOMAINS.some(domain => url.includes(domain));
    const isWhitelisted = WHITELIST_DOMAINS.some(domain => url.includes(domain));

    if (isAd && !isWhitelisted) {
        // 🛠️ SPOOFING: ऐड को ब्लॉक करने के बजाय एक नकली खाली स्क्रिप्ट भेजो
        // इससे वीडियो सर्वर को लगेगा कि ऐड चल गया, लेकिन वो कुछ नहीं करेगा
        console.log('🛡️ Fake Ad Served to bypass Anti-Adblock:', url);
        
        const fakeAdScript = `
            // नकली ऐड स्क्रिप्ट (कुछ नहीं करती, बस वीडियो सर्वर को धोखा देती है)
            console.log("Ad Space Rendered Successfully");
            window.adBlockDetected = false;
        `;
        
        event.respondWith(
            new Response(fakeAdScript, {
                status: 200,
                headers: new Headers({ 'Content-Type': 'application/javascript' })
            })
        );
    } else {
        // बाकी सब कुछ सामान्य रूप से लोड होने दो
        event.respondWith(fetch(event.request));
    }
});