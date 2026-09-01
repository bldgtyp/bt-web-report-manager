# v0.0.25

PDF -> PNG crash fix.

- Dropping more than one PDF on the **PDF -> PNG** modal no longer quits the
  Manager. NiceGUI raises one upload handler per file, and the converter used
  to run each on its own thread; PDFium is not thread-safe, so concurrent
  renders corrupted its heap and aborted the process before any PNG was
  written.
- Conversions now queue onto a single dedicated PDFium worker thread. A
  multi-file drop processes in order rather than in parallel, at no measurable
  cost: six floor plans convert in about 1.5 seconds either way.
- The action log now reads `Queued <file>` on arrival, so a file waiting its
  turn does not look like one that stalled mid-render.
