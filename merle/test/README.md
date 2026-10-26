# Checking Merle against named term sheets

Runs the extraction code from `B01_app.html` in Node and compares the name it
builds with the file name the desk gave each PDF (`OK` or `DIFF`).

```
mkdir -p /tmp/merle && python3 -I merle/test/split.py merle/B01_app.html /tmp/merle
MERLE_JS=/tmp/merle V=1 node merle/test/run.js /tmp/merle/rules.json path/to/termsheets/*.pdf
```

`V=1` prints every field with its warning and source snippet; `DUMP=<dir>` also
writes the text pdf.js read from each sheet.
