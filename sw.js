/* 由 build.py 生成，请勿手改 · 版本 8fd3f91c1a */
const VER = '8fd3f91c1a';
const CACHE = 'cgq-' + VER;
const PRECACHE = ["./", "index.html", "questions.js?v=8fd3f91c1a", "assets/over-bottom.webp?v=8fd3f91c1a", "assets/over-c1-daoxiao.webp?v=8fd3f91c1a", "assets/over-c2-chenlun.webp?v=8fd3f91c1a", "assets/win-ascend.webp?v=8fd3f91c1a", "assets/win-c1-feisheng.webp?v=8fd3f91c1a", "assets/win-c2-wuwo.webp?v=8fd3f91c1a"];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if(req.method !== 'GET') return;
  const url = new URL(req.url);
  if(url.origin !== location.origin) return;

  /* 页面导航：网络优先（在线拿最新版），失败回退缓存（离线可玩） */
  if(req.mode === 'navigate' || req.destination === 'document'){
    e.respondWith(
      fetch(req).then(r => {
        if(r.ok){
          const cp = r.clone();
          caches.open(CACHE).then(c => { c.put(req, cp); c.put('./', r.clone()); });
        }
        return r;
      }).catch(() =>
        caches.match('./').then(m => m || caches.match(req) || caches.match('index.html'))
      )
    );
    return;
  }

  /* 其余静态资源：缓存优先，未命中才走网络并写入缓存 */
  e.respondWith(
    caches.match(req).then(m => m || fetch(req).then(r => {
      if(r.ok){
        const cp = r.clone();
        caches.open(CACHE).then(c => c.put(req, cp));
      }
      return r;
    }))
  );
});
