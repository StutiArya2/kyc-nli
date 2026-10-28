"""Render text to an image with correct complex-script shaping.

Why this module exists rather than a two-line Pillow call: Pillow's text drawing
only shapes complex scripts when it was built against Raqm, and the standard
Windows wheel is not. Without shaping, Devanagari vowel signs do not reorder
(कि renders as ka-then-i instead of i-then-ka), Bengali and Tamil conjuncts do
not form, and Arabic letters do not join — every glyph comes out in isolated
form.

That is not a cosmetic problem for this project. We are rendering text in order
to measure what an OCR engine does to it. Feeding the engine text no real
document has ever contained would calibrate the noise model against a fiction.

So layout goes through HarfBuzz (the same shaper Chrome, Firefox and Android
use) and rasterisation through FreeType, and Pillow is used only as a canvas.

A rendering-based calibration has a real limitation, stated here so it is not
forgotten downstream: rendered text has no perspective, glare, print texture,
paper grain or security overlay. ``degrade`` approximates capture conditions,
but approximating is what it does. See docs/decisions/0006-ocr-calibration.md.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import freetype
import numpy as np
import uharfbuzz as hb
from PIL import Image, ImageFilter

from kyc_nli.languages import repo_root
from kyc_nli.schema import Script

#: Open-licensed fonts, pinned rather than taken from whatever the OS provides.
#: A calibration whose numbers depend on which fonts a machine happens to have
#: installed is not reproducible.
FONTS: dict[Script, str] = {
    Script.LATIN: "NotoSans-Regular.ttf",
    Script.DEVANAGARI: "NotoSansDevanagari-Regular.ttf",
    Script.TAMIL: "NotoSansTamil-Regular.ttf",
    Script.BENGALI: "NotoSansBengali-Regular.ttf",
    Script.ARABIC: "NotoNaskhArabic-Regular.ttf",
}

FONT_URL_BASE = "https://github.com/notofonts/notofonts.github.io/raw/main/fonts"
FONT_SOURCES: dict[str, str] = {
    "NotoSans-Regular.ttf": "NotoSans/hinted/ttf/NotoSans-Regular.ttf",
    "NotoSansDevanagari-Regular.ttf": (
        "NotoSansDevanagari/hinted/ttf/NotoSansDevanagari-Regular.ttf"
    ),
    "NotoSansTamil-Regular.ttf": "NotoSansTamil/hinted/ttf/NotoSansTamil-Regular.ttf",
    "NotoSansBengali-Regular.ttf": "NotoSansBengali/hinted/ttf/NotoSansBengali-Regular.ttf",
    "NotoNaskhArabic-Regular.ttf": "NotoNaskhArabic/hinted/ttf/NotoNaskhArabic-Regular.ttf",
}


def fonts_dir() -> Path:
    return repo_root() / "data" / "external" / "fonts"


def fonts_available() -> bool:
    return all((fonts_dir() / name).exists() for name in FONTS.values())


def download_fonts() -> Path:
    """Fetch the pinned Noto fonts into data/external/fonts (gitignored)."""
    import urllib.request

    target = fonts_dir()
    target.mkdir(parents=True, exist_ok=True)
    for name, rel in FONT_SOURCES.items():
        path = target / name
        if not path.exists():
            urllib.request.urlretrieve(f"{FONT_URL_BASE}/{rel}", path)  # noqa: S310
    return target


@dataclass(frozen=True)
class DegradeConfig:
    """Approximates phone-camera capture of a printed document.

    These are the axes a real capture varies on that a clean render does not:
    focus, sensor noise, lossy compression, and slight rotation. Values are
    hand-chosen to span "good scan" to "bad phone photo"; they are not measured
    from a device, and the calibration report says so.
    """

    name: str
    blur: float = 0.0
    noise_sigma: float = 0.0
    jpeg_quality: int = 95
    rotation_deg: float = 0.0
    contrast: float = 1.0
    #: Rendered pixel height of the text. Small text is the dominant driver of
    #: real OCR error and the cheapest axis to vary.
    font_size: int = 40


#: Degradation levels, tuned against measured Tesseract output rather than
#: guessed. Two earlier attempts were wrong in opposite directions and both are
#: worth recording, because the mistakes are easy to repeat:
#:
#:   1. Sizes 44->22 with gentle blur produced a FLAT axis: Latin sat at 0.000
#:      CER for three of four levels, so three quarters of the ladder measured
#:      the same condition.
#:   2. Sizes 48->14 with heavy blur produced a CLIFF: the last two levels
#:      returned blank output (CER 1.000), which is total read failure, not
#:      degraded reading, and equally useless as an operating point.
#:
#: A sweep then showed why: at a fixed blur, font size barely matters down to
#: 16px, while at a fixed size, blur drives CER from ~0 to ~0.6 between 1.0 and
#: 2.2. **Blur is the lever; resolution is nearly irrelevant in this range.**
#: That was not the intuition the first two ladders were built on.
#:
#: The ladder below therefore holds size roughly constant and steps blur across
#: the measured transition. Verified by
#: tests/test_ocr_calibration.py::test_degradation_is_monotonic_in_measured_cer,
#: which checks real OCR output — the pixel-difference check passed on both
#: broken ladders and told us nothing.
#: A third correction: blur 2.2 returned blank output (CER ~1.0) for every
#: script. Total read failure is not a degradation level -- nothing downstream
#: can learn from "the engine returned nothing" -- so the ladder stops at the
#: last setting where the engine still produces text. Blank reads that do occur
#: are tracked separately as ``blank_rate`` rather than averaged into CER.
DEGRADE_LEVELS: tuple[DegradeConfig, ...] = (
    DegradeConfig("pristine", font_size=32),
    DegradeConfig("good_scan", blur=0.7, noise_sigma=5, jpeg_quality=75,
                  rotation_deg=0.4, font_size=26),
    DegradeConfig("phone_photo", blur=1.3, noise_sigma=10, jpeg_quality=55,
                  rotation_deg=0.9, contrast=0.9, font_size=24),
    DegradeConfig("poor_capture", blur=1.65, noise_sigma=14, jpeg_quality=45,
                  rotation_deg=1.3, contrast=0.8, font_size=23),
    DegradeConfig("severe", blur=1.95, noise_sigma=18, jpeg_quality=35,
                  rotation_deg=1.8, contrast=0.7, font_size=22),
)


@lru_cache(maxsize=8)
def _hb_font(path: str, size_px: int) -> hb.Font:
    blob = hb.Blob.from_file_path(path)
    font = hb.Font(hb.Face(blob))
    upem = font.face.upem
    font.scale = (upem, upem)
    hb.ot_font_set_funcs(font)
    return font


@lru_cache(maxsize=8)
def _ft_face(path: str) -> freetype.Face:
    return freetype.Face(path)


def render(text: str, script: Script, size_px: int = 40, padding: int = 16) -> Image.Image:
    """Render ``text`` with correct shaping. Returns a greyscale image, black on white."""
    font_path = str(fonts_dir() / FONTS[script])
    hb_font = _hb_font(font_path, size_px)
    face = _ft_face(font_path)
    face.set_pixel_sizes(0, size_px)

    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()  # sets script, language and RTL direction
    hb.shape(hb_font, buf)

    upem = hb_font.face.upem
    scale = size_px / upem

    # First pass: measure, so the canvas fits the shaped run.
    pen_x = 0.0
    boxes: list[tuple[int, float, float]] = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions, strict=True):
        boxes.append((info.codepoint, pen_x + pos.x_offset * scale, pos.y_offset * scale))
        pen_x += pos.x_advance * scale

    width = int(pen_x) + 2 * padding
    height = int(size_px * 2.2) + 2 * padding
    baseline = int(size_px * 1.45) + padding

    # Rasterise every glyph and place it relative to that advance-sized canvas.
    glyphs: list[tuple[np.ndarray, int, int]] = []
    for gid, x, y in boxes:
        face.load_glyph(gid, freetype.FT_LOAD_RENDER)
        bitmap = face.glyph.bitmap
        if bitmap.width == 0 or bitmap.rows == 0:
            continue
        glyph = np.array(bitmap.buffer, dtype=np.uint8).reshape(bitmap.rows, bitmap.pitch)
        glyphs.append(
            (
                glyph[:, : bitmap.width],
                int(x) + padding + face.glyph.bitmap_left,
                baseline - face.glyph.bitmap_top - int(y),
            )
        )

    # GROW the canvas to fit any glyph that overhangs it; never drop the glyph.
    #
    # Marks such as the Devanagari reph and ी overhang their advance width, by an
    # amount that grows with the font size. This used to `continue` past any
    # glyph that would not fit, so at large sizes with small padding the reph and
    # the vowel sign simply vanished -- चटर्जी drew as चटज, with no error. The
    # margins below are zero whenever nothing overhangs, so every render that was
    # already complete is byte-identical to before. That was checked against all
    # 4,200 renders the M1 calibration made (none had lost a glyph), so
    # ocr/measured.py and the calibrated noise model are unaffected.
    left = max([0] + [-gx for _, gx, _ in glyphs])
    top = max([0] + [-gy for _, _, gy in glyphs])
    right = max([0] + [gx + g.shape[1] - width for g, gx, _ in glyphs])
    bottom = max([0] + [gy + g.shape[0] - height for g, _, gy in glyphs])
    canvas = np.full((height + top + bottom, max(width + left + right, 1)), 255, dtype=np.uint8)

    for glyph, gx, gy in glyphs:
        gx, gy = gx + left, gy + top
        gh, gw = glyph.shape
        region = canvas[gy : gy + gh, gx : gx + gw]
        # Glyph coverage is alpha; composite black ink onto white.
        canvas[gy : gy + gh, gx : gx + gw] = np.minimum(region, 255 - glyph)

    return Image.fromarray(canvas, mode="L")


def degrade(image: Image.Image, config: DegradeConfig, seed: int = 0) -> Image.Image:
    """Apply the capture-condition approximation described by ``config``."""
    out = image
    if config.rotation_deg:
        # Image.BICUBIC is a deprecated alias kept alive by Pillow for now; the
        # enum is where it actually lives.
        out = out.rotate(
            config.rotation_deg,
            resample=Image.Resampling.BICUBIC,
            fillcolor=255,
            expand=True,
        )
    if config.blur:
        out = out.filter(ImageFilter.GaussianBlur(config.blur))
    if config.contrast != 1.0:
        arr = np.asarray(out, dtype=np.float32)
        arr = 255 - (255 - arr) * config.contrast
        out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="L")
    if config.noise_sigma:
        rng = np.random.default_rng(seed)
        arr = np.asarray(out, dtype=np.float32)
        arr = (arr + rng.normal(0.0, config.noise_sigma, arr.shape)).astype(np.float32)
        out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="L")
    if config.jpeg_quality < 95:
        buffer = io.BytesIO()
        out.convert("L").save(buffer, format="JPEG", quality=config.jpeg_quality)
        buffer.seek(0)
        out = Image.open(buffer).convert("L")
    return out
