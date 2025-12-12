from django.core.exceptions import ValidationError
from lxml import etree

ALLOWED_SVG_TAGS: set[str] = {
    "svg",
    "g",
    "path",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "text",
    "tspan",
    "defs",
    "lineargradient",
    "radialgradient",
    "stop",
    "clippath",
    "use",
    "title",
    "desc",
    "style",
}

ALLOWED_SVG_ATTRIBUTES: set[str] = {
    "id",
    "class",
    "style",
    "d",
    "fill",
    "fill-opacity",
    "fill-rule",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-miterlimit",
    "stroke-dasharray",
    "stroke-dashoffset",
    "stroke-opacity",
    "transform",
    "x",
    "y",
    "cx",
    "cy",
    "r",
    "rx",
    "ry",
    "width",
    "height",
    "x1",
    "y1",
    "x2",
    "y2",
    "gradienttransform",
    "gradientunits",
    "offset",
    "stop-color",
    "stop-opacity",
    "clip-path",
    "viewbox",
    "preserveaspectratio",
    "href",
    "xlink:href",
    "font-family",
    "font-size",
    "font-weight",
    "text-anchor",
    "xmlns",
    "xmlns:xlink",
    "version",
    "type",
}


def reject_dangerous_svg(file):
    """
    Rejects SVG files that contain dangerous tags or attributes.
    Raises ValidationError if unsafe content is found.
    See GHSA-6p53-hqqw-8j62
    """
    try:
        parser = etree.XMLParser(resolve_entities=False)
        file.seek(0)
        tree = etree.parse(file, parser)
        root = tree.getroot()
    except etree.XMLSyntaxError:
        raise ValidationError("Invalid SVG file.")

    for element in root.iter():
        tag = etree.QName(element.tag).localname.lower()
        if tag not in ALLOWED_SVG_TAGS:
            raise ValidationError(f"Disallowed SVG tag: <{tag}>")

        for attr_name, attr_value in element.attrib.items():
            attr_name_lower = attr_name.lower()
            if attr_name_lower not in ALLOWED_SVG_ATTRIBUTES:
                raise ValidationError(f"Disallowed SVG attribute: {attr_name}")

            if attr_name_lower in {
                "href",
                "xlink:href",
            } and attr_value.strip().lower().startswith("javascript:"):
                raise ValidationError(f"Disallowed javascript: URI in {attr_name}")
