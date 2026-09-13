from .crud import nav_groups


def dashboard_nav(request):
    return {"crud_groups": nav_groups()}
