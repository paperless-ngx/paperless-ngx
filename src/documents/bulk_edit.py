from documents.models import Document, Correspondent

methods_supported = [
    "set_correspondent"
]


def validate_data(data):
    if 'ids' not in data or not isinstance(data['ids'], list):
        raise ValueError()
    ids = data['ids']
    if not all([isinstance(i, int) for i in ids]):
        raise ValueError()
    count = Document.objects.filter(pk__in=ids).count()
    if not count == len(ids):
        raise Document.DoesNotExist()

    if 'method' not in data or not isinstance(data['method'], str):
        raise ValueError()
    method = data['method']
    if method not in methods_supported:
        raise ValueError()

    if 'args' not in data or not isinstance(data['args'], list):
        raise ValueError()
    parameters = data['args']

    return ids, method, parameters


def perform_bulk_edit(data):
    ids, method, args = validate_data(data)

    getattr(__file__, method)(ids, args)


def set_correspondent(ids, args):
    if not len(args) == 1:
        raise ValueError()

    if not args[0]:
        correspondent = None
    else:
        if not isinstance(args[0], int):
            raise ValueError()

        correspondent = Correspondent.objects.get(args[0])

    Document.objects.filter(id__in=ids).update(correspondent=correspondent)
