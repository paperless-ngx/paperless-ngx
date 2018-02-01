from django.contrib.auth.models import User

'''
  This is a dummy authentication middleware module that creates what 
  is roughly an Anonymous authenticated user so we can disable login
  and not interfere with existing user ID's.
'''

class User:
    is_superuser = True
    is_active = True
    is_staff = True
    is_authenticated=True
    id = -1 #Must be -1 to avoid colliding with possible existing user ID's (that start number at 1)
    pk = -1

def return_true(*args, **kwargs):
    return True
User.has_module_perms = return_true
User.has_perm = return_true

class Middleware(object):
    def process_request(self, request):
        request.user = User()
