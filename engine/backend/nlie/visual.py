"""Visual intelligence: screenshot registration, perceptual hash, change detection, annotations.

Change detection is pixel arithmetic, not interpretation. Any model-based description of an image must be stored
with classification 'hypothesis'. Model-based image description is not implemented yet.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

try:
    from PIL import Image, ImageChops
    HAVE_PIL = True
except ImportError:  # pragma: no cover
    HAVE_PIL = False


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image_info(path: str | Path) -> dict:
    info = {"sha256": sha256_file(path), "width": 0, "height": 0, "ahash": ""}
    if HAVE_PIL:
        with Image.open(path) as im:
            info["width"], info["height"] = im.size
            small = im.convert("L").resize((8, 8))
            px = list(small.tobytes())
            avg = sum(px) / 64
            info["ahash"] = f"{int(''.join('1' if p > avg else '0' for p in px), 2):016x}"
    return info


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def compare(path_a: str | Path, path_b: str | Path, threshold: int = 16) -> dict:
    """changed_ratio = pixels whose greyscale difference exceeds `threshold` / total pixels, after resizing B to A.
    Different aspect ratios are reported, because resizing then distorts the comparison."""
    if not HAVE_PIL:
        raise RuntimeError("Pillow is required for image comparison.")
    with Image.open(path_a) as a, Image.open(path_b) as b:
        a, b = a.convert("RGB"), b.convert("RGB")
        same_size = a.size == b.size
        if not same_size:
            b = b.resize(a.size)
        diff = ImageChops.difference(a, b).convert("L")
        changed = sum(1 for p in diff.tobytes() if p > threshold)
        total = a.size[0] * a.size[1]
        bbox = diff.point(lambda p: 255 if p > threshold else 0).getbbox()
    ia, ib = image_info(path_a), image_info(path_b)
    return {"identical_file": ia["sha256"] == ib["sha256"], "same_dimensions": same_size,
            "changed_pixels": changed, "total_pixels": total, "changed_ratio": round(changed / total, 6) if total else 0.0,
            "changed_region": list(bbox) if bbox else None, "ahash_distance": hamming(ia["ahash"], ib["ahash"]),
            "method": f"per-pixel greyscale difference > {threshold} of 255; B resized to A when sizes differ"}


def categorise(viewport_width: int, full_page: bool) -> str:
    size = "mobile" if viewport_width < 600 else "tablet" if viewport_width < 1100 else "desktop"
    return f"{size}-{'full' if full_page else 'viewport'}"
