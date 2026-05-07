const CACHE_NAME = 'yeedem-books-v1';
const ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/logo.png',
  'https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700&display=swap',
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/htmx.org@1.9.10',
  'https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});
