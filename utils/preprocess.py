import io
from pdf2image import convert_from_bytes
from PIL import Image


def preprocess(uploaded) -> list[Image.Image]:
    """
    Convert a PDF or image upload into a list of PIL Images.
    No OCR: raw images are passed directly to the LLM.
    """
    data = uploaded.read()
    uploaded.seek(0)
    filename = uploaded.name.lower()

    if filename.endswith(".pdf"):
        # Convert all pages to images
        return convert_from_bytes(data)
    else:
        # Single image file
        return [Image.open(io.BytesIO(data))]
