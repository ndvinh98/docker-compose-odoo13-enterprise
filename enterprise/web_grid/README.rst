=========
Grid View
=========

.. versionadded:: 10 (?)

Limitations
===========

This view is a work in progress and may have to be expanded or altered.

* only ``date`` column fields have been tested, ``selection`` and ``many2one``
  are nominally implemented and supported but have not been tested, 
  ``datetime`` is not implemented at all.
* column cells are hardly configurable and must be numerical
* cell adjustment is disabled by default and must be configured to be enabled
* ``create``, ``edit`` and ``delete`` ACL metadata doesn't get automatically
  set on the view root due to limitations in ``fields_view_get`` 
  post-processing (there's a fixed explicit list of the view types getting 
  those attributes)

Schema
======

The grid view has its own schema and additional validation in this module. The
view architecture is:

``<grid>`` (1)
    architecture root element
    
    * mandatory ``string`` attribute
    * optional ``create``, ``edit`` and ``delete`` attributes
    * optional ``adjustment`` and ``adjust_name`` attributes

      ``adjustment`` can be either ``object`` or ``action`` to indicate
      whether a cell's adjustment should be performed through a method call
      or an action execution. ``adjust_name`` provides respectively the method
      name and the action id.

      In both cases, the adjustment parameters are provided as a
      ``grid_adjust`` context member, in the ``object`` case, the parameters
      are also provided as positional function parameters (next to an empty
      list of ids):

      ``row_domain``
        the domain matching the entire row of the adjusted cell
      ``column_field``
        the name of the column for the adjusted cell
      ``column_value``
        the value of the column for the adjusted cell
      ``cell_field``
        the measure field of the adjusted cell
      ``change``
        the difference between the old value of the cell and the adjusted one,
        may be possitive or negative

``<button>`` (0+)
    Regular Odoo action buttons, displayed in the view header
    
    * mandatory ``string`` attribute (the button label)
    * mandatory ``type`` attribute, either ``object`` or ``action``
    
      .. note:: workflow buttons are not supported

    * mandatory ``name`` attribute, either the name of the method to call, or
      the ID of the action to execute
    * optional ``context``
    
    The server callback is provided with all the record ids displayed in the 
    view, either as the ids passed to the method (``object`` button) or as 
    the context's ``active_ids`` (``action`` buttons)
    
``<field type="row">`` (1+)
    Row grouping fields, will be replaced by the search view's groupby filter
    if any.
    
    The order of ``row`` fields in the view provides their grouping depth:
    if the first field is ``school`` and the second is ``age`` the records 
    will be grouped by ``school`` first and by ``age`` within each school.
    
``<field type="col">`` (1)
    Column grouping field.
    
    The col field can contain 0+ ``<range>`` elements which specify 
    customisable column ranges. ``range`` elements have the following 
    mandatory attributes
    
    ``name``
        can be used to override the default range (the first one by default)
        through the ``grid_range`` context value
    ``string``
        the range button's label (user-visible)
    ``span``
        symbolic name of the span of all columns to display at once in the 
        view, may trigger pagination.
        
        For ``date`` fields, valid spans are currently ``week`` and ``month``.
    ``step``
        symbolic name of the step between one column and the previous/next
        
        For ``date`` fields, the only valid span is currently ``day``.
``<field type="measure">`` (1)
    Cell field, automatically accumulated (by ``read_group``).
    
    The measure field can take a ``widget`` attribute to customise its 
    display.

Server interactions
===================

Aside from optional buttons, the grid view currently calls two methods:

* ``read_grid`` (provided on all models by the module) returns almost the
  entirety of the grid's content as a dict:
  
  * the row titles is a list of dictionaries with the following keys:

    ``values`` (required)
        this maps to a dictionary with a key per ``row`` field, the values are
        *always* of the form ``[value, label]``.
    ``domain`` (required)
        the domain of any record at the source of this row, in case it's 
        necessary to copy a record during cell adjustment

  * the column titles is a list of dictionaries with at least one key:

    ``values`` (required)
        see row title values
    ``domain`` (required)
        see column domain value
    ``current`` (optional)
        boolean, marks/highlights a column

  * the grid data as a list (of rows) of list (of cells) of cell dicts each 
    with the following keys:
    
    ``value``
        the numeric value associated with the cell
    ``domain``
        the domain matching the cell's records (should be assumed opaque)
    ``size``
        the number of records grouped in the cell
    ``readonly`` (optional)
        a boolean indicating that this specific cell should not be
        client-editable
    ``classes`` (optional)
        a list of classes (as strings) to add on the cell's container (between
        the cell's TD and the cell's potentially-editable element).

        In case of conflicts between this list and the base classes (prefixed
        with ``o_grid_cell_``), the classes in this list are ignored.

    Note that the grid data is *dense*, if querying the database yields no
    group matching a cell a cell will generate an "empty" cell with default
    values for required keys.
  * ``prev`` and ``next`` which can be either falsy (no pagination) or a
    context item to merge into the view's own context to ``read_grid`` the 
    previous or next page, it should be assumed to be opaque

* ``read_grid_domain(field, range)`` (provided on al models by the module)
  returns the domain matching the current configured "span" of the grid. This
  is also done internally by ``read_grid``, but can be useful or necessary to
  call independently to use with separate e.g. ``search_count`` or
  ``read_group``.

* ``adjust_grid``, for which there currently isn't a blanket implementation
  and whose semantics are likely to evolve with time and use cases

Server Hooks
============

``read_grid`` calls a number of hooks allowing the customisation of its
operations from within without having to override the entire method:

``_grid_format_cell(group, cell_field)``
    converts the output of a read_group (group-by-group) into cells in the
    format described above (as part of "the grid data")
``_grid_make_empty_cell(row_domain, column_domain, view_domain)``
    generates an empty version of a cell (if there is no corresponding group)
``_grid_column_info(name, range)``
    generates a ColumnMetadata object based on the column type, storing values
    either returned directly (as part of ``read_grid``) or used query and
    reformat ``read_group`` into ``read_grid``:

    ``grouping``
        the actual grouping field/query for the columns
    ``domain``
        domain to apply to ``read_group`` in case the column field is
        paginated, can be an empty list
    ``prev`` and ``next``
        context segments which will be sent to ``read_grid`` for pages before
        and after the current one. If ``False``, disables pagination in that
        direction
    ``values``
        column values to display on the "current page", each value is a
        dictionary with the following keys:

        ``values``
            dictionary mapping field names to values for the entire column,
            usually just ``name`` -> a value
        ``domain``
            domain matching this specific column
        ``is_current``
            ``True`` if the current column should be specifically outlined in
            the grid, ``False`` otherwise
        ``format``
            how to format the values of that column/type from ``read_group``
            formatting to ``read_grid`` formatting (matching ``values`` in
            ColumnInfo)

ACL
===

* if the view is not editable, individual cells won't be editable
* if the view is not creatable, the ``Add a Line`` button will not be 
  displayed (it currently creates a new empty record)

Context Keys
============

``grid_range``
    selects which range should be used by default if the view has multiple 
    ranges
``grid_anchor``
    if applicable, used as the default anchor of column ranges instead of 
    whatever ``read_grid`` defines as its default.
    
    For date fields, the reference date around which the initial span will be
    computed. The default date anchor is "today" (in the user's timezone)
