#!/usr/bin/env python3
# Aufruf: python3 scripts/new_entry.py [Optionen]
"""
Egons Tagebuch – Bot-Interface zum Erstellen und Veröffentlichen von Einträgen.

Verwendung:
    # Via JSON (stdin) – bevorzugte Bot-Methode:
    echo '{"title": "...", "content": "..."}' | python scripts/new_entry.py

    # Via Argumente:
    python scripts/new_entry.py --title "..." --content "..."

    # JSON aus Datei:
    python scripts/new_entry.py --json /tmp/entry.json

    # Nur Datei erstellen, NICHT pushen (für Vorschau):
    python scripts/new_entry.py --title "..." --content "..." --dry-run
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).parent.parent
CONTENT_DIR = REPO_ROOT / "content" / "posts"
TIMEZONE = ZoneInfo("Europe/Berlin")


def slugify(text: str) -> str:
    """Titel in URL-tauglichen Dateinamen umwandeln."""
    text = text.lower()
    text = re.sub(r"[äöüß]", lambda m: {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}[m.group()], text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text[:60].rstrip("-")


def build_frontmatter(title: str, date: datetime, tags: list[str], description: str) -> str:
    tags_yaml = ", ".join(f'"{t.lower()}"' for t in tags) if tags else ""
    date_str = date.strftime("%Y-%m-%dT%H:%M:%S%z")
    # Zeitzone als +HH:MM formatieren
    date_str = date_str[:-2] + ":" + date_str[-2:]

    lines = [
        "---",
        f'title: "{title}"',
        f"date: {date_str}",
        "draft: false",
    ]
    if description:
        lines.append(f'description: "{description}"')
    if tags_yaml:
        lines.append(f"tags: [{tags_yaml}]")
    lines.append("---")
    return "\n".join(lines)


def create_entry(
    title: str,
    content: str,
    tags: list[str] | None = None,
    description: str = "",
    date: datetime | None = None,
) -> Path:
    """Markdown-Datei erstellen und Pfad zurückgeben."""
    if not title.strip():
        raise ValueError("Titel darf nicht leer sein.")
    if not content.strip():
        raise ValueError("Inhalt darf nicht leer sein.")

    date = date or datetime.now(tz=TIMEZONE)
    tags = [t.strip() for t in (tags or []) if t.strip()]

    date_prefix = date.strftime("%Y-%m-%d")
    slug = slugify(title)
    filename = f"{date_prefix}-{slug}.md"
    filepath = CONTENT_DIR / filename

    if filepath.exists():
        raise FileExistsError(f"Datei existiert bereits: {filepath}")

    frontmatter = build_frontmatter(title, date, tags, description)
    full_content = f"{frontmatter}\n\n{content.strip()}\n"

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(full_content, encoding="utf-8")
    return filepath


def git_push(filepath: Path, title: str) -> None:
    """Datei committen und pushen."""
    rel_path = filepath.relative_to(REPO_ROOT)

    def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, **kwargs)
        if result.returncode != 0:
            raise RuntimeError(f"Fehler bei `{' '.join(cmd)}`:\n{result.stderr.strip()}")
        return result

    # Sicherstellen dass wir auf main sind und aktuell
    run(["git", "fetch", "origin"])
    run(["git", "pull", "--rebase", "origin", "main"])

    run(["git", "add", str(rel_path)])
    run(["git", "commit", "-m", f"Neuer Eintrag: {title}"])
    run(["git", "push", "origin", "main"])


def parse_input() -> dict:
    """Eingabe aus stdin (JSON) oder CLI-Argumenten lesen."""
    parser = argparse.ArgumentParser(description="Neuen Tagebucheintrag erstellen")
    parser.add_argument("--title", help="Titel des Eintrags")
    parser.add_argument("--content", help="Inhalt als Markdown-Text")
    parser.add_argument("--description", default="", help="Kurzbeschreibung (SEO)")
    parser.add_argument("--tags", nargs="*", default=[], help="Tags (Leerzeichen-getrennt)")
    parser.add_argument("--date", help="Datum im ISO-Format (Standard: jetzt)")
    parser.add_argument("--json", dest="json_file", help="JSON-Datei als Eingabe")
    parser.add_argument("--dry-run", action="store_true", help="Nur Datei erstellen, nicht pushen")

    args = parser.parse_args()

    # Priorität: --json Datei > stdin JSON > CLI-Argumente
    data: dict = {}

    if args.json_file:
        with open(args.json_file, encoding="utf-8") as f:
            data = json.load(f)
    elif not sys.stdin.isatty():
        try:
            raw = sys.stdin.read().strip()
            if raw:
                data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Fehler beim Parsen des JSON-Inputs: {e}", file=sys.stderr)
            sys.exit(1)

    # CLI-Argumente als Fallback / Überschreibung
    if args.title:
        data["title"] = args.title
    if args.content:
        data["content"] = args.content
    if args.description:
        data["description"] = args.description
    if args.tags:
        data["tags"] = args.tags
    if args.date:
        data["date"] = args.date

    data["dry_run"] = args.dry_run

    if not data.get("title") or not data.get("content"):
        parser.print_help()
        print("\nFehler: --title und --content sind Pflichtfelder.", file=sys.stderr)
        sys.exit(1)

    return data


def main() -> None:
    data = parse_input()

    title = data["title"]
    content = data["content"]
    description = data.get("description", "")
    tags = data.get("tags", [])
    dry_run = data.get("dry_run", False)

    # Datum parsen falls angegeben
    date = None
    if raw_date := data.get("date"):
        try:
            date = datetime.fromisoformat(raw_date)
            if date.tzinfo is None:
                date = date.replace(tzinfo=TIMEZONE)
        except ValueError:
            print(f"Ungültiges Datumsformat: {raw_date}", file=sys.stderr)
            sys.exit(1)

    try:
        filepath = create_entry(title, content, tags, description, date)
        print(f"Eintrag erstellt: {filepath.relative_to(REPO_ROOT)}")

        if dry_run:
            print("Dry-run: Kein Commit/Push.")
            return

        git_push(filepath, title)
        print(f"Veröffentlicht: '{title}' wurde nach GitHub gepusht.")
        print("GitHub Actions deployt die Seite automatisch.")

    except FileExistsError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(2)
    except RuntimeError as e:
        print(f"Git-Fehler: {e}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"Unerwarteter Fehler: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
