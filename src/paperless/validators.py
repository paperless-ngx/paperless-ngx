from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from lxml import etree

ALLOWED_SVG_TAGS: set[str] = {
    # Basic shapes
    "svg",  # Root SVG element
    "g",  # Group elements together
    "path",  # Draw complex shapes with commands
    "rect",  # Rectangle
    "circle",  # Circle
    "ellipse",  # Ellipse/oval
    "line",  # Straight line
    "polyline",  # Connected lines (open path)
    "polygon",  # Connected lines (closed path)
    # Text
    "text",  # Text container
    "tspan",  # Text span within text
    "textpath",  # Text along a path
    "style",  # Embedded CSS
    # Definitions and reusable content
    "defs",  # Container for reusable elements
    "symbol",  # Reusable graphic template
    "use",  # Reference/instantiate reusable elements
    "marker",  # Arrowheads and path markers
    "pattern",  # Repeating pattern fills
    "mask",  # Masking effects
    # Gradients
    "lineargradient",  # Linear gradient fill
    "radialgradient",  # Radial gradient fill
    "stop",  # Gradient color stop
    # Clipping
    "clippath",  # Clipping path definition
    # Metadata
    "title",  # Accessible title
    "desc",  # Accessible description
    "metadata",  # Document metadata
}

ALLOWED_SVG_ATTRIBUTES: set[str] = {
    # Core attributes
    "id",  # Unique identifier
    "class",  # CSS class names
    "style",  # Inline CSS styles (validate content separately!)
    # Positioning and sizing
    "x",  # X coordinate
    "y",  # Y coordinate
    "cx",  # Center X coordinate (circle/ellipse)
    "cy",  # Center Y coordinate (circle/ellipse)
    "r",  # Radius (circle)
    "rx",  # X radius (ellipse, rounded corners)
    "ry",  # Y radius (ellipse, rounded corners)
    "width",  # Width
    "height",  # Height
    "x1",  # Start X (line, gradient)
    "y1",  # Start Y (line, gradient)
    "x2",  # End X (line, gradient)
    "y2",  # End Y (line, gradient)
    "dx",  # X offset (text)
    "dy",  # Y offset (text)
    "points",  # Point list for polyline/polygon
    # Path data
    "d",  # Path commands and coordinates
    # Fill properties
    "fill",  # Fill color or none
    "fill-opacity",  # Fill transparency
    "fill-rule",  # Fill algorithm (nonzero/evenodd)
    "color",  # Current color
    # Stroke properties
    "stroke",  # Stroke color or none
    "stroke-width",  # Stroke thickness
    "stroke-opacity",  # Stroke transparency
    "stroke-linecap",  # Line ending style (butt/round/square)
    "stroke-linejoin",  # Corner style (miter/round/bevel)
    "stroke-miterlimit",  # Miter join limit
    "stroke-dasharray",  # Dash pattern
    "stroke-dashoffset",  # Dash pattern offset
    "vector-effect",  # Non-scaling stroke, etc.
    "clip-rule",  # Rule for clipping paths
    # Transforms and positioning
    "overflow",  # Overflow behavior
    "transform",  # Transformations (translate/rotate/scale)
    "viewbox",  # Coordinate system and viewport
    "preserveaspectratio",  # Scaling behavior
    # Opacity
    "opacity",  # Overall element opacity
    # Gradient attributes
    "gradienttransform",  # Transform applied to gradient
    "gradientunits",  # Gradient coordinate system
    "spreadmethod",  # Gradient spread method
    "fx",  # Radial gradient focal point X
    "fy",  # Radial gradient focal point Y
    "fr",  # Radial gradient focal radius
    "offset",  # Position of gradient stop
    "stop-color",  # Color at gradient stop
    "stop-opacity",  # Opacity at gradient stop
    # Clipping and masking
    "clip-path",  # Reference to clipping path
    "mask",  # Reference to mask
    # Markers
    "marker-start",  # Marker at path start
    "marker-mid",  # Marker at path vertices
    "marker-end",  # Marker at path end
    "markerunits",  # Marker coordinate system
    "markerwidth",  # Marker viewport width
    "markerheight",  # Marker viewport height
    "refx",  # Marker reference point X
    "refy",  # Marker reference point Y
    "orient",  # Marker orientation
    # Text attributes
    "font-family",  # Font name
    "font-size",  # Font size
    "font-weight",  # Font weight (normal/bold)
    "font-style",  # Font style (normal/italic)
    "text-anchor",  # Text alignment (start/middle/end)
    "text-decoration",  # Text decoration (underline/etc)
    "letter-spacing",  # Space between letters
    "word-spacing",  # Space between words
    "text-rendering",  # Text rendering hint
    "shape-rendering",  # Shape rendering hint
    "image-rendering",  # Image rendering hint
    "startoffset",  # TextPath start offset
    "method",  # TextPath method
    "spacing",  # TextPath spacing
    # Links and references
    "href",  # Link or reference (validate for javascript:!)
    "xlink:href",  # Legacy link reference (validate for javascript:!)
    "xlink:title",  # Accessible title for links
    # Pattern attributes
    "patternunits",  # Pattern coordinate system
    "patterntransform",  # Transform applied to pattern
    "patterncontentunits",  # Pattern content coordinate system
    # Mask attributes
    "maskunits",  # Mask coordinate system
    "maskcontentunits",  # Mask content coordinate system
    # SVG namespace declarations
    "xmlns",  # XML namespace (usually http://www.w3.org/2000/svg)
    "xmlns:xlink",  # XLink namespace
    "version",  # SVG version
    "type",
    # Accessibility
    "aria-label",
    "aria-hidden",
    "role",
    "focusable",
}

