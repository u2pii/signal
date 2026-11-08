/* 今日信号 · Service Worker
   策略：同源请求一律「先网络，失败才用缓存」——保证信号永远是新的，
   断网时还能打开上一版页面。跨域行情接口完全不拦截。 */
const CACHE = "sig-shell-v1";
const SHELL = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/apple-touch-icon.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  let url;
  try { url = new URL(req.url); } catch (err) { return; }
  // 只接管本站静态文件，行情 API 直连
  if (url.origin !== location.origin) return;

  const isDoc = req.mode === "navigate";
  const cacheable = isDoc || (!url.search && /\.(?:html|json|js|png|svg|ico|webmanifest)$/i.test(url.pathname));

  e.respondWith(
    fetch(req)
      .then((res) => {
        if (cacheable && res && res.status === 200 && res.type === "basic") {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() =>
        caches.match(req, { ignoreSearch: isDoc }).then(
          (m) => m || (isDoc ? caches.match("./index.html") : undefined) ||
                 new Response("离线，且没有缓存", { status: 503, headers: { "Content-Type": "text/plain;charset=utf-8" } })
        )
      )
  );
});
