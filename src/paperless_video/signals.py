def get_parser(*args, **kwargs):
    from paperless_video.parsers import VideoDocumentParser

    return VideoDocumentParser(*args, **kwargs)


def video_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 10,
        "mime_types": {
            "video/mp4": ".mp4",
        },
    }