# Dangerous patterns in style attributes that can execute code
DANGEROUS_STYLE_PATTERNS: set[str] = {
    "javascript:",  # javascript: URLs in url() functions
    "data:text/html",  # HTML data URIs can contain scripts
    "expression(",  # IE's CSS expressions (legacy but dangerous)
    "import",  # CSS @import can load external resources
    "@import",  # CSS @import directive
    "-moz-binding:",  # Firefox XBL bindings (can execute code)
    "behaviour:",  # IE behavior property
    "behavior:",  # IE behavior property (US spelling)
    "vbscript:",  # VBScript URLs
    "data:application/",  # Data URIs for arbitrary application payloads
}

XLINK_NS: set[str] = {
    "http://www.w3.org/1999/xlink",
    "https://www.w3.org/1999/xlink",
}

# Dangerous URI schemes
DANGEROUS_SCHEMES: set[str] = {
    "javascript:",
    "data:text/html",
    "vbscript:",
    "file:",
    "data:application/",  # Can contain scripts
}

SAFE_PREFIXES: set[str] = {"#", "/", "./", "../", "data:image/"}


def reject_dangerous_svg(file: UploadedFile) -> None:
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
        tag: str = etree.QName(element.tag).localname.lower()
        if tag not in ALLOWED_SVG_TAGS:
            raise ValidationError(f"Disallowed SVG tag: <{tag}>")

        if tag == "style":
            # Combine all text (including CDATA) to scan for dangerous patterns
            style_text: str = "".join(element.itertext()).lower()
            for pattern in DANGEROUS_STYLE_PATTERNS:
                if pattern in style_text:
                    raise ValidationError(
                        f"Disallowed pattern in <style> content: {pattern}",
                    )

        attr_name: str
        attr_value: str
        for attr_name, attr_value in element.attrib.items():
            # lxml expands namespaces to {url}name. We must convert the standard
            # XLink namespace back to 'xlink:' so it matches our allowlist.
            if attr_name.startswith("{"):
                qname = etree.QName(attr_name)
                if qname.namespace in XLINK_NS:
                    attr_name_check = f"xlink:{qname.localname}"
                else:
                    # Unknown namespace: keep raw name (will fail allowlist)
                    attr_name_check = attr_name
            else:
                attr_name_check = attr_name

            attr_name_lower = attr_name_check.lower().strip()

            if attr_name_lower not in ALLOWED_SVG_ATTRIBUTES:
                raise ValidationError(f"Disallowed SVG attribute: {attr_name}")

            if attr_name_lower == "style":
                style_lower: str = attr_value.lower()
                # Check if any dangerous pattern is a substring of the style
                for pattern in DANGEROUS_STYLE_PATTERNS:
                    if pattern in style_lower:
                        raise ValidationError(
                            f"Disallowed pattern in style attribute: {pattern}",
                        )

            # Validate URI attributes (href, xlink:href)
            if attr_name_lower in {"href", "xlink:href"}:
                value_stripped: str = attr_value.strip().lower()

                # Check if value starts with any dangerous scheme
                for scheme in DANGEROUS_SCHEMES:
                    if value_stripped.startswith(scheme):
                        raise ValidationError(
                            f"Disallowed URI scheme in {attr_name}: {scheme}",
                        )

                # Allow safe schemes for logos: #anchor, relative paths, data:image/*
                # No external resources (http/https) needed for logos

                if value_stripped and not any(
                    value_stripped.startswith(prefix) for prefix in SAFE_PREFIXES
                ):
                    raise ValidationError(
                        f"URI scheme not allowed in {attr_name}: must be #anchor, relative path, or data:image/*",
                    )
