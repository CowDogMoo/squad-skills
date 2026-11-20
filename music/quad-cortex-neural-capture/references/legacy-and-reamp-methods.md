# Legacy and reamp methods

Both are superseded by the one-pass QC-over-USB method. Use them only under
the stated conditions, and never propose either unprompted.

## Legacy: two cables, two passes (before 2026-08-24)

Earlier comparisons used guitar → RME In 3 for a plugin pass and guitar →
QC → RME In 4 for a QC pass, as separate performances.

Those charts are different-performance long-term spectra only. They remain
valid for cab and EQ balance but say nothing about drive. Pair takes by
timestamp, trim to the active region, and average dual-mono to mono. Old
two-cable takes have one silent channel per take by design — do not
diagnose them.

Only use this method if the QC USB path is unavailable.

## Optional: reamp

Only if the user asks; the USB method makes it unnecessary.

1. Record a DI once: guitar → RME In 3, no plugin.
2. Reamp that DI at matched level into the plugin — DI clip → plugin track,
   record Post FX.
3. Reamp the same DI into the QC: DI clip → spare ext out → QC In 2, preset
   input block on In 2, Instrument / 1 MΩ / 0 dB.
4. Calibrate the send so the QC In 2 meter peaks match the DI file's peaks.
5. Switch the preset input back to In 1 afterwards.
