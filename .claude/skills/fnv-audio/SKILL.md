---
name: fnv-audio
description: Process Fallout New Vegas voice (ogg+lip), sound effects (wav/ogg), and music (mp3) using public tools.
paths: "**/*.ogg,**/*.lip,**/*.fuz,Data/Sound/**"
---

# Audio / Voice Operations (FNV)

> **Preferred:** `bash tools/automod-cli.sh audio wav-to-ogg <in.wav> <out.ogg> --json` (24kHz mono via oggenc2, auto-detected) and `audio info` — see `docs/automod-cli.md`. `.lip` is GECK-only.
> **With the MO2 MCP running** (the mo2 MCP tools present): prefer `mo2_audio_info` (ogg/wav, VFS path) and `mo2_convert_audio` (wav→ogg into the output mod).

FNV uses **no FUZ and no XWM** (unlike Skyrim). See `KNOWLEDGEBASE.md → Audio / Voice Files`.

| Purpose | Format |
|--------|--------|
| Voice / dialogue | **`.ogg` (24 kHz, mono, ~64 kbps VBR) + `.lip`** |
| Sound effects | `.wav` (16-bit PCM safest) or `.ogg` |
| Music / radio | `.mp3` (radio also needs a `<name>_mono.ogg`) |

## Folder & filename convention (verified)
```
Data\Sound\Voice\<PluginName.esp>\<VoiceType>\<questEDID>_<topicEDID>_<INFO-FormID>_<take>.ogg  (+ .lip)
```
The 8-hex chunk is the dialogue **response `INFO` FormID** — that's how the engine maps audio→line.

## Replace / add a voice line (public tools)
1. Get the line as **WAV**, named to match the target `INFO` (the GECK fills the name when you assign audio to a response).
2. Place it in `Data\Sound\Voice\<plugin>\<voicetype>\`.
3. **Generate the `.lip`** in the GECK: install **FonixData.cdf** (`Data\sound\voice\processing\`), then in the Response panel select the audio → **`FromWav`** radio → **`GenerateLipFile`**. The WAV must be correctly named/placed or no `.lip` is produced.
4. **Encode WAV → OGG** at **24 kHz, mono, ~64 kbps VBR** — easiest is the AutoMod CLI (`audio wav-to-ogg`, via **oggenc2**). Alternatives: `oggenc2 --downmix --resample 24000 -q 1 -o out.ogg in.wav`, `ffmpeg -i in.wav -ar 24000 -ac 1 -q:a 2 out.ogg`, Audacity, or GECK Sound Converter. Ship **`.ogg` + `.lip`** (not the WAV).
5. Crackling? Re-encode to clean 16-bit PCM / OGG.

## Pack / extract
- Vanilla voice/sound in `Fallout - Voices1.bsa` / `Fallout - Sound.bsa` — extract with **BSArch** (`fnv-bsa` skill).
- **Loose files override BSA audio.** Under MO2, put new audio in `mods/<YourMod>/Sound/Voice/…` or `overwrite/`.

## TTW / FO3 note
**FO3 voice is 44.1 kHz, FNV is 24 kHz** — re-encode to 24 kHz when porting FO3 voice to FNV/TTW.
