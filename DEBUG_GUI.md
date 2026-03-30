# DEBUG GUI

## Purpose

This document explains how to use the local debug GUI for replay inspection.

The GUI is intended to help with:

- simulation debugging
- event log inspection
- capture trigger verification
- future gameplay visualization iteration

## File

- [debug_gui.html](/home/xincheng/toy/Chase/debug_gui.html)

## What It Shows

- built-in replay selection
- JSON file upload
- event timeline
- event scrubber
- runner / hunter carrier state cards
- raw selected-event JSON
- simplified Yamanote station strip for node-position inspection

## Recommended Launch

Use a local static server from the project root:

```bash
cd /home/xincheng/toy/Chase
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/debug_gui.html
```

## Notes

- Built-in preset loading works best when served over `http://localhost`.
- If the file is opened directly from disk, preset `fetch` may be blocked by the browser. In that case, use the file-upload control instead.
