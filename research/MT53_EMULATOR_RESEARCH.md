# MT-53 Phase 1: macOS Emulator Research

## Recommendation: PyBoy (Crystal) + mGBA (Emerald)

| Game | Emulator | Scripting | Speed Control | Install |
|------|----------|-----------|---------------|---------|
| Pokemon Crystal (GBC) | **PyBoy** | Python native (`pyboy.button()`, `pyboy.memory[addr]`) | `set_emulation_speed(N)` — 0=unlimited, any multiplier | `pip install pyboy` |
| Pokemon Emerald (GBA) | **mGBA** | Lua 5.4 (`core.addKey()`, `read8/16/32()`, frame callbacks) | UI fast-forward (2x/3x/4x/unbounded) | `brew install mgba` |

## Why Not Single Emulator?
- PyBoy: GBC only, no GBA support (Emerald impossible)
- mGBA: handles both GBA+GBC but scripting is Lua-only (no Python API)
- Best path: Python bot core, PyBoy native API for Crystal, mGBA via Lua for Emerald

## Eliminated Options
- **BizHawk**: macOS not supported (Windows+Linux only)
- **OpenEmu**: Beautiful macOS UI but zero scripting API
- **RetroArch**: No RAM read API, only basic stdin/UDP commands

## Key PyBoy Features
- `pyboy.game_wrapper()` provides high-level Pokemon-specific API (HP, coordinates, opponent data)
- Headless mode for max speed (395x achievable)
- Multiple instances supported
- Apple Silicon native (ARM64 wheel)

## Key mGBA Features
- Lua scripting since v0.10.0
- macOS universal binary, Metal acceleration
- Socket API for Python↔Lua bridge
- Save state support for bot checkpointing

## Next Steps (Phase 1 continued)
- [ ] Reddit/GitHub scan for existing AI Pokemon bot projects (Matthew directive S189)
- [ ] Download PyBoy, test Crystal ROM loading + basic input
- [ ] Download mGBA, test Emerald ROM loading + Lua script execution
- [ ] Map RAM addresses for Crystal (party, HP, location, badges)
- [ ] Map RAM addresses for Emerald (same)

## Sources
- PyBoy: https://github.com/Baekalfen/PyBoy | https://docs.pyboy.dk/
- mGBA: https://mgba.io/ | https://mgba.io/docs/scripting.html
- mGBA Lua scripting: https://gbatemp.net/threads/620256/
