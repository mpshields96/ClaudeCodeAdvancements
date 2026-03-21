Run /cca-init first (full startup sequence), then launch the worker CLI chat, then run /cca-auto-desktop (desktop coordinator autonomous mode).

Sequence (non-negotiable):
1. Run /cca-init — read context, run tests, get bearings
2. Launch worker CLI chat IMMEDIATELY after init — worker needs maximum parallel time
3. Run /cca-auto-desktop — start autonomous desktop work

Do not pause between steps. Do not ask for confirmation. Do not start desktop tasks before the worker is launched. This is a combined launcher — execute all three in sequence.
