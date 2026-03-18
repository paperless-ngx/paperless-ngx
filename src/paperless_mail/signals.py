def get_parser(*args, **kwargs):
    from paperless.parsers.mail import MailDocumentParser

    # MailDocumentParser accepts no constructor args in the new-style protocol.
    # Pop legacy args that arrive from the signal-based consumer path.
    # Phase 4 will replace this signal path with the ParserRegistry.
    kwargs.pop("logging_group", None)
    kwargs.pop("progress_callback", None)
    return MailDocumentParser()


def mail_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 20,
        "mime_types": {
            "message/rfc822": ".eml",
        },
    }
