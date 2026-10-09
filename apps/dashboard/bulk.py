"""Select-all and bulk delete for every list in the dashboard.

Every list page posts its selection here: either the ticked rows (`ids`) or "all matching"
(`scope=all`), which means every record the page's current filters match, including those beyond
the rows the page shows. The first POST renders a confirmation with the count and examples; only
the second, carrying `confirm`, deletes.

Deleting is one record at a time, for three reasons:
- a record that others still depend on (on_delete=PROTECT or RESTRICT) is skipped and reported, not allowed
  to abort the rest;
- each model's own delete() runs, so cascades behave exactly as the single-record Delete button;
- uploaded files are removed with their record. A CV or a requirements document left behind in
  private storage after its application or lead is deleted would be personal data nobody can
  find, which is the opposite of what deleting it was for.

Every bulk delete is written to the audit log, after the deletion. The audit log itself is not a
section here and cannot be deleted from the dashboard: a record of who deleted what is only worth
anything if the people it records cannot remove it. Store orders are payment records, so only a
superuser may bulk delete them.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.careers.models import JobApplication
from apps.commerce.models import Order
from apps.core.utils import log_action
from apps.estimator.models import ProjectInquiry

from . import crud, views
from .deletion import delete_with_files, file_fields
from .mixins import staff_required

# Examples shown on the confirmation page; the count is always exact.
SAMPLE_SIZE = 20

# The dashboard's own sections. The registry-driven lists (crud.REGISTRY) are added below.
# superuser_only: other staff can see the list but get 403 from bulk delete. The audit log is
# deliberately absent; see the module docstring.
SECTIONS = {
    "leads": dict(model=ProjectInquiry, title="Leads", list_url="dashboard:leads",
                  queryset=views.filtered_leads, files=["document"]),
    "applications": dict(model=JobApplication, title="Job applications", list_url="dashboard:applications_list",
                         queryset=lambda request, params: views._filtered_applications(request, params), files=["cv"]),
    "orders": dict(model=Order, title="Store orders", list_url="dashboard:orders",
                   queryset=views.filtered_orders, files=[], superuser_only=True),
}


def _section(name):
    if name in SECTIONS:
        return SECTIONS[name]
    cfg = crud.REGISTRY.get(name)
    if cfg is None:
        raise Http404
    return dict(
        model=cfg["model"], title=cfg["title"], list_url="dashboard:crud_list", list_args=[name],
        queryset=lambda request, params, cfg=cfg: crud.filtered_queryset(cfg, params),
        # Whatever FileFields the model has; deleting the record deletes what it uploaded.
        files=file_fields(cfg["model"]),
    )


def _list_url(section, filters):
    url = reverse(section["list_url"], args=section.get("list_args", []))
    return f"{url}?{filters}" if filters else url


def _selection(request, section):
    """The records chosen on the list page, re-resolved from what it posted."""
    filters = request.POST.get("filters", "")
    if request.POST.get("scope") == "all":
        return section["queryset"](request, QueryDict(filters)), filters
    ids = [i for i in request.POST.getlist("ids") if i.isdigit()]
    return section["model"].objects.filter(pk__in=ids), filters


@staff_required
@require_POST
def bulk_delete(request, section_name):
    section = _section(section_name)
    if section.get("superuser_only") and not request.user.is_superuser:
        raise PermissionDenied
    selection, filters = _selection(request, section)
    count = selection.count()
    back = _list_url(section, filters)
    if count == 0:
        messages.info(request, "Nothing was selected, so nothing was deleted.")
        return redirect(back)

    expected = request.POST.get("expected", "")
    if "confirm" not in request.POST or expected != str(count):
        # First visit, or the matching records changed since the page was confirmed (somebody
        # added or removed one): show the real count again rather than delete a different set.
        changed = "confirm" in request.POST
        sample = [str(obj) for obj in selection[:SAMPLE_SIZE]]
        return render(request, "dashboard/bulk_confirm.html", {
            "section": section, "section_name": section_name, "count": count, "back": back, "changed": changed,
            "sample": sample, "more": count - len(sample),
            "scope": request.POST.get("scope", ""), "ids": request.POST.getlist("ids"), "filters": filters,
        })

    deleted = kept = 0
    for obj in selection.iterator():
        if delete_with_files(obj, section["files"]):
            deleted += 1
        else:
            kept += 1

    log_action(request, "bulk deleted", None,
               detail=f"{section['title']}: {deleted} deleted, {kept} kept (still in use)"
                      + (f"; filters: {filters}" if filters else ""))
    if deleted:
        messages.success(request, f"Deleted {deleted} {section['title'].lower()} record{'s' if deleted != 1 else ''}.")
    if kept:
        messages.error(request, f"{kept} could not be deleted because other records still use them.")
    return redirect(back)
