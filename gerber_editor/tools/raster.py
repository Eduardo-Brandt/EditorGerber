"""Threshold raster artwork to exact rectangular Gerber regions, without GDAL."""

from decimal import Decimal
from uuid import uuid4

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter

from gerber_editor.core.objects import GerberObject, Polarity
from gerber_editor.tools.shapes import layer_quantum, point_on_grid, rectangle_region


def binary_image(image: QImage, pixels: int, threshold: int, invert=False):
    if image.isNull():
        raise ValueError("Unable to read the image.")
    if not 1 <= pixels <= 2000 or not 0 <= threshold <= 255:
        raise ValueError("Invalid image resolution or threshold.")
    scaled = image.scaledToWidth(pixels, Qt.TransformationMode.SmoothTransformation)
    if scaled.height() > 4000:
        raise ValueError("Image is too tall. Reduce the pixel resolution.")
    opaque = QImage(scaled.size(), QImage.Format.Format_RGB32)
    opaque.fill(Qt.GlobalColor.white)
    painter = QPainter(opaque)
    painter.drawImage(0, 0, scaled)
    painter.end()
    gray = opaque.convertToFormat(QImage.Format.Format_Grayscale8)
    values = np.frombuffer(gray.constBits(), dtype=np.uint8).reshape(
        gray.height(), gray.bytesPerLine()
    )
    mask = (values[:, : gray.width()] < threshold).copy()
    if invert:
        mask = ~mask
    preview = np.ascontiguousarray(np.where(mask, 0, 255).astype(np.uint8))
    bitmap = QImage(
        preview.data, gray.width(), gray.height(), gray.width(), QImage.Format.Format_Grayscale8
    ).copy()
    return mask, bitmap


def merged_rectangles(mask):
    """Merge identical horizontal pixel runs in consecutive rows."""
    active = {}
    for row_index, row in enumerate(mask):
        changes = np.flatnonzero(np.diff(np.r_[False, row, False].astype(np.int8)))
        runs = {(int(a), int(b)) for a, b in zip(changes[::2], changes[1::2], strict=True)}
        for run in list(active):
            if run not in runs:
                yield run[0], active.pop(run), run[1], row_index
        for run in runs:
            active.setdefault(run, row_index)
    for run, start in active.items():
        yield run[0], start, run[1], len(mask)


def raster_objects(layer, mask, position, width_mm: Decimal, polarity=Polarity.DARK):
    if not width_mm.is_finite() or width_mm <= 0:
        raise ValueError("Image width must be positive.")
    quantum = layer_quantum(layer)
    pitch = width_mm / Decimal(mask.shape[1])
    if pitch < quantum:
        raise ValueError(
            "Image resolution is finer than the layer coordinate grid. Reduce pixels or increase width."
        )
    objects = []
    group_id = uuid4().hex
    height = mask.shape[0]
    for left, top, right, bottom in merged_rectangles(mask):
        a = point_on_grid(
            position.x + left * pitch, position.y + (height - bottom) * pitch, quantum
        )
        b = point_on_grid(position.x + right * pitch, position.y + (height - top) * pitch, quantum)
        objects.append(GerberObject(rectangle_region(a, b), None, polarity, group_id=group_id))
        if len(objects) > 30000:
            raise ValueError("Artwork exceeds 30,000 regions. Reduce the pixel resolution.")
    if not objects:
        raise ValueError("No black pixels found. Change the threshold or invert the image.")
    return objects
