// Service worker: context menu → capture from page → stub service → side panel.
const SERVICE_URL = "http://localhost:8000";
const USE_EMPTY_STUB = false; // true = test the "no evidence" response (?empty=true)

const SUPPORTED_SITES = [
  "https://x.com/*",
  "https://twitter.com/*",
  "https://www.instagram.com/*",
  "https://www.tiktok.com/*",
];

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "smcrd-check",
      title: "Check where this appeared before",
      // "page" too: Instagram and TikTok put invisible layers over their media,
      // so Chrome often doesn't see an image or video under the cursor.
      contexts: ["image", "video", "page"],
      documentUrlPatterns: SUPPORTED_SITES,
    });
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== "smcrd-check" || !tab?.id) return;
  // Must run first and synchronously: opening the panel needs the user's click.
  chrome.sidePanel.open({ tabId: tab.id });
  handleClick(info, tab);
});

async function handleClick(info, tab) {
  const capture = {
    media_url: info.srcUrl || null,
    media_type: info.mediaType || null,
    page_url: info.pageUrl || null,
    platform: null,
    caption: null,
    author_name: null,
    author_handle: null,
    timestamp: null,
    post_url: null,
    capture_error: null,
    captured_at: new Date().toISOString(),
  };

  try {
    const fromPage = await chrome.tabs.sendMessage(
      tab.id,
      { type: "smcrd-capture" },
      { frameId: info.frameId ?? 0 }
    );
    if (fromPage?.found) {
      const { media_url, ...rest } = fromPage.data;
      Object.assign(capture, rest);
      // Prefer Chrome's own srcUrl; fall back to what the page found under the cursor.
      capture.media_url = capture.media_url || media_url || null;
      if (!capture.media_type) capture.media_type = fromPage.data.media_kind || null;
    } else {
      capture.capture_error = "No post found around the clicked media.";
    }
  } catch (e) {
    capture.capture_error =
      "Content script not reachable. Reload the tab after installing or reloading the extension.";
  }

  if (capture.media_url?.startsWith("blob:")) {
    capture.capture_error =
      (capture.capture_error ? capture.capture_error + " " : "") +
      "Media URL is a blob: stream; the service can't download it. Use the post URL instead (week 2).";
  }

  await chrome.storage.session.set({ capture, result: null, status: "loading", error: null });

  try {
    const url = `${SERVICE_URL}/verify${USE_EMPTY_STUB ? "?empty=true" : ""}`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ media_url: capture.media_url }),
    });
    if (!res.ok) throw new Error(`Service answered ${res.status}`);
    await chrome.storage.session.set({ result: await res.json(), status: "done" });
  } catch (e) {
    await chrome.storage.session.set({
      status: "error",
      error: `Could not reach the service at ${SERVICE_URL} (${e.message}). Is uvicorn running?`,
    });
  }
}
