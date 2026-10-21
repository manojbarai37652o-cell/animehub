// =========================================
// 🛑 BRAVE STYLE SERVICE WORKER: AD SPOOFER & NAVIGATION TRAP
// =========================================

const AD_DOMAINS = [
    "doubleclick.net", "googleadservices.com", "googlesyndication.com",
    "popads.net", "propellerads.com", "exoclick.com", "hilltopads.net",
    "onclickads.net", "popcash.net", "adcash.com", "juicyads.com",
    "mgid.com", "taboola.com", "outbrain.com", "adsterra.com",
    "profitablecpmrate.com", "adf.ly", "shorte.st", "clkmon.com",
    "tsyndicate.com", "trafficjunky.com", "adnium.com"
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
    // 🛡️ 1. NAVIGATION TRAP (वेबसाइट बदलने से रोकने के लिए)
    if (event.request.mode === 'navigate') {
        const url = new URL(event.request.url);
        
        if (url.origin !== self.location.origin) {
            console.log('🛡️ Trap: Redirect intercepted to', url.href);
            const safeUrl = event.request.referrer && event.request.referrer.startsWith(self.location.origin) 
                            ? event.request.referrer 
                            : self.location.origin;
            
            event.respondWith(Response.redirect(safeUrl, 302));
            return;
        }
    }

    // 🛡️ 2. FAKE DETECTIVE (नकली जासूस भेजना ताकि सर्वर धोखा खाए)
    if (event.request.method !== 'GET') return;

    const url = event.request.url.toLowerCase();
    const isAd = AD_DOMAINS.some(domain => url.includes(domain));
    const isWhitelisted = WHITELIST_DOMAINS.some(domain => url.includes(domain));

    if (isAd && !isWhitelisted) {
        console.log('🛡️ Fake Detective Sent for:', url);
        
        const fakeAdScript = `
            console.log("Ad Rendered Successfully");
            window.adBlockDetected = false;
        `;
        
        event.respondWith(
            new Response(fakeAdScript, {
                status: 200, 
                headers: new Headers({ 
                    'Content-Type': 'application/javascript',
                    'Access-Control-Allow-Origin': '*' 
                })
            })
        );
    } else {
        event.respondWith(fetch(event.request));
    }
});