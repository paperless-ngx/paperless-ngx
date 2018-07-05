import base64
import binascii
import datetime
import os
import shutil
from functools import wraps
from sys import getfilesystemencoding
from urllib.parse import unquote_plus

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.contrib.auth import authenticate

from djangodav.base.resources import MetaEtagMixIn, BaseDavResource
from djangodav.utils import url_join
from djangodav.views import DavView

from documents.models import Tag, Document, Correspondent


def extract_basicauth(authorization_header, encoding='utf-8'):
    splitted = authorization_header.split(' ')
    if len(splitted) != 2:
        return None

    auth_type, auth_string = splitted

    if 'basic' != auth_type.lower():
        return None

    try:
        b64_decoded = base64.b64decode(auth_string)
    except (TypeError, binascii.Error):
        return None
    try:
        auth_string_decoded = b64_decoded.decode(encoding)
    except UnicodeDecodeError:
        return None

    splitted = auth_string_decoded.split(':')

    if len(splitted) != 2:
        return None

    username, password = map(unquote_plus, splitted)
    return username, password


def validate_request(request):

    if 'HTTP_AUTHORIZATION' not in request.META:
        return False

    authorization_header = request.META['HTTP_AUTHORIZATION']
    ret = extract_basicauth(authorization_header)
    if not ret:
        return False

    username, password = ret

    user = authenticate(username=username, password=password)

    if user is None:
        return False

    request.META['REMOTE_USER'] = username
    return True


class HttpResponseUnauthorized(HttpResponse):
    status_code = 401

    def __init__(self):
        super(HttpResponseUnauthorized, self).__init__(
            """<html><head><title>Basic auth required</title></head>
               <body><h1>Authorization Required</h1></body></html>""",
        )
        realm = 'Paperless WebDAV'
        self['WWW-Authenticate'] = 'Basic realm="{}"'.format(realm)


def basic_auth_required(func=None,
                        target_test=(lambda request: True)):
    def actual_decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if target_test(request) and not validate_request(request):
                return HttpResponseUnauthorized()
            return view_func(request, *args, **kwargs)
        return _wrapped

    if func:
        return actual_decorator(func)
    else:
        return actual_decorator

#@method_decorator(basic_auth_required, name='dispatch')
class SecuredDavView(DavView):
    pass

class PaperlessDavResource(MetaEtagMixIn, BaseDavResource):

    document = None

    def __init__(self, path, **kwargs):
        super(PaperlessDavResource, self).__init__(path)
        self.documents, self.document, self.children = parse_path(path)

    @property
    def getcontentlength(self):
        if self.document:
            return os.path.getsize(self.document.source_path)
        else:
            return None

    def get_created(self):
        """Return the create time as datetime object."""
        if self.document:
            return self.document.created
        else:
            return None

    def get_modified(self):
        if self.document:
            return self.document.modified
        else:
            return None

    @property
    def is_collection(self):
        return not self.document

    @property
    def is_object(self):
        return self.document

    @property
    def exists(self):
        return True

    def get_children(self):
        if not self.document:
            for child in self.children:
                yield PaperlessDavResource(url_join(*(self.path + [child])))

            for doc in self.documents:
                yield PaperlessDavResource(url_join(*(self.path + [doc.title])), document=doc)

    def write(self, content, temp_file=None):
        raise NotImplementedError

    def read(self):
        print("calling read!!!")
        return self.document.source_file

    def delete(self):
        raise NotImplementedError

    def create_collection(self):
        raise NotImplementedError

    def copy_object(self, destination, depth=0):
        raise NotImplementedError

    def move_object(self, destination):
        raise NotImplementedError

def parse_path(path):
    used_tags = []
    used_correspondents = []
    year_selected = False
    month_selected = False
    day_selected = False
    show_documents = True

    def get_filter_children():
        filters = []
        if not year_selected:
            filters.append('year')
        elif not month_selected:
            filters.append('month')
        elif not day_selected:
            filters.append('day')
        filters.append('correspondent')
        filters.append('tag')
        return filters

    path_queue = [x for x in path.split('/') if x]

    filter = Document.objects.all()
    children = get_filter_children()
    document = None

    current_rule = 'select_filter'

    print("path",path_queue)
    while len(path_queue) > 0:
        path_segment = path_queue.pop(0)
        # 1. check if path_segment exists / is allowed
        # 2. determine what path_segment does
        # 3. determine

        print("segment", path_segment)
        print("rule   ", current_rule)
        print("---")

        if current_rule == 'select_filter':
            show_documents = False
            if path_segment == 'year':
                next_rule = 'select_year'
                children = [str(d.year) for d in filter.dates('created', 'year')]
            elif path_segment == 'month':
                next_rule = 'select_month'
                children = [str(d.month) for d in filter.dates('created', 'month')]
            elif path_segment == 'day':
                next_rule = 'select_day'
                children = [str(d.day) for d in filter.dates('created', 'day')]
            elif path_segment == 'correspondent':
                next_rule = 'select_correspondent'
                children = [c.name for c in Correspondent.objects.all()]
            elif path_segment == 'tag':
                next_rule = 'select_tag'
                children = [t.name for t in Tag.objects.all()]
            else:
                next_rule = 'document'
                children = []
                document = Document.objects.get(title=path_segment)
        elif current_rule == 'select_tag':
            next_rule = 'select_filter'
            filter = filter.filter(tags__name=path_segment)
            used_tags.append(path_segment)
            children = get_filter_children()
            show_documents = True
        elif current_rule == 'select_correspondent':
            next_rule = 'select_filter'
            filter = filter.filter(correspondent__name=path_segment)
            used_tags.append(path_segment)
            children = get_filter_children()
            show_documents = True
        elif current_rule == 'select_year':
            next_rule = 'select_filter'
            filter = filter.filter(created__year=path_segment)
            year_selected = True
            children = get_filter_children()
            show_documents = True
        elif current_rule == 'select_month':
            next_rule = 'select_filter'
            filter = filter.filter(created__month=path_segment)
            month_selected = True
            children = get_filter_children()
            show_documents = True
        elif current_rule == 'select_day':
            next_rule = 'select_filter'
            filter = filter.filter(created__day=path_segment)
            day_selected = True
            children = get_filter_children()
            show_documents = True
        else:
            raise ValueError()

        current_rule = next_rule

    print("ok")
    print("children", children)
    return filter if show_documents else [], document, children