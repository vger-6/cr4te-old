# cr4te-old

This repository contains an earlier development codebase for **cr4te**.

The current repository is available at:

https://github.com/vger-6/cr4te

This repository is kept for historical reference only and is not actively maintained.

![Version](https://img.shields.io/badge/version-0.0.1-blue.svg)
[![License](https://img.shields.io/badge/license-NonCommercial-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10+-yellow.svg)

> **⚠️ Under Construction**
> This project is still in development. Features, structure, and configuration may change without notice.

cr4te scans your local folder structure, automatically detects images, videos, audio tracks, documents, and Markdown files, generates thumbnails, and builds a beautiful, responsive, searchable HTML gallery site — no database or server required.

Ideal for artists, musicians, filmmakers, photographers, writers, or anyone with a large personal media archive.

[View example gallery →](info/SCREENSHOTS.md)

## Features

* Automatic gallery generation from your existing folder hierarchy
* Support for **images**, **videos**, **audio playlists**, **PDFs**, and **Markdown** content
* Built-in **search**, **tags**, **pagination**, and **lightbox**
* Two responsive image gallery layouts (justified + fixed-aspect)
* Theme switcher (dark themes included)
* Domain-specific presets (`film`, `music`, `book`, `model`, `art`)
* Clean, customizable HTML output with no runtime dependencies

## Example Folder Structure

cr4te works with a simple nested structure:

```text
Creators/
├── Noomi/
│   ├── portrait.jpg
│   ├── Project Alpha/
│   │   ├── cover.jpg
│   │   ├── track01.mp3
│   │   ├── image01.jpg
│   │   └── README.md
│   └── cr4te.json          # auto-generated + editable
├── Bob & Charlie/          # collaborations supported
│   └── Joint Project/
└── ...
```

This works naturally for:

* Directors → Movies
* Musicians → Albums
* Authors → Books
* Artists → Projects
* etc.

## Installation

```bash
git clone https://github.com/vger-6/cr4te.git
cd cr4te
pip install -e .
```

Or install from the `pyproject.toml` dependencies manually.

## Quick Start

```bash
# Build JSON metadata + HTML site
cr4te build -i path/to/your/creators -o path/to/output/website

# Open the result immediately
cr4te build -i path/to/your/creators -o path/to/output/website --open
```

> Note: The build command will delete the output folder if it exists (use `--force` to skip confirmation).

## Useful Commands

```bash
cr4te build --domain film            # Use film-specific labels and defaults
cr4te build --config myconfig.json   # Load custom configuration
cr4te print-config                   # Show current (merged) configuration
cr4te clean-json -i path/to/creators # Remove all cr4te.json files
```

## Configuration

cr4te ships with sensible defaults. You can override labels, media ordering, gallery behavior, and more with a JSON config file:

```bash
cr4te print-config > my_config.json
```

Then pass it with `--config my_config.json`.

Editable fields in each `cr4te.json` (auto-generated in your creator folders):

* `tags`, `info` (Markdown supported)
* `aliases`, `nationality`
* `projects[].info`, `projects[].tags`, `projects[].release_date`
* `person.date_of_birth`, `person.civil_name`, etc.
* Collaboration members and dates

## Output

The generated site includes:

* `index.html` — Creator overview with search
* `projects.html` — All projects overview
* `tags.html` — Browse by tags
* Responsive galleries with lightbox and pagination
* Audio players with playlists
* Video players with controls
* Embedded PDFs and Markdown content

## Troubleshooting

### localStorage issues on file://

Some browsers block `localStorage` when opening files directly.

**Solution:** Serve the output folder locally:

```bash
cd path/to/output/website
python3 -m http.server 8000
```

Then visit [http://localhost:8000](http://localhost:8000).

### Other issues

* Make sure the output directory is writable.
* Run with `--force` if you want to skip confirmation prompts.

## License

This software is provided for personal, educational, and non-commercial purposes only.

See LICENSE for details.

Commercial use requires written permission from the author.

---

Contributions, feedback, and bug reports are welcome!
