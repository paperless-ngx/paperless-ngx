class User:
    """
      This is a dummy django User used with our middleware to disable
      login authentication if that is configured in paperless.conf
    """
    is_superuser = True
    is_active = True
    is_staff = True
    is_authenticated = True
    has_module_perms = lambda *_: True
    has_perm = lambda *_: True

    #Must be -1 to avoid colliding with real user ID's (which start at 1)
    id = -1

    @property
    def pk(self):
      return self.id 
  
