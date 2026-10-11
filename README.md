# LetsGrowMP — Murachh Civic Guide

Live: https://spikeopp.github.io/letsgrowmp/

A civic guide for Murachh Gram Panchayat (Pawai, Panna, Madhya Pradesh):

- **Murachh data** — every MGNREGA work since 2007 (estimate, spending, wage share, person-days),
  material bills paid to vendors, job-card counts, and automatically computed red flags.
- Government structure, officials and their roles, official scheme portals, a red-flag checklist,
  an RTI application drafter, and complaint channels.

## How the data stays fresh

`scraper/fetch_murachh.py` walks the public NREGASoft reports (State → District → Block → Panchayat)
and writes `data/murachh.json`. Standard-library Python only.

A GitHub Action (`.github/workflows/refresh-data.yml`) runs it every Monday and commits any changes.
Run it by hand:

```sh
python3 scraper/fetch_murachh.py
```

`src/portal.html` is the page source; `./build.sh` produces `index.html`.

Red flags are leads to check with an RTI or a site visit, not proof of wrongdoing.
