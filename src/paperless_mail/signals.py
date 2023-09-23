def get_parser(*args, **kwargs):
    from paperless_mail.parsers import MailDocumentParser

    return MailDocumentParser(*args, **kwargs)


def mail_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 20,
        "mime_types": {
            "message/rfc822": ".eml",
        },
    }
