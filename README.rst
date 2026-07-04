=========
rst2typst
=========

Converter from DocTree of docutils to Typst source and PDF.

Overview
========

rst2typst is Python project that includes docutils custom writer and frontend CLI.

I develop this for two purposes:

* To generate PDF documentation from reStructuredText rapidly.
* To work as core of atsphinx-typst that it is Sphinx extension to generate PDF file on Sphinx lifecycle.

I will use this and atsphinx-typst to generate documentation PDF files of my Python projects.

Benchmark
=========

**rst2typstpdf is about 53.5x faster** than rst2latex+pdflatex
when including the installation of TeX Live (1.7 s vs 92.3 s).

For full details, see `Benchmark in the documentation <https://rst2typst.attakei.dev/#benchmark>`_.

Usage
=====

Use CLI
-------

You write reStructuredText source to generate for PDF using Typst.
(e.g. this filename is ``document.rst``.)

.. code:: rst

   ==================
   rst2typst document
   ==================

   Overview
   ========

   We like reStructuredText! It is an one of great docutils.

   * This has custom writer of docutils.
   * This has CLI endpoint named ``rst2typst`` and ``rst2typstpdf``.

   Usage
   =====

   Enjoy it!

You can run these command to convert to Typse code.

.. code:: console

   rst2typst document.rst document.typ

Generated `document.typ` has this content (actually this is not formated).

.. code:: typst

   #title([rst2typst document])

   = Overview

   We like reStructuredText! It is an one of great docutils.

   - This has custom writer of docutils.
   - This has CLI endpoint named `rst2typst` and `rst2typstpdf`.

   = Usage

   Enjoy it!

Use as library
--------------

(TBD)

Development
===========

Run all spec tests with PDFs for eyeballing

```
pytest tests/test_spec.py --render-spec-pdfs
```

License
=======

Apache-2.0 license. Please see LICENSE on repository.
