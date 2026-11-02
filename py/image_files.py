from pathlib import Path
import re

import folder_paths
from PIL import Image


def _plain_png(path):
    # PNG EXIF can follow IDAT. Pillow.getexif() decodes the image to find it;
    # skip compressed chunks instead, and leave such files on the tensor path.
    with open(path, "rb") as source:
        source.seek(8)
        while header := source.read(8):
            if len(header) != 8:
                return False
            length, kind = int.from_bytes(header[:4], "big"), header[4:]
            if kind in {b"eXIf", b"acTL", b"tRNS"}:
                return False
            if kind == b"IEND":
                return True
            source.seek(length + 4, 1)
    return False


def _source_files(dynprompt, link, visiting):
    if not isinstance(link, list) or len(link) != 2 or link[1] != 0:
        return None
    node_id = link[0]
    if node_id in visiting or not dynprompt.has_node(node_id):
        return None
    node = dynprompt.get_node(node_id)
    inputs = node["inputs"]
    if node["class_type"] == "LoadImage" and set(inputs) == {"image"}:
        filename = inputs["image"]
        if not isinstance(filename, str):
            return None
        root = Path(folder_paths.get_input_directory()).resolve()
        filename, annotated_root = folder_paths.annotated_filepath(filename)
        if annotated_root is not None and Path(annotated_root).resolve() != root:
            return None
        path = (root / filename).resolve()
        if Path(filename).is_absolute() or not path.is_relative_to(root):
            raise ValueError("Reference image must be inside the current input directory.")
        try:
            with Image.open(path) as image:
                if image.format not in {"JPEG", "PNG"} or image.mode != "RGB":
                    return None
                if image.format == "JPEG" and image.getexif().get(274, 1) != 1:
                    return None
                if image.format == "PNG" and not _plain_png(path):
                    return None
                return [(str(path), image.size)]
        except (OSError, Image.DecompressionBombError):
            return None

    if node["class_type"] != "BatchImagesNode" or not inputs:
        return None
    if any(re.fullmatch(r"images\.image\d+", key) is None for key in inputs):
        return None
    files = []
    for key in sorted(inputs, key=lambda key: int(key.removeprefix("images.image"))):
        sources = _source_files(dynprompt, inputs[key], visiting | {node_id})
        if sources is None:
            return None
        files.extend(sources)
    # BatchImages resizes to its first input. Only bypass a batch that would
    # concatenate unchanged RGB images of equal dimensions.
    if any(size != files[0][1] for _, size in files):
        return None
    return files


def original_image_files(dynprompt, unique_id, input_name):
    if dynprompt is None or unique_id is None:
        return None
    link = dynprompt.get_node(unique_id)["inputs"].get(input_name)
    sources = _source_files(dynprompt, link, set())
    return [path for path, _ in sources] if sources is not None else None


def required_image_inputs(dynprompt, unique_id, images):
    return [name for name, image in images.items()
            if image is None and original_image_files(dynprompt, unique_id, name) is None]
