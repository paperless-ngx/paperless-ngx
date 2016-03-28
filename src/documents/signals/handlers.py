import logging

from ..models import Correspondent, Tag


def logger(message, group):
    logging.getLogger(__name__).debug(message, extra={"group": group})


def set_correspondent(sender, document=None, logging_group=None, **kwargs):

    # No sense in assigning a correspondent when one is already set.
    if document.correspondent:
        return

    # No matching correspondents, so no need to continue
    potential_correspondents = list(Correspondent.match_all(document.content))
    if not potential_correspondents:
        return

    potential_count = len(potential_correspondents)
    selected = potential_correspondents[0]
    if potential_count > 1:
        message = "Detected {} potential correspondents, so we've opted for {}"
        logger(
            message.format(potential_count, selected),
            logging_group
        )

    logger(
        'Assigning correspondent "{}" to "{}" '.format(selected, document),
        logging_group
    )

    document.correspondent = selected
    document.save(update_fields=("correspondent",))


def set_tags(sender, document=None, logging_group=None, **kwargs):

    current_tags = set(document.tags.all())
    relevant_tags = set(Tag.match_all(document.content)) - current_tags

    if not relevant_tags:
        return

    message = 'Tagging "{}" with "{}"'
    logger(
        message.format(document, ", ".join([t.slug for t in relevant_tags])),
        logging_group
    )

    document.tags.add(*relevant_tags)
