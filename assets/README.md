# assets

Drop your photo here as `assets/portrait.jpg` (or `.png`), then run:

```sh
pip install -r requirements.txt
python scripts/make_portrait.py --input assets/portrait.jpg --output ascii.svg
```

Without a photo, `make_portrait.py` renders a procedural placeholder so the
README layout can still be reviewed.
