"""Filter widgets take the `capability_implementation` name components use.

`multiselect` becomes `multiselect_plinta`, so the plain name is free for
whoever implements it next — which is the point of the convention.

Reversible, and it renames rather than resetting: a stored widget nobody
recognises would silently draw as a text input, which looks like the filter
working and is not.
"""
from django.db import migrations

RENAMES = {
    "input": "input_plinta",
    "boolean": "boolean_plinta",
    "select": "select_plinta",
    "multiselect": "multiselect_plinta",
    "daterange": "daterange_plinta",
}


def rename(apps, schema_editor, mapping):
    PageFilter = apps.get_model("plinta_pages", "PageFilter")
    for old, new in mapping.items():
        PageFilter.objects.filter(widget=old).update(widget=new)


def forwards(apps, schema_editor):
    rename(apps, schema_editor, RENAMES)


def backwards(apps, schema_editor):
    rename(apps, schema_editor, {v: k for k, v in RENAMES.items()})


class Migration(migrations.Migration):
    dependencies = [("plinta_pages", "0003_pagefilter_data_source")]
    operations = [migrations.RunPython(forwards, backwards)]
