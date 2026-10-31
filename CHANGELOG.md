# Changelog

## 1.1.0 - 2026-10-31
- Interface language: Russian / English, switch in the right-click menu (default follows the Windows language).
- Layout and shape are now stored as language-independent ids; settings from 1.0.0 are migrated automatically.
- Overheat protection: red pulsing frame, tray notification, optional sound, thresholds in the right-click menu. Action at a critical temperature: only warn (default), reduce CPU power to 50% until cooled, hibernate or shut down with a cancellable 30 s countdown.
- Russian README (`README.ru.md`) and language links.

## 1.0.0 - 2026-10-31
- First public release.
- Readings: CPU/GPU temperature, CPU/GPU load, RAM usage, drive temperatures.
- 10 layouts (including the 8GadgetPack-style speedometer with temperature in the hub), 14 themes, 5 shapes, one-click presets.
- Size 20-100% (Ctrl + mouse wheel), horizontal or vertical arrangement, opacity, always-on-top, tray icon.
- Hover hint with the name and value of the metric under the cursor.
- Optional system cleaner (temp files, caches, recycle bin) - runs only on request.
- Windows installer (Inno Setup) with license, description, autostart and PawnIO driver options.
