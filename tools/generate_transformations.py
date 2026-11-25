#!/usr/bin/env python3
"""
Transformation generator (Week 2, dataset track).

For every row in data/dataset.csv, take local_path_original and write labelled
variants to:   data/transformed/<case_id>/<transformation>_<strength>.jpg
plus a manifest: data/transformed/transformations.csv  (what was applied to what).

Usage (from repo root):
    pip install pillow
    python tools/generate_transformations.py
    python tools/generate_transformations.py --dataset data/dataset.csv --out data/transformed
    python tools/generate_transformations.py --only case_01 case_02

Conventions
-----------
- crop p%      : p% of each dimension is removed in total, split evenly over both
                 sides (crop_10 -> 5% off each edge). Change CROP_MODE to
                 "per_edge" to remove p% from EACH edge instead (40% per edge
                 leaves only 20% of the image - probably too brutal).
- crop_offcentre: keeps only the left/right/top/bottom 67% (aspect ratio changes, subject
                 moves off-centre). The centred crops above keep the aspect ratio.
- resize       : 50% / 25% of original width and height.
- re_encode    : original size, JPEG quality 90 / 70 / 50.
- screenshot   : scale to 90% + JPEG q75 (what a screen capture roughly does).
- mirror       : horizontal flip.
- text_overlay : "bar" = semi-opaque caption bar at the bottom (same fixed text on every case),
                 "meme" = large outlined block text, top and bottom.
- logo         : synthetic watermark in the bottom-right corner.
- All variants not testing compression are saved at JPEG quality 95, so the
  only change in each file is the transformation itself.
- The original is also copied as none_original.jpg (q95) as a baseline.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

BASE_QUALITY = 95
CROP_MODE = "total"  # "total" or "per_edge"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

FONT_CANDIDATES = [
    "Impact.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "arialbd.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


# --------------------------------------------------------------------------- helpers
def load_font(size):
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def wrap(draw, text, font, max_width):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= max_width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def open_rgb(path):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


# --------------------------------------------------------------------------- transformations
def t_none(img):
    return img.copy(), {}


def t_crop(p):
    def f(img):
        w, h = img.size
        frac = p / 100
        dx, dy = (int(w * frac), int(h * frac)) if CROP_MODE == "per_edge" else (int(w * frac / 2), int(h * frac / 2))
        box = (dx, dy, w - dx, h - dy)
        return img.crop(box), {"percent": p, "mode": CROP_MODE, "box": box}
    return f


def t_crop_offcentre(side, pct=67):
    """Keep only the left/right/top/bottom pct%: aspect ratio changes and the subject moves
    off-centre, like most real-world reuse (centred crops preserve aspect ratio)."""
    def f(img):
        w, h = img.size
        kw, kh = round(w * pct / 100), round(h * pct / 100)
        box = {"left": (0, 0, kw, h), "right": (w - kw, 0, w, h),
               "top": (0, 0, w, kh), "bottom": (0, h - kh, w, h)}[side]
        return img.crop(box), {"side": side, "kept_percent": pct, "box": box, "aspect_ratio_changed": True}
    return f


def t_resize(p):
    def f(img):
        w, h = img.size
        size = (max(1, round(w * p / 100)), max(1, round(h * p / 100)))
        return img.resize(size, Image.LANCZOS), {"percent": p}
    return f


def t_reencode(q):
    def f(img):
        return img.copy(), {"jpeg_quality": q}
    return f


def t_screenshot(img):
    w, h = img.size
    out = img.resize((round(w * 0.9), round(h * 0.9)), Image.BILINEAR)
    return out, {"scale": 0.9, "jpeg_quality": 75}


def t_mirror(img):
    return ImageOps.mirror(img), {"axis": "horizontal"}


def fit_lines(draw, text, max_w, max_h, start_size, min_size=10, spacing=1.1):
    """Shrink the font until the wrapped text fits in max_w x max_h."""
    size = int(start_size)
    while True:
        font = load_font(size)
        lines = wrap(draw, text, font, max_w)
        widest = max(draw.textlength(ln, font=font) for ln in lines)
        total = len(lines) * size * spacing
        if (widest <= max_w and total <= max_h) or size <= min_size:
            return font, lines, size
        size -= 2


BAR_TEXT = "BREAKING: Happening right now"
MEME_TOP = "This is happening right now"
MEME_BOTTOM = "They don't want you to see this"


def t_text_bar(img):
    w, h = img.size
    base = img.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    bar_h = int(h * 0.14)
    d.rectangle((0, h - bar_h, w, h), fill=(0, 0, 0, 190))
    font, lines, size = fit_lines(d, BAR_TEXT, w * 0.94, bar_h * 0.85, bar_h * 0.45)
    y = h - bar_h + (bar_h - len(lines) * size * 1.1) / 2
    for ln in lines:
        tw = d.textlength(ln, font=font)
        d.text(((w - tw) / 2, y), ln, font=font, fill=(255, 255, 255, 255))
        y += size * 1.1
    return (Image.alpha_composite(base, layer).convert("RGB"),
            {"style": "caption_bar", "bar_height_pct": 14, "text": BAR_TEXT})


def t_text_meme(img):
    w, h = img.size
    base = img.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    start = min(h * 0.10, w * 0.12)

    def block(text, top):
        font, lines, size = fit_lines(d, text.upper(), w * 0.90, h * 0.22, start)
        stroke = max(2, size // 12)
        total = len(lines) * size * 1.1
        y = 0.03 * h if top else h - total - 0.03 * h
        for ln in lines:
            tw = d.textlength(ln, font=font)
            d.text(((w - tw) / 2, y), ln, font=font, fill=(255, 255, 255, 255),
                   stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
            y += size * 1.1

    block(MEME_TOP, top=True)
    block(MEME_BOTTOM, top=False)
    return (Image.alpha_composite(base, layer).convert("RGB"),
            {"style": "meme_block", "text_top": MEME_TOP, "text_bottom": MEME_BOTTOM})


def t_logo(img):
    w, h = img.size
    base = img.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lw = min(max(60, int(min(w, h) * 0.30)), int(w * 0.40))
    lh = int(lw * 0.35)
    margin = int(min(w, h) * 0.03)
    x0, y0 = w - lw - margin, h - lh - margin
    d.rounded_rectangle((x0, y0, x0 + lw, y0 + lh), radius=lh // 4, fill=(20, 60, 160, 170))
    d.ellipse((x0 + lh * 0.15, y0 + lh * 0.15, x0 + lh * 0.85, y0 + lh * 0.85), fill=(255, 200, 0, 200))
    text_x = x0 + lh * 1.0
    font, _, _ = fit_lines(d, "NEWS24", lw - lh * 1.1, lh * 0.9, lh * 0.45)
    bbox = d.textbbox((0, 0), "NEWS24", font=font)
    ty = y0 + (lh - (bbox[3] - bbox[1])) / 2 - bbox[1]
    d.text((text_x, ty), "NEWS24", font=font, fill=(255, 255, 255, 230))
    return (Image.alpha_composite(base, layer).convert("RGB"),
            {"position": "bottom_right", "width_px": lw})


# (transformation, strength label, function, jpeg quality for the saved file)
VARIANTS = (
    [("none", "original", t_none, BASE_QUALITY)]
    + [("crop", str(p), t_crop(p), BASE_QUALITY) for p in (5, 10, 20, 30, 40)]
    + [("crop_offcentre", f"{side}67", t_crop_offcentre(side), BASE_QUALITY)
       for side in ("left", "right", "top", "bottom")]
    + [("resize", str(p), t_resize(p), BASE_QUALITY) for p in (50, 25)]
    + [("re_encode", f"q{q}", t_reencode(q), q) for q in (90, 70, 50)]
    + [("screenshot", "s90q75", t_screenshot, 75)]
    + [("mirror", "h", t_mirror, BASE_QUALITY)]
    + [("text_overlay", "bar", t_text_bar, BASE_QUALITY),
       ("text_overlay", "meme", t_text_meme, BASE_QUALITY)]
    + [("logo", "corner", t_logo, BASE_QUALITY)]
)

MANIFEST_FIELDS = [
    "case_id", "source_path", "output_path", "transformation", "strength",
    "params", "jpeg_quality", "src_width", "src_height", "out_width", "out_height",
]


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="data/dataset.csv")
    ap.add_argument("--out", default="data/transformed")
    ap.add_argument("--root", default=".", help="repo root that local_path_original is relative to")
    ap.add_argument("--only", nargs="*", help="only these case_ids")
    args = ap.parse_args()

    root, out_dir = Path(args.root), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.dataset, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    manifest, skipped = [], []
    for row in rows:
        case_id = (row.get("case_id") or "").strip()
        rel = (row.get("local_path_original") or "").strip().replace("\\", "/")
        if not case_id or (args.only and case_id not in args.only):
            continue
        src = root / rel
        if not rel or not src.is_file():
            skipped.append((case_id, f"file not found: {rel!r}"))
            continue
        if src.suffix.lower() not in IMAGE_EXTS:
            skipped.append((case_id, f"not an image ({src.suffix}) - video cases need keyframes"))
            continue

        try:
            img = open_rgb(src)
        except Exception as e:  # noqa: BLE001
            skipped.append((case_id, f"cannot open: {e}"))
            continue

        case_out = out_dir / case_id
        case_out.mkdir(parents=True, exist_ok=True)
        for name, strength, fn, quality in VARIANTS:
            out_img, params = fn(img)
            out_path = case_out / f"{name}_{strength}.jpg"
            out_img.save(out_path, "JPEG", quality=quality)
            manifest.append({
                "case_id": case_id,
                "source_path": rel,
                "output_path": out_path.as_posix(),
                "transformation": name,
                "strength": strength,
                "params": json.dumps(params),
                "jpeg_quality": quality,
                "src_width": img.size[0], "src_height": img.size[1],
                "out_width": out_img.size[0], "out_height": out_img.size[1],
            })
        print(f"{case_id}: {len(VARIANTS)} variants")

    manifest_path = out_dir / "transformations.csv"
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(manifest)

    print(f"\n{len(manifest)} files written, manifest: {manifest_path}")
    if skipped:
        print("\nSkipped:")
        for cid, why in skipped:
            print(f"  {cid}: {why}")
        sys.exit(1)


if __name__ == "__main__":
    main()