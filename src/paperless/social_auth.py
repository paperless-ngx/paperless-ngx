from paperless.models import SSOGroup


def update_groups(response, user, *args, **kwargs):
    # This works at least for openidconnect, if you want to implement new SSO
    # you need to check that groups are strings in the list "groups"

    # Search all existing groups associated with sso groups
    sso_groups = set()
    for group in response.get("groups", []):
        for g in SSOGroup.objects.filter(name__exact=group):
            sso_groups.add(g.group)
    # Extract current sso groups currently connected to the user
    actual_sso_groups = set()
    for group in user.groups.filter(sso_groups__isnull=False):
        if group.sso_groups.count() != 0:
            for sso_group in group.sso_groups.all():
                actual_sso_groups.add(sso_group.group)
    # Add missing groups
    for g in sso_groups - actual_sso_groups:
        g.user_set.add(user)
    # Remove groups which are connected to a sso group, but not connected
    # anymore
    for g in actual_sso_groups - sso_groups:
        g.user_set.remove(user)
