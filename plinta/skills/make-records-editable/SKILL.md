---
name: make-records-editable
description: Let people write data through plinta — an editable cell, a record form, an Add button. Use when a screen should change data rather than only show it. Not for adding a column (a DataSourceField) or a new widget (a component).
---

# Make records editable

Nothing in plinta is writable until three separate people say so, and all three
must agree. This is the order to do them in.

## 1. The author opens the column

Set `editable` on the `DataSourceField`. Saving the row **mints its change
permission automatically** — a signal does it, so there is no sync step and no
migration.

```
Book.title  editable ✓   →  mints  change_book_title
```

Untick it and the permission is deleted, along with every grant on it. That is
deliberate: a grant that no longer means anything is worse than none.

**A traversal is never writable.** `region__name` names a column on another
row, and writing it would mean deciding which row — so it stays read-only
however it is declared.

## 2. An administrator grants it

Two levels, and both are required:

- the model — `change_book`, and `add_book` if anyone is to create one
- the column — `change_book_title`, `change_book_region`, …

A create is authorised as **add**, not change: somebody who may edit every book
still may not make one.

## 3. Relations need a third grant

A picker offers only rows the viewer may **see**, and the write resolves
against that same list — so a column pointing at `Region` needs
`view_region` as well. Without it the dropdown is empty and the save refuses,
which is correct and looks like a bug if you have not read this.

Set `picker_mode` if the default is wrong: `auto` offers a list at or under a
hundred rows and a search above.

## Then pick how it is edited

| | |
|---|---|
| **A form on a detail page** | a `form_plinta` block on a page whose `page_type` is `detail` |
| **A pencil on each row** | `row_form: true` on a `table_tabulator` block — opens the same form in a dialog |
| **An Add button** | automatic on any card whose model the viewer may `add` |
| **A cell edited in place** | `editable: true` on `table_tabulator`. Core's `table_plinta` is server-rendered and does neither |

The first three are the same form and the same endpoint; only the trigger
differs, and none of them decides what may be written.

## What the viewer gets

**"View mode" is not a setting.** A form draws every column the viewer may
*see* and offers the ones they may *change*. Somebody holding `view` and not
`change` gets the record shown, formatted, with no controls and no submit
button. Give them `change_book_title` and that one field becomes editable.

So there is one block, one layout and one URL for reading and writing, and the
permissions decide.

## What to expect when it refuses

| | |
|---|---|
| **405** | the component does not write at all — a chart has nowhere to put an edit |
| **403** | a refusal: this field or this row, and no value will change that |
| **422** | a rejection, naming the fields: fix the value and it will |

A many-to-many is refused **whole** if any of the chosen rows is not
choosable — taking the permitted ones would report a success for a write
nobody asked for.

A value the field cannot hold — a name typed where a pk belongs — is a 422 and
never a 500.

## Related

- `add-form-layout` — arrange a form's fields your own way
- `add-component` — a widget that writes something a form does not
