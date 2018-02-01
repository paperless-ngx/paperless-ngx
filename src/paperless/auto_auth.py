from django.contrib.auth.models import User

class User:
    is_superuser = True
    is_active = True
    is_staff = True
    id = 1

def return_true(*args, **kwargs):
    return True
User.has_module_perms = return_true
User.has_perm = return_true

class Middleware(object):
    def process_request(self, request):
        request.user = User()
