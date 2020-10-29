import re

from fuzzywuzzy import fuzz

from documents.models import MatchingModel, Correspondent, DocumentType, Tag


def match_correspondents(document_content, classifier):
    correspondents = Correspondent.objects.all()
    predicted_correspondent_id = classifier.predict_correspondent(document_content) if classifier else None

    matched_correspondents = [o for o in correspondents if matches(o, document_content) or o.id == predicted_correspondent_id]
    return matched_correspondents


def match_document_types(document_content, classifier):
    document_types = DocumentType.objects.all()
    predicted_document_type_id = classifier.predict_document_type(document_content) if classifier else None

    matched_document_types = [o for o in document_types if matches(o, document_content) or o.id == predicted_document_type_id]
    return matched_document_types


def match_tags(document_content, classifier):
    objects = Tag.objects.all()
    predicted_tag_ids = classifier.predict_tags(document_content) if classifier else []

    matched_tags = [o for o in objects if matches(o, document_content) or o.id in predicted_tag_ids]
    return matched_tags


def matches(matching_model, document_content):
    search_kwargs = {}

    document_content = document_content.lower()

    # Check that match is not empty
    if matching_model.match.strip() == "":
        return False

    if matching_model.is_insensitive:
        search_kwargs = {"flags": re.IGNORECASE}

    if matching_model.matching_algorithm == MatchingModel.MATCH_ALL:
        for word in _split_match(matching_model):
            search_result = re.search(
                r"\b{}\b".format(word), document_content, **search_kwargs)
            if not search_result:
                return False
        return True

    if matching_model.matching_algorithm == MatchingModel.MATCH_ANY:
        for word in _split_match(matching_model):
            if re.search(r"\b{}\b".format(word), document_content, **search_kwargs):
                return True
        return False

    if matching_model.matching_algorithm == MatchingModel.MATCH_LITERAL:
        return bool(re.search(
            r"\b{}\b".format(matching_model.match), document_content, **search_kwargs))

    if matching_model.matching_algorithm == MatchingModel.MATCH_REGEX:
        return bool(re.search(
            re.compile(matching_model.match, **search_kwargs), document_content))

    if matching_model.matching_algorithm == MatchingModel.MATCH_FUZZY:
        match = re.sub(r'[^\w\s]', '', matching_model.match)
        text = re.sub(r'[^\w\s]', '', document_content)
        if matching_model.is_insensitive:
            match = match.lower()
            text = text.lower()

        return True if fuzz.partial_ratio(match, text) >= 90 else False

    if matching_model.matching_algorithm == MatchingModel.MATCH_AUTO:
        # this is done elsewhere.
        return False

    raise NotImplementedError("Unsupported matching algorithm")


def _split_match(matching_model):
    """
    Splits the match to individual keywords, getting rid of unnecessary
    spaces and grouping quoted words together.

    Example:
      '  some random  words "with   quotes  " and   spaces'
        ==>
      ["some", "random", "words", "with+quotes", "and", "spaces"]
    """
    findterms = re.compile(r'"([^"]+)"|(\S+)').findall
    normspace = re.compile(r"\s+").sub
    return [
        normspace(" ", (t[0] or t[1]).strip()).replace(" ", r"\s+")
        for t in findterms(matching_model.match)
    ]
