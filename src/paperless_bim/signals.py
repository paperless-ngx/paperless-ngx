def get_parser(*args, **kwargs):
    from paperless_bim.parsers import BimDocumentParser

    return BimDocumentParser(*args, **kwargs)


def bim_consumer_declaration(sender, **kwargs):
    """
    Register the IFC parser as a consumer for the BIM MIME types.

    IFC files are usually served as application/octet-stream because there is
    no IANA-registered MIME type, so we declare several common aliases
    (including application/x-step, the de-facto IFC MIME) and let the
    sniffing in BimDocumentParser.handle confirm the magic header
    `ISO-10303-21` before treating the file as BIM.
    """
    return {
        "parser": get_parser,
        "weight": 20,
        "mime_types": {
            "application/x-step": ".ifc",
            "application/x-ifc": ".ifc",
            "application/ifc": ".ifc",
            "application/x-ifczip": ".ifczip",
        },
    }
