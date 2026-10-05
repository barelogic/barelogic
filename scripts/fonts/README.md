# scripts/fonts

This directory holds `JetBrainsMono-Regular.ttf`, fetched automatically by
`.github/workflows/stats.yml` (and subset + inlined as base64 by the
generators, so viewers don't need the font installed).

To fetch locally:

```sh
mkdir -p scripts/fonts
curl -Lso scripts/fonts/JetBrainsMono-Regular.ttf \
  https://github.com/JetBrains/JetBrainsMono/raw/master/fonts/ttf/JetBrainsMono-Regular.ttf
```

Only the glyphs each graphic actually draws are embedded. The portrait grid
assumes an advance width of exactly 0.600 em.
