==========
Hyperlinks
==========

Details
=======

reStructuredText supports several types of hyperlink targets as documented in the `docutils reference <https://www.docutils.org/docs/ref/rst/restructuredtext.html#hyperlink-targets>`_:

1. **External hyperlink targets**: Links to external URLs
2. **Internal hyperlink targets**: Links to explicit targets within the document
3. **Indirect hyperlink targets**: Aliases that point to other targets
4. **Implicit hyperlink targets**: Automatically created from section titles
5. **Anonymous hyperlink targets**: Targets matched by position using double underscores

Examples
========

External hyperlink targets
---------------------------

External hyperlink targets link to URLs outside the document.

.. tab-set-code::

   .. literalinclude:: external.rst.txt
      :language: rst

   .. literalinclude:: external.typ.txt
      :language: typst

Internal hyperlink targets
---------------------------

Internal hyperlink targets create anchors within the document that can be referenced.

.. tab-set-code::

   .. literalinclude:: internal.rst.txt
      :language: rst

   .. literalinclude:: internal.typ.txt
      :language: typst

Indirect hyperlink targets
---------------------------

Indirect hyperlink targets are aliases that point to other targets, allowing multiple names for the same destination.

.. tab-set-code::

   .. literalinclude:: indirect.rst.txt
      :language: rst

   .. literalinclude:: indirect.typ.txt
      :language: typst

Anonymous hyperlink targets
----------------------------

Anonymous hyperlink targets use double underscores and are matched to references in order of appearance.

.. tab-set-code::

   .. literalinclude:: anonymous.rst.txt
      :language: rst

   .. literalinclude:: anonymous.typ.txt
      :language: typst

References
==========

Docutils:

* https://www.docutils.org/docs/ref/rst/restructuredtext.html#hyperlink-targets

Typst:

* https://typst.app/docs/reference/model/link/
