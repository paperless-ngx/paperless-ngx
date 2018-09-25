class Renderable:
    """
    A handy mixin to make it easier/cleaner to print output based on a
    verbosity value.
    """

    def _render(self, text, verbosity):
        if self.verbosity >= verbosity:
            print(text)
