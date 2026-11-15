# Public redactions in this release copy

Eight sprint records are hash-pinned by other files, or were checked byte for byte, and they contain local paths or internal session IDs. The public branch does not carry those originals. Each one is replaced by a visibly separate `.public-redacted` copy that has its own hash. In it, personal paths become `~/` or repo-relative and session IDs become placeholders. JSON copies also gain a `_public_redaction` key. The authentic originals, their recorded hashes and the evidence behind them stay local and unchanged.

Hash pins in the published files still name the originals. They include `pack_sunday.py`, `build_watchlist.py`, the watchlist JSON, `claude_review.json`, `ENGINE_HANDOFF.md` and `pdf_export/DELIVERY.md`. Tools and repros that read these records need the local originals.

| Original (kept local) | Original sha256 | Public copy | Public copy sha256 |
|---|---|---|---|
| `nfl/slate/experiment/EVALUATION.md` | `ecbf6cf348ea394171abb2287554895997707d8775b09eafc2fa538d628b9bcd` | `nfl/slate/experiment/EVALUATION.public-redacted.md` | `c4de92caed6ae0157b6c1d23bb4d0e22a94ee4deda2c37b261ccdab6a56d4964` |
| `nfl/slate/results/sunday_20261115_review_evidence.json` | `6b99a7662178f58ece05fe029dd8a92725c16345ff15469acb84b9ba19477604` | `nfl/slate/results/sunday_20261115_review_evidence.public-redacted.json` | `d753f240e110645053f0ad08780d4e158a26d05363426485d179f2e14ace3913` |
| `nfl/slate/results/sunday_20261115_selections.json` | `519c9506d143113ff7cb1334e496dbd987d6c1935bc45ebdf5df445ad51ffdd3` | `nfl/slate/results/sunday_20261115_selections.public-redacted.json` | `b98c0a4be33131ca4faa32dd7218756049ab1c4b54cc98bf4a4085f82ae6f1b4` |
| `nfl/slate/results/sunday_20261115_watchlist.issued_2026-11-15T073826Z.json` | `155a4e84da6ff16c57135bafff7832658a44be6988246c02a19f20f0b72325b4` | `nfl/slate/results/sunday_20261115_watchlist.issued_2026-11-15T073826Z.public-redacted.json` | `64e8c778db612b4ac3a1d3ed6e2d56144307d05aebdf30df5ec2cd9fccefac59` |
| `nfl/slate/results/sunday_20261115_watchlist.json` | `60f4a1c5c77a1d5f34321ad8af62df80a4f5a0ef0506a4ee43be40e4abc2249e` | `nfl/slate/results/sunday_20261115_watchlist.public-redacted.json` | `099c0b153c3d603d905b37b247fba6fe792281e12a8889292e9d61ae04ed1b40` |
| `review/PKT-7069f9b05f2a/claude_review_raw.txt` | `ba47bad237734d52d0f43cf5cb41b992b8cf213b67917e7bbc10f10a35150c81` | `review/PKT-7069f9b05f2a/claude_review_raw.public-redacted.txt` | `e7dcd2a7881f566a27bcd8fcf0a90bec81e8eb5d9735f1ee4c385ffcca64a9cb` |
| `review/PKT-7069f9b05f2a/inputs/PROMPT.txt` | `7e914ae488bfeeb3b7ac19830f86c7772cd74d9d3d0da9b2ce4f75f445f74d50` | `review/PKT-7069f9b05f2a/inputs/PROMPT.public-redacted.txt` | `de3bb80b7d6cf803f65ba9c8da80dd48cfe73769341ab2a9b5463e03645c9a6b` |
| `review/PKT-7069f9b05f2a/inputs/MANIFEST.json` | `9c81dc70e92913085b618c1800f9ef8ef85645b96b5759ec9fb4152a8693ff0a` | `review/PKT-7069f9b05f2a/inputs/MANIFEST.public-redacted.json` | `a021ebd25934f0f540f53f5cb386bf5d9f54f479093b5857ee1f983afe46dd17` |

The three published PDFs were checked: their metadata and decoded content streams hold no personal paths or session IDs, so they are unchanged.
