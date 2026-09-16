# macOS audio capture helpers (CoreAudio, C)

Built 16 September 2026 while capturing the State of the Union live. All three are small CoreAudio
programs in C. They are C, not Swift, because `swiftc` in the installed Command Line Tools was out of
sync with the macOS 26 SDK and could not build anything that imports Foundation.

| Source | What it does |
|---|---|
| `bhrec.c` | Records a CoreAudio input device (default `BlackHole 2ch`) to stdout as raw float32 stereo PCM through an AudioQueue. `capture_live_audio.py` pipes it into ffmpeg for resampling and segmenting. |
| `mkmulti.c` | Creates a Multi-Output Device ("Brubru Capture (Multi-Output)": every real output plus BlackHole) and makes it the default output, so you hear the stream and BlackHole receives a copy. Pass the name of the output you listen on as the clock master, e.g. `mkmulti "MacBook Pro Speakers"`. Add `only` to build it from that output and BlackHole alone, so earphones do not also play through the speakers: `mkmulti "External Headphones" only`. |
| `setout.c` | Sets the default output device by name, e.g. `setout "BlackHole 2ch"` to capture silently. |

**Why `bhrec` exists:** ffmpeg's `avfoundation` audio input silently drops about 12% of the audio
(it keeps a single pending buffer, and a block that arrives before the previous one is read replaces it).
Measured: segments closing every 300 wall seconds held 257 to 265 seconds of audio. Queue size, native
sample rate and freeing the CPU made no difference. The AudioQueue path delivers complete 300.0-second
segments.

**Muting the player mutes the capture.** Muting in the browser silences the stream at its source. To
capture without hearing it, run `setout "BlackHole 2ch"` and leave the player unmuted.

Build any of them with:
`clang -O2 -o <name> <name>.c -framework AudioToolbox -framework CoreAudio -framework CoreFoundation`
