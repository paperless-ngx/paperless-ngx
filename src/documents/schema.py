from drf_spectacular.extensions import OpenApiAuthenticationExtension


class AngularApiAuthenticationOverrideScheme(OpenApiAuthenticationExtension):
    target_class = "paperless.auth.AngularApiAuthenticationOverride"
    name = "AngularApiAuthenticationOverride"

    def get_security_definition(self, auto_schema):
        return {
            "name": "Angular Authorization",
            "description": "Automatic Angular authentication for the dev server",
        }
