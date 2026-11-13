// Runs on X, Instagram and TikTok. Remembers what was right-clicked and reads the surrounding post. Selectors are best-effort: these sites change their HTML often.
let last = { target: null, x: 0, y: 0 };

let cached = null;

// Read the post at the moment of the right-click. X swaps image elements on hover, so by the time the menu item is clicked the target can be gone.
document.addEventListener(
  "contextmenu",
  (e) => {
    last = { target: e.target, x: e.clientX, y: e.clientY };
    try { cached = capture(); } catch (err) { cached = { found: false, error: String(err) }; }
  },
  true
);

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== "smcrd-capture") return;
  sendResponse(cached || { found: false });
});

function capture() {
  let el = last.target;
  if (el && !el.isConnected) el = document.elementFromPoint(last.x, last.y);
  if (!el) return { found: false };
  const host = location.hostname;
  const isX = host.endsWith("x.com") || host.endsWith("twitter.com");
  const isInstagram = host.endsWith("instagram.com");

  let mediaEl = mediaAtClick(el, isX);
  let post;
  if (isX) {
    post = extractX(el);
    // Clicked the text next to the photo: take the media of the same post / photo viewer.
    if (!mediaEl) mediaEl = xMediaForPost(el);
  } else if (isInstagram) {
    // Reels: several reels are stacked on the same spot; the one playing is the one shown.
    if (/^\/reels?\//.test(location.pathname)) mediaEl = mostVisibleVideo() || mediaEl;
    post = extractInstagram(el, mediaEl);
  } else if (host.endsWith("tiktok.com")) post = extractTikTok(el);
  else return { found: false };

  const media = mediaInfo(mediaEl);
  const { platform, ...fields } = post;
  const postFound = Object.values(fields).some((v) => v);
  // follows the week 1 instructions now :)
  return {
    found: postFound || !!media.media_url,
    data: {
      platform,
      media_url: media.media_url,
      media_type: media.media_kind,
      video_poster: media.video_poster,
      media_alt: media.media_alt,
      post_caption: post.caption ?? null,
      post_author: post.author_handle || post.author_name || null,
      post_author_name: post.author_name ?? null,
      post_date: post.timestamp ?? null,
      post_date_source: post.timestamp_source ?? null,
      post_url: post.post_url ?? null,
      capture_error: postFound ? null : "Media found, but no post details around it.",
    },
  };
}

// media under the cursor (works through overlay layers)
function mediaAtClick(el, allowBoxSearch) {
  for (const node of document.elementsFromPoint(last.x, last.y)) {
    if (node.tagName === "IMG" || node.tagName === "VIDEO") return node;
  }
  // Box search only on X: on Instagram it picked up hidden pre-loaded reels next to the visible one.
  if (!allowBoxSearch) return el.closest?.("img, video") || null;
  // X videos: the player sets pointer-events:none on the <video>, so the loop above, never sees it. Fall back to the img/video whose box contains the click point.
  let best = null;
  let bestArea = Infinity;
  for (const m of document.querySelectorAll("video, img")) {
    const r = m.getBoundingClientRect();
    if (r.width < 50 || r.height < 50) continue; // skip avatars and icons
    if (last.x < r.left || last.x > r.right || last.y < r.top || last.y > r.bottom) continue;
    const area = r.width * r.height;
    if (area < bestArea || (area === bestArea && m.tagName === "VIDEO")) {
      best = m;
      bestArea = area;
    }
  }
  return best || el.closest?.("img, video") || null;
}

function mediaInfo(m) {
  if (!m) return { media_url: null, media_kind: null, video_poster: null, media_alt: null };
  // Alt text. Instagram generates it automatically and often includes the text written on the image ("May be an image of text that says ..."). X's default "Image" is skipped.
  const altRaw = (m.getAttribute("alt") || m.getAttribute("aria-label") || "").trim();
  const alt = altRaw && altRaw !== "Image" && altRaw !== "Embedded video" ? altRaw : null;
  if (m.tagName === "VIDEO") {
    return {
      media_url: m.currentSrc || m.src || m.querySelector("source")?.src || null,
      media_kind: "video",
      video_poster: m.poster || null,
      media_alt: alt,
    };
  }
  return { media_url: m.currentSrc || m.src || null, media_kind: "image", video_poster: null, media_alt: alt };
}

function text(node) {
  const t = node?.innerText?.trim();
  return t ? t : null;
}

// Specifically for X
function extractX(el) {
  const article = xArticle(el);
  if (!article) return { platform: "x" };
  const userLines = (article.querySelector('[data-testid="User-Name"]')?.innerText || "")
    .split("\n").map((s) => s.trim()).filter(Boolean);
  const timeEl = article.querySelector("time[datetime]");
  return {
    platform: "x",
    caption: text(article.querySelector('[data-testid="tweetText"]')),
    author_name: userLines.find((s) => !s.startsWith("@") && s !== "·") || null,
    author_handle: userLines.find((s) => s.startsWith("@")) || null,
    timestamp: timeEl?.getAttribute("datetime") || null,
    timestamp_source: timeEl ? "page" : null,
    post_url: timeEl?.closest("a")?.href || null,
  };
}

// The post around the clicked element. In the photo viewer (/status/<id>/photo/1) the photo is outside the post, so find the post by the status ID in the URL instead.
function xArticle(el) {
  const direct = el.closest('article[data-testid="tweet"]') || el.closest("article");
  if (direct) return direct;
  const id = location.pathname.match(/\/status\/(\d+)/)?.[1];
  if (!id) return null;
  return [...document.querySelectorAll('article[data-testid="tweet"]')]
    .find((a) => a.querySelector(`a[href*="/status/${id}"] time`)) || null;
}

// Media of the post when the click was on its text: first inside the post itself, then in the open photo viewer (the largest pbs.twimg.com/media image on the page).
function xMediaForPost(el) {
  const article = xArticle(el);
  const inPost = article?.querySelector('[data-testid="tweetPhoto"] img, video');
  if (inPost) return inPost;
  if (!/\/(photo|video)\/\d+/.test(location.pathname)) return null;
  let best = null;
  let bestArea = 0;
  for (const m of document.querySelectorAll('img[src*="pbs.twimg.com/media"], video')) {
    const r = m.getBoundingClientRect();
    if (r.width * r.height > bestArea) {
      best = m;
      bestArea = r.width * r.height;
    }
  }
  return best;
}

// Specifically for Insta

// Three layouts: feed (<article>), post page/modal (caption shown as first comment), reels viewer (no <time>, author and caption on top of the video).
function extractInstagram(el, mediaEl) {
  const root = el.closest("article") || el.closest('[role="dialog"]') || document;
  const isPostPage = /\/(p|reel|reels)\//.test(location.pathname);
  // Reel viewer (also when opened from the home feed): a video that is not part of a feed post.
  // Its author and caption sit on top of the video. Everything else on the page belongs to
  // other posts, so page-wide <time>, header, h1 and post links must not be used.
  // THIS IS THE FIX FOR REELS 
  const reelViewer =
    mediaEl?.tagName === "VIDEO" && !mediaEl.closest("article") && !el.closest("article");
  const timeEl = reelViewer ? null : root.querySelector("time[datetime]");
  const rawPostUrl =
    el.closest('a[href*="/p/"], a[href*="/reel/"]')?.href || // a tile in the explore/profile grid
    timeEl?.closest("a")?.href ||
    (root === document && isPostPage ? location.href : null) ||
    (reelViewer ? null : root.querySelector('a[href*="/p/"], a[href*="/reel/"]')?.href) ||
    (isPostPage ? location.href : null);
  // Keep only /p/<code>/ or /reel/<code>/ — drops extras like /liked_by/ or ?img_index=1
  const code = rawPostUrl?.match(/\/(p|reel|reels)\/([^/?#]+)/);
  const postUrl = code
    ? `https://www.instagram.com/${code[1] === "reels" ? "reel" : code[1]}/${code[2]}/`
    : null;

  const authorLink = reelViewer ? null : root.querySelector('header a[href^="/"]');
  let handle = authorLink?.getAttribute("href")?.replace(/\//g, "") || null;

  // Post page: caption is in an h1. Feed: take the longest text span in the post.
  let caption = reelViewer ? null : text(root.querySelector("h1"));
  if (!caption && root !== document && !reelViewer) {
    let best = "";
    for (const s of root.querySelectorAll('span[dir="auto"]')) {
      const t = s.innerText?.trim() || "";
      if (t.length > best.length && t !== handle) best = t;
    }
    caption = best || null;
  }

  // Reels: author and caption are drawn on top of the video. Only what is visibly on top of the current video counts (other reels are pre-loaded underneath it).
    if ((!handle || !caption) && mediaEl && (reelViewer || /^\/reels?\//.test(location.pathname))) {
    const over = overlayOnMedia(mediaEl);
    handle = handle || over.handle;
    caption = caption || over.caption;
  }

  // Post page / modal: walk up from the caption's <time> or the clicked element.
  // Not on the reels feed: there it ends up in a neighbouring reel.
    if ((!handle || !caption) && !reelViewer && !location.pathname.startsWith("/reels/")) {
    const near = postBlockAround(timeEl || el);
    handle = handle || near.handle;
    caption = caption || near.caption;
  }

  // Reels show no date, but the shortcode in the URL contains the upload time.
  let timestamp = timeEl?.getAttribute("datetime") || null;
  let timestampSource = timestamp ? "page" : null;
  if (!timestamp && code) {
    timestamp = timeFromShortcode(code[2]);
    timestampSource = timestamp ? "shortcode" : null;
  }

  return {
    platform: "instagram",
    caption: caption ? caption.replace(/\s*(…|\.\.\.)\s*more$/i, " …") : null,
    author_name: null,
    author_handle: handle ? "@" + handle : null,
    timestamp,
    timestamp_source: timestampSource,
    post_url: postUrl,
  };
}

// Walks up from a starting element until it finds one author link and the caption text.
// Stops as soon as a second user link appears: that means it reached comments or other posts.
function postBlockAround(startEl) {
  const userHref = (a) => {
    const h = a.getAttribute("href") || "";
    return /^\/[A-Za-z0-9._]+\/$/.test(h) && !/^\/(explore|reels|direct|accounts|notifications|stories)\/$/.test(h)
      ? h.replace(/\//g, "")
      : null;
  };
  const noise = /^(Edited|•|·|Follow|Following|more|… more|\.\.\. more|Original audio|Verified)$/i;
  const isNoise = (t, h) => !t || t === h || noise.test(t) || /^\d+[smhdw]$/.test(t);

  let handle = null;
  let caption = null;
  for (let node = startEl, i = 0; node && i < 15; node = node.parentElement, i++) {
    if (node === document.body || node === document.documentElement) break;
    const users = new Set([...node.querySelectorAll("a[href]")].map(userHref).filter(Boolean));
    if (users.size > 1) break;
    // Also stop when this part of the page links to more than one post (a grid of posts).
    const posts = new Set(
      [...node.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]')]
        .map((a) => a.getAttribute("href").match(/\/(?:p|reel)\/([^/?#]+)/)?.[1])
        .filter(Boolean)
    );
    if (posts.size > 1) break;
    if (!handle && users.size === 1) handle = [...users][0];
    if (!handle) continue;
    let best = "";
    for (const s of node.querySelectorAll('span[dir="auto"], h1')) {
      const t = s.innerText?.trim() || "";
      if (!isNoise(t, handle) && !t.startsWith(handle + " ") && t.length > best.length) best = t;
    }
    if (best) caption = best;
  }
  return { handle, caption };
}

// Reels: finds the author link and caption text that sit on top of the video on screen.
function overlayOnMedia(mediaEl) {
  const box = mediaEl.getBoundingClientRect();
  // Inside the video's box AND actually visible on top: hit-test the element's centre.
  // Pre-loaded reels sit underneath the current one and fail this test.
  const inside = (n) => {
    const r = n.getBoundingClientRect();
    if (!(r.width > 0 && r.height > 0 &&
      r.left >= box.left - 5 && r.right <= box.right + 5 &&
      r.top >= box.top - 5 && r.bottom <= box.bottom + 5)) return false;
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return !!hit && (hit === n || n.contains(hit));
  };

  let handle = null;
  for (const a of document.querySelectorAll("a[href]")) {
    const m = (a.getAttribute("href") || "").match(/^\/([A-Za-z0-9._]+)\/?(\?.*)?$/);
    if (!m || /^(explore|reels|reel|p|direct|accounts|stories|notifications)$/.test(m[1])) continue;
    // The name or the avatar: on reels Instagram often links only the avatar picture.
    if (inside(a)) { handle = m[1]; break; }
  }
  // Last resort: the avatar's alt text, "<handle>'s profile picture".
  if (!handle) {
    for (const img of document.querySelectorAll('img[alt$="profile picture"]')) {
      const m = (img.getAttribute("alt") || "").match(/^([A-Za-z0-9._]+)'s profile picture$/);
      if (m && inside(img)) { handle = m[1]; break; }
    }
  }

  const noise = /^(Edited|•|·|Follow|Following|more|… more|\.\.\. more|Original audio|Verified|See translation)$/i;
  let caption = null;
  for (const s of document.querySelectorAll("span, h1")) {
    const t = s.innerText?.trim() || "";
    if (!t || !inside(s)) continue;
    // Skip containers that also hold the name or the Follow button.
    const lines = t.split("\n").map((l) => l.trim());
    if (lines.some((l) => l === handle || noise.test(l))) continue;
    if (!caption || t.length > caption.length) caption = t;
  }
  return { handle, caption };
}

// The reel currently shown: a playing video first; otherwise the one covering most of the screen.
function mostVisibleVideo() {
  const videos = [...document.querySelectorAll("video")];
  const playing = videos.filter((v) => !v.paused && !v.ended && v.readyState > 2);
  let best = null;
  let bestArea = 0;
  for (const v of playing.length ? playing : videos) {
    const r = v.getBoundingClientRect();
    const w = Math.max(0, Math.min(r.right, window.innerWidth) - Math.max(r.left, 0));
    const h = Math.max(0, Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0));
    if (w * h > bestArea) {
      best = v;
      bestArea = w * h;
    }
  }
  return best;
}

// Instagram shortcodes are base64 media IDs; the top bits are milliseconds since Instagram's epoch (1314220021721). Accurate to about a minute.
function timeFromShortcode(shortcode) {
  const A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
  let id = 0n;
  for (const c of shortcode.slice(0, 11)) {
    const i = A.indexOf(c);
    if (i < 0) return null;
    id = id * 64n + BigInt(i);
  }
  return new Date(Number((id >> 23n) + 1314220021721n)).toISOString();
}

// Specifically for TikTok
function extractTikTok(el) {
  const root =
    el.closest('[data-e2e="recommend-list-item-container"]') ||
    el.closest("article") ||
    document;
  const pick = (...sels) => {
    for (const s of sels) {
      const n = root.querySelector(s);
      if (n) return n;
    }
    return null;
  };

  const onVideoPage = /\/video\/\d+/.test(location.pathname);
  const postUrl = onVideoPage
    ? location.href
    : root.querySelector('a[href*="/video/"]')?.href || null;

  const authorEl = pick('[data-e2e="video-author-uniqueid"]', '[data-e2e="browse-username"]');
  let handle = text(authorEl);
  if (!handle && postUrl) handle = postUrl.match(/\/@([^/]+)/)?.[1] || null;
  if (handle && !handle.startsWith("@")) handle = "@" + handle;

  // TikTok video IDs contain the upload time: the top 32 bits are Unix seconds.
  const id = postUrl?.match(/\/video\/(\d+)/)?.[1];
  const timestamp = id ? new Date(Number(BigInt(id) >> 32n) * 1000).toISOString() : null;

  return {
    platform: "tiktok",
    caption: text(pick('[data-e2e="video-desc"]', '[data-e2e="browse-video-desc"]')),
    author_name: text(pick('[data-e2e="video-author-nickname"]', '[data-e2e="browser-nickname"]')),
    author_handle: handle,
    timestamp,
    timestamp_source: timestamp ? "video_id" : null,
    post_url: postUrl,
  };
}
