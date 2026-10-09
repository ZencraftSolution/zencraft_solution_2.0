"""Deleting a record from the dashboard, files included.

Shared by the single Delete button (crud.crud_delete) and bulk delete (bulk.py) so the two cannot
drift apart. A record's uploaded files are removed after the record itself is: a CV, a
requirements document or a team photo left in storage after its record is gone is data nobody
can find any more, which is the opposite of what deleting it was for.
"""

from django.db import models, transaction


def file_fields(model):
    """The names of a model's file and image fields."""
    return [f.name for f in model._meta.get_fields() if isinstance(f, models.FileField)]


def delete_with_files(obj, fields=None):
    """Deletes the record, then its files. Returns False, deleting nothing, if other records
    still depend on it (on_delete=PROTECT or RESTRICT).

    `fields` limits which file fields are cleaned up; by default, all of the model's.
    """
    names = file_fields(type(obj)) if fields is None else fields
    files = [getattr(obj, name) for name in names if getattr(obj, name, None)]
    try:
        with transaction.atomic():
            obj.delete()
    except (models.ProtectedError, models.RestrictedError):
        return False
    for stored in files:
        stored.delete(save=False)
    return True
