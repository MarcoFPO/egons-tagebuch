#!/usr/bin/env python3
import json
import sys
import os
from datetime import datetime

def generate_slug(title: str) -> str:
    import re
    slug = re.sub(r'[\W_]+', '-', title.lower().strip())
    return slug

def parse_cli_args(args):
    """Parse CLI arguments like --title "..." --content "..." --tags tag1 tag2 --dry-run"""
    data = {
        'title': '',
        'content': '',
        'tags': [],
    }
    i = 1  # Skip script name
    while i < len(args):
        arg = args[i]
        if arg == '--title' and i + 1 < len(args):
            data['title'] = args[i + 1]
            i += 2
        elif arg == '--content' and i + 1 < len(args):
            data['content'] = args[i + 1]
            i += 2
        elif arg == '--tags':
            # Tags continue until next flag or end
            i += 1
            while i < len(args) and not args[i].startswith('--'):
                data['tags'].append(args[i])
                i += 1
        elif arg == '--dry-run':
            i += 1
        else:
            # Unknown arg, skip
            i += 1

    return data

def main():
    dry_run = False

    if len(sys.argv) > 1 and sys.argv[1] == '--json':
        if len(sys.argv) > 2:
            with open(sys.argv[2], 'r') as f:
                data = json.load(f)
        else:
            data = json.load(sys.stdin)
    else:
        args = [arg for arg in sys.argv if arg != '--dry-run']
        data = parse_cli_args(args)

    if 'title' not in data or not data['title']:
        print('Error: title is required', file=sys.stderr)
        print('Usage: echo \'{"title":"..."}}\' | python3 new_entry.py', file=sys.stderr)
        print('   or: python3 new_entry.py --json file.json', file=sys.stderr)
        print('   or: python3 new_entry.py --title "..." --content "..." --tags "tag1" "tag2" --dry-run', file=sys.stderr)
        sys.exit(1)

    if 'date' not in data:
        now = datetime.now()
        data['date'] = now.strftime('%Y-%m-%dT%H:%M:%S+01:00')

    slug = generate_slug(data['title'])
    date_part = datetime.fromisoformat(data['date']).strftime('%Y-%m-%d')
    filename = f'content/posts/{date_part}-{slug}.md'

    if os.path.exists(filename):
        print(f'Error: File {filename} already exists', file=sys.stderr)
        sys.exit(2)

    md_content = f'''---
title: {data['title']}
date: {data['date']}
description: {data.get('description', '')}
tags: {data.get('tags', [])}
---

{data['content']}

---
'''

    if dry_run:
        print(f'[DRY RUN] Would create: {filename}')
        print(f'Content length: {len(md_content)} characters')
    else:
        with open(filename, 'w') as f:
            f.write(md_content)
        print(f'Eintrag erstellt: {filename}')

    sys.exit(0)

if __name__ == '__main__':
    main()
