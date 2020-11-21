import re

from fuzzywuzzy import fuzz

from documents.models import MatchingModel, Correspondent, DocumentType, Tag


def match_correspondents(document_content, classifier):
    if classifier:
        pred_id = classifier.predict_correspondent(document_content)
    else:
        pred_id = None

    correspondents = Correspondent.objects.all()

    return list(filter(
        lambda o: matches(o, document_content) or o.pk == pred_id,
        correspondents))


def match_document_types(document_content, classifier):
    if classifier:
        pred_id = classifier.predict_document_type(document_content)
    else:
        pred_id = None

    document_types = DocumentType.objects.all()

    return list(filter(
        lambda o: matches(o, document_content) or o.pk == pred_id,
        document_types))


def match_tags(document_content, classifier):
    if classifier:
        predicted_tag_ids = classifier.predict_tags(document_content)
    else:
        predicted_tag_ids = []

    tags = Tag.objects.all()

    return list(filter(
        lambda o: matches(o, document_content) or o.pk in predicted_tag_ids,
        tags))


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
                rf"\b{word}\b", document_content, **search_kwargs)
            if not search_result:
                return False
        return True

    elif matching_model.matching_algorithm == MatchingModel.MATCH_ANY:
        for word in _split_match(matching_model):
            if re.search(rf"\b{word}\b", document_content, **search_kwargs):
                return True
        return False

    elif matching_model.matching_algorithm == MatchingModel.MATCH_LITERAL:
        return bool(re.search(
            rf"\b{matching_model.match}\b",
            document_content,
            **search_kwargs
        ))

    elif matching_model.matching_algorithm == MatchingModel.MATCH_REGEX:
        return bool(re.search(
            re.compile(matching_model.match, **search_kwargs),
            document_content
        ))

    elif matching_model.matching_algorithm == MatchingModel.MATCH_FUZZY:
        match = re.sub(r'[^\w\s]', '', matching_model.match)
        text = re.sub(r'[^\w\s]', '', document_content)
        if matching_model.is_insensitive:
            match = match.lower()
            text = text.lower()

        return fuzz.partial_ratio(match, text) >= 90

    elif matching_model.matching_algorithm == MatchingModel.MATCH_AUTO:
        # this is done elsewhere.
        return False

    else:
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
