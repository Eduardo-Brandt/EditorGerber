"""Static, amount-free BR Code; no network or payment initiation."""

import binascii
import unicodedata


def field(tag, value):
    if len(value.encode("ascii")) > 99:
        raise ValueError("Pix field too long")
    return f"{tag}{len(value):02d}{value}"


def pix_payload(key, name, city):
    def plain(value, maximum):
        return (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode()
            .strip()[:maximum]
        )

    account = field("00", "br.gov.bcb.pix") + field("01", key)
    payload = (
        field("00", "01")
        + field("26", account)
        + field("52", "0000")
        + field("53", "986")
        + field("58", "BR")
        + field("59", plain(name, 25))
        + field("60", plain(city, 15))
        + field("62", field("05", "***"))
        + "6304"
    )
    return payload + f"{binascii.crc_hqx(payload.encode('ascii'), 0xFFFF):04X}"


def qr_image(payload, scale=6):
    import qrcode
    from PySide6.QtGui import QImage

    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
    code.add_data(payload)
    code.make(fit=True)
    matrix = code.get_matrix()
    image = QImage(len(matrix), len(matrix), QImage.Format.Format_RGB32)
    image.fill(0xFFFFFFFF)
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                image.setPixel(x, y, 0xFF000000)
    from PySide6.QtCore import Qt

    return image.scaled(
        len(matrix) * scale,
        len(matrix) * scale,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )
