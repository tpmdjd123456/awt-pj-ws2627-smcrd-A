# Video and `blob:` media URLs

## Problem
On X, Instagram and TikTok, video players stream the video in chunks and give the
`<video>` element a `blob:` URL (e.g. `blob:https://x.com/f7f81aea-...`).
A blob URL only exists inside the browser tab that created it. Opened anywhere else,
including by our service, it returns nothing (`ERR_FILE_NOT_FOUND`). So for most
videos the extension has no downloadable media URL.

## What the extension already captures
- `post_url`: the permalink, always available
- `video_poster`: a real thumbnail image URL (X: `pbs.twimg.com/amplify_video_thumb/...`);
  often missing on Instagram reels
- `media_url_expires`: Instagram/TikTok CDN URLs that do work expire after a few days

## Plan (not built yet)
1. Extension: if `media_url` starts with `blob:`, send `post_url` plus `video_poster`
   (if present) instead of the blob URL.
2. Service: make `media_url` optional in `VerifyRequest`; accept `post_url` as the source.
3. Service, quick path: run hash match and reverse search on `video_poster` (a real frame).
4. Service, full path: download the video from `post_url` (e.g. with `yt-dlp`), extract
   keyframes (e.g. one per scene change with `ffmpeg`), and probe each keyframe.
5. Panel: say when a result is based on the thumbnail only, since a thumbnail is
   weaker evidence than keyframes.

## Open points
- Platform terms of service for downloading videos; rate limits and logins.
- Instagram/TikTok CDN URLs expire: download promptly or store only `post_url`.
- The Mastodon demo feed has no blob problem: its media URLs are permanent files.
