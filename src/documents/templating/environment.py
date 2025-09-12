from jinja2.sandbox import SandboxedEnvironment


class JinjaEnvironment(SandboxedEnvironment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.undefined_tracker = None

    def is_safe_callable(self, obj):
        # Block access to .save() and .delete() methods
        if callable(obj) and getattr(obj, "__name__", None) in (
            "save",
            "delete",
            "update",
        ):
            return False
        # Call the parent method for other cases
        return super().is_safe_callable(obj)


_template_environment = JinjaEnvironment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
    autoescape=False,
    extensions=["jinja2.ext.loopcontrols"],
)
