# Frontend Maintainability Notes

This project keeps frontend code simple and framework-free for easier learning.

## Current Structure

- `static/app.js`: main bootstrap, DOM wiring, socket event handlers.
- `static/socket_loader.js`: isolated dynamic loading logic for Socket.IO script candidates.
- `static/i18n.js`: locale dictionary and `createI18n()` translator factory.
- `static/upload_flow.js`: upload UI item state and `/ui/upload` transport orchestration.
- `static/file_preview.js`: file preview and context-menu helpers.
- `static/message_renderer.js`: message normalization, de-dup and render flow.
- `static/message_view.js`: thin composition layer for message modules.
- `templates/index.html`: script load order and DOM skeleton.

## Why Split `socket_loader.js`

The dynamic script loading path is operationally important but conceptually separate from UI behavior.
Splitting it provides:

- Smaller cognitive scope when reading `app.js`.
- A single place to maintain CDN fallback candidates.
- Reusable loader behavior for future pages.
- Lower-risk first step before larger frontend modularization.

## Design Rules

- Keep runtime behavior unchanged during refactors.
- Isolate one responsibility per file whenever possible.
- Favor explicit dependencies via function parameters (`log`, `logError`) over hidden globals.
- Keep script order explicit in `index.html`.

## Next Suggested Split Steps

1. Add lightweight browser smoke checks for script boot order and socket bootstrap.
2. Consider a tiny integration test for upload placeholder replacement and de-dup rendering.
3. Keep module contracts explicit (document required deps for each `create*` factory).




