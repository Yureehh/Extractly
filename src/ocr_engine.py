from __future__ import annotations

from PIL import Image

from extractly.integrations.ocr import run_ocr as _run_ocr


def run_ocr(pages: list[Image.Image]) -> str:
    return _run_ocr(pages)


__all__ = ["run_ocr"]
