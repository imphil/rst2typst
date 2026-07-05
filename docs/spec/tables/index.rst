======
Tables
======

Details
=======

rst2typst supports all types of tabple syntax,
but it only accepts some attributes.


Examples
========

Grid table
----------

.. tab-set-code::

   .. literalinclude:: grid-table.rst.txt
      :language: rst

   .. literalinclude:: grid-table.typ.txt
      :language: typst

Simple table
------------

.. tab-set-code::

   .. literalinclude:: simple-table.rst.txt
      :language: rst

   .. literalinclude:: simple-table.typ.txt
      :language: typst

CSV table
---------

.. tab-set-code::

   .. literalinclude:: csv-table.rst.txt
      :language: rst

   .. literalinclude:: csv-table.typ.txt
      :language: typst

List table
----------

.. tab-set-code::

   .. literalinclude:: list-table.rst.txt
      :language: rst

   .. literalinclude:: list-table.typ.txt
      :language: typst

List table with autolayout
--------------------------

.. tab-set-code::

   .. literalinclude:: list-table-autolayout.rst.txt
      :language: rst

   .. literalinclude:: list-table-autolayout.typ.txt
      :language: typst

CSV table with autolayout
-------------------------

.. tab-set-code::

   .. literalinclude:: csv-table-autolayout.rst.txt
      :language: rst

   .. literalinclude:: csv-table-autolayout.typ.txt
      :language: typst

CSV table with "auto" keyword
-----------------------------

.. tab-set-code::

   .. literalinclude:: csv-table-auto-keyword.rst.txt
      :language: rst

   .. literalinclude:: csv-table-auto-keyword.typ.txt
      :language: typst

List table with "auto" keyword
------------------------------

.. tab-set-code::

   .. literalinclude:: list-table-auto-keyword.rst.txt
      :language: rst

   .. literalinclude:: list-table-auto-keyword.typ.txt
      :language: typst

Simple table with explicit widths
---------------------------------

.. tab-set-code::

   .. literalinclude:: simple-table-with-widths.rst.txt
      :language: rst

   .. literalinclude:: simple-table-with-widths.typ.txt
      :language: typst

Grid table with "grid" widths keyword
-------------------------------------

.. tab-set-code::

   .. literalinclude:: grid-table-with-widths.rst.txt
      :language: rst

   .. literalinclude:: grid-table-with-widths.typ.txt
      :language: typst

Simple table with an overall width
-----------------------------------

.. tab-set-code::

   .. literalinclude:: simple-table-with-overall-width.rst.txt
      :language: rst

   .. literalinclude:: simple-table-with-overall-width.typ.txt
      :language: typst

References
==========

Docutils:

* https://www.docutils.org/docs/ref/rst/restructuredtext.html#tables
* https://www.docutils.org/docs/ref/rst/directives.html#tables

Typst:

* https://typst.app/docs/reference/model/table/
