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
  let post;
  if (host.endsWith("x.com") || host.endsWith("twitter.com")) post = extractX(el);
  else if (host.endsWith("instagram.com")) post = extractInstagram(el);
  else if (host.endsWith("tiktok.com")) post = extractTikTok(el);
  else return { found: false };

  const media = mediaInfo(mediaAtClick(el));
  const { platform, ...fields } = post;
  const postFound = Object.values(fields).some((v) => v);
  return {
    found: postFound || !!media.media_url,
    data: {
      ...post,
      ...media,
      capture_error: postFound ? null : "Media found, but no post details around it.",
    },
  };
}

// media under the cursor (works through overlay layers)
function mediaAtClick(el) {
  for (const node of document.elementsFromPoint(last.x, last.y)) {
    if (node.tagName === "IMG" || node.tagName === "VIDEO") return node;
  }
  return el.closest?.("img, video") || null;
}

function mediaInfo(m) {
  if (!m) return { media_url: null, media_kind: null, video_poster: null };
  if (m.tagName === "VIDEO") {
    return {
      media_url: m.currentSrc || m.src || m.querySelector("source")?.src || null,
      media_kind: "video",
      video_poster: m.poster || null,
    };
  }
  return { media_url: m.currentSrc || m.src || null, media_kind: "image", video_poster: null };
}

function text(node) {
  const t = node?.innerText?.trim();
  return t ? t : null;
}

// Specifically for X
function extractX(el) {
  const article = el.closest('article[data-testid="tweet"]') || el.closest("article");
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

// Specifically for Insta
function extractInstagram(el) {
  const root = el.closest("article") || el.closest('[role="dialog"]') || document;
  const timeEl = root.querySelector("time[datetime]");
  const isPostPage = /\/(p|reel|reels)\//.test(location.pathname);
  const postUrl =
    timeEl?.closest("a")?.href ||
    root.querySelector('a[href*="/p/"], a[href*="/reel/"]')?.href ||
    (isPostPage ? location.href : null);

  const authorLink = root.querySelector('header a[href^="/"]');
  const handle = authorLink?.getAttribute("href")?.replace(/\//g, "") || null;

  // Post page: caption is in an h1. Feed: take the longest text span in the post.
  let caption = text(root.querySelector("h1"));
  if (!caption && root !== document) {
    let best = "";
    for (const s of root.querySelectorAll('span[dir="auto"]')) {
      const t = s.innerText?.trim() || "";
      if (t.length > best.length && t !== handle) best = t;
    }
    caption = best || null;
  }

  return {
    platform: "instagram",
    caption,
    author_name: null,
    author_handle: handle ? "@" + handle : null,
    timestamp: timeEl?.getAttribute("datetime") || null,
    timestamp_source: timeEl ? "page" : null,
    post_url: postUrl,
  };
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
