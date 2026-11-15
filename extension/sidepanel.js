// Shows whatever background.js stored. textContent only: captions are untrusted.
function fill(dl, rows) {
  dl.replaceChildren();
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value ?? "not found";
    dl.append(dt, dd);
  }
}

function render({ capture, result, status, error }) {
  const statusEl = document.getElementById("status");
  if (status === "captured") statusEl.textContent = "Captured.";
  else if (status === "loading") statusEl.textContent = "Checking…";
  else if (status === "error") statusEl.textContent = error;
  else if (status === "done") statusEl.textContent = "Done (stubbed result).";

  if (capture) {
    fill(document.getElementById("capture"), [
      ["Media URL", capture.media_url],
      ["Media URL expires", capture.media_url_expires],
      ["Text on media (alt)", capture.media_alt],
      ["Video poster", capture.video_poster],
      ["Caption", capture.post_caption],
      ["Author", capture.post_author],
      ["Timestamp", capture.post_date
        ? `${capture.post_date}${capture.post_date_source === "video_id" ? " (from video ID)" : ""}${capture.post_date_source === "shortcode" ? " (from post ID, ±1 min)" : ""}`
        : null],
      ["Permalink", capture.post_url],
      ["Platform", capture.platform],
      ["Media type", capture.media_type],
      ["Capture problem", capture.capture_error],
    ]);
  }

  const resultDl = document.getElementById("result");
  const raw = document.getElementById("raw");
  document.getElementById("service").hidden = !result && status !== "loading" && status !== "error";
  if (!result) { resultDl.replaceChildren(); raw.textContent = ""; return; }

  const e = result.earliest_known_appearance;
  const a = result.attested_context;
  fill(resultDl, [
    ["Confidence tier", result.confidence_tier],
    ["Earliest known appearance", e ? `${e.date} · ${e.source} (${e.evidence_type})` : "None found"],
    ["Earliest caption", e?.caption],
    ["Attested context", a ? `${a.description} — ${a.location ?? ""}, ${a.date ?? ""}` : "None"],
    ["Attested by", a ? `${a.source} (${a.evidence_type})` : null],
    ["Other candidates", String(result.candidates?.length ?? 0)],
    ["Probes run", (result.probes_run || []).join(", ")],
    ["Probes failed", (result.probes_failed || []).join(", ") || "none"],
  ]);
  raw.textContent = JSON.stringify(result, null, 2);
}

chrome.storage.session.get(null).then(render);
chrome.storage.onChanged.addListener((_changes, area) => {
  if (area === "session") chrome.storage.session.get(null).then(render);
});