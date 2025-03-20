def get_parser(*args, **kwargs):
    from paperless_mistralocr.parsers import MistralOcrDocumentParser

    return MistralOcrDocumentParser(*args, **kwargs)


def mistral_ocr_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 10,  # Higher weight than default parsers to prioritize this parser
        "mime_types": {
            "application/pdf": ".pdf",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/tiff": ".tif",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
            "image/webp": ".webp",
        },
    } 