#!/usr/bin/env python3
"""Find and insert missing translations of Jmix messages.properties files.

Usage:
  python3 messages.py missing <locale> [--root DIR] [--module TEXT ...] [--summary]
  python3 messages.py apply <locale> <translations.json> [--root DIR]
  python3 messages.py terms <locale> <English text> [--root DIR] [--limit N]

<locale> is a file suffix such as de, pt_BR, zh_CN (pt-br and zh-cn also work).

`missing` prints JSON: {"<target file>": {"<key>": "<English value>", ...}, ...}
for every English key that has no entry in the target locale file. Values are
unescaped (real newlines, real unicode characters). With --summary it prints
only the counts.

`apply` reads the same JSON shape with translated values and inserts each entry
into the target file next to its English neighbours. It creates the target file
when it does not exist. It never changes existing entries.

`terms` prints existing translations of English messages that contain the given
text (case-insensitive), shortest first, to keep terminology consistent.
"""

import argparse
import json
import os
import re
import sys

ENGLISH_NAME = "messages.properties"


# ---------------------------------------------------------------- parsing

def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def ends_with_continuation(line):
    count = len(line) - len(line.rstrip("\\"))
    return count % 2 == 1


def unescape(text):
    out = []
    i = 0
    while i < len(text):
        c = text[i]
        if c != "\\" or i + 1 >= len(text):
            out.append(c)
            i += 1
            continue
        n = text[i + 1]
        if n == "u" and re.match(r"[0-9a-fA-F]{4}", text[i + 2:i + 6]):
            out.append(chr(int(text[i + 2:i + 6], 16)))
            i += 6
            continue
        out.append({"t": "\t", "n": "\n", "r": "\r", "f": "\f"}.get(n, n))
        i += 2
    return "".join(out)


def split_key_value(logical):
    """Split a logical line into (raw key, raw value) by Java Properties rules."""
    s = logical.lstrip()
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c in "=: \t\f":
            break
        i += 1
    raw_key = s[:i]
    rest = s[i:].lstrip(" \t\f")
    if rest[:1] in ("=", ":"):
        rest = rest[1:].lstrip(" \t\f")
    return raw_key, rest


class Entry:
    def __init__(self, key, raw_key, value, start, end):
        self.key = key            # unescaped key
        self.raw_key = raw_key    # key as written in the file
        self.value = value        # unescaped value
        self.start = start        # index of first physical line
        self.end = end            # index of last physical line


def parse(lines):
    """Return the list of entries of a .properties file in file order."""
    entries = []
    i = 0
    while i < len(lines):
        stripped = lines[i].lstrip()
        if not stripped or stripped[0] in "#!":
            i += 1
            continue
        start = i
        parts = [stripped]
        while ends_with_continuation(parts[-1]) and i + 1 < len(lines):
            parts[-1] = parts[-1][:-1]
            i += 1
            parts.append(lines[i].lstrip())
        if ends_with_continuation(parts[-1]):
            parts[-1] = parts[-1][:-1]
        raw_key, raw_value = split_key_value("".join(parts))
        entries.append(Entry(unescape(raw_key), raw_key, unescape(raw_value), start, i))
        i += 1
    return entries


def header_lines(lines):
    """Leading comment block (license header) of a file."""
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and stripped[0] not in "#!":
            break
        result.append(line)
    while result and not result[-1].strip():
        result.pop()
    return result


def escape_value(value):
    out = []
    for c in value:
        if c == "\\":
            out.append("\\\\")
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif c == "\r":
            out.append("\\r")
        elif c == "\f":
            out.append("\\f")
        else:
            out.append(c)
    text = "".join(out)
    if text.startswith(" "):
        text = "\\" + text
    if text.endswith(" ") and len(text) > 1:
        text = text[:-1] + "\\u0020"
    return text


def shorten(text, limit=100):
    text = text.replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit - 3] + "..."


# ---------------------------------------------------------------- locales

def english_files(root, modules=None):
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d != "build")
        if ENGLISH_NAME in filenames:
            path = os.path.join(dirpath, ENGLISH_NAME)
            if not modules or any(m in path for m in modules):
                result.append(path)
    return sorted(result)


def known_locales(root):
    found = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "build"]
        for name in filenames:
            m = re.fullmatch(r"messages_(.+)\.properties", name)
            if m:
                found.add(m.group(1))
    return found


def resolve_locale(root, locale):
    wanted = locale.replace("-", "_")
    for known in known_locales(root):
        if known.lower() == wanted.lower():
            return known, False
    parts = wanted.split("_")
    parts[0] = parts[0].lower()
    if len(parts) > 1:
        parts[1] = parts[1].upper()
    return "_".join(parts), True


def target_path(english_path, locale):
    return os.path.join(os.path.dirname(english_path), "messages_%s.properties" % locale)


# ---------------------------------------------------------------- missing

def find_missing(english_path, locale):
    english = parse(read_lines(english_path))
    target = target_path(english_path, locale)
    present = set()
    if os.path.exists(target):
        present = {e.key for e in parse(read_lines(target))}
    missing = {}
    for e in english:
        if e.key not in present and e.key not in missing:
            missing[e.key] = e.value
    english_keys = {e.key for e in english}
    obsolete = sorted(present - english_keys)
    return target, missing, obsolete


def cmd_missing(args):
    root = args.root
    locale, new = resolve_locale(root, args.locale)
    if new:
        print("NOTE: no files exist yet for locale '%s'. This is a new locale." % locale,
              file=sys.stderr)
    result = {}
    obsolete_total = {}
    for path in english_files(root, args.module):
        target, missing, obsolete = find_missing(path, locale)
        rel = os.path.relpath(target)
        if missing:
            result[rel] = missing
        if obsolete:
            obsolete_total[rel] = obsolete
    if args.summary:
        total = 0
        for rel, missing in result.items():
            state = "" if os.path.exists(rel) else "  (file does not exist)"
            print("%5d  %s%s" % (len(missing), rel, state))
            total += len(missing)
        print("%5d  total missing keys for locale %s in %d files" % (total, locale, len(result)))
        for rel, keys in obsolete_total.items():
            print("NOTE: %s has %d keys that are not in the English file:" % (rel, len(keys)),
                  file=sys.stderr)
            for key in keys:
                print("        %s" % shorten(key), file=sys.stderr)
    else:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()


# ---------------------------------------------------------------- apply

PLACEHOLDER = re.compile(r"%(?:\d+\$)?[-#+ 0,(]*\d*(?:\.\d+)?[a-zA-Z%]|\{[^{}\s]*\}")
HTML_TAG = re.compile(r"</?[a-zA-Z][^<>]*>")


def check_translation(english, translated):
    """Return (errors, warnings) for one translated value."""
    errors, warnings = [], []
    if not translated.strip() and english.strip():
        errors.append("translation is empty")
    if sorted(PLACEHOLDER.findall(english)) != sorted(PLACEHOLDER.findall(translated)):
        errors.append("placeholders differ: English %s, translation %s" % (
            sorted(PLACEHOLDER.findall(english)), sorted(PLACEHOLDER.findall(translated))))
    if len(HTML_TAG.findall(english)) != len(HTML_TAG.findall(translated)):
        warnings.append("number of HTML tags differs")
    if english.endswith(" ") != translated.endswith(" "):
        warnings.append("trailing space differs")
    return errors, warnings


def starts_group(english_lines, english_entries, index):
    """True when a blank line or comment separates entry `index` from the previous entry."""
    if index == 0:
        return False
    prev_end = english_entries[index - 1].end
    return english_entries[index].start - prev_end > 1


def group_comments(english_lines, english_entries, index):
    """Comment lines directly above entry `index` (not the file header)."""
    if index == 0:
        return []
    comments = []
    i = english_entries[index].start - 1
    while i > english_entries[index - 1].end and english_lines[i].strip()[:1] in ("#", "!"):
        comments.insert(0, english_lines[i])
        i -= 1
    return comments


def apply_file(english_path, target, translations, force):
    english_lines = read_lines(english_path)
    english = parse(english_lines)
    english_index = {}
    for idx, e in enumerate(english):
        english_index.setdefault(e.key, idx)

    if os.path.exists(target):
        lines = read_lines(target)
    else:
        lines = header_lines(english_lines)

    added, skipped = [], []
    for idx, e in enumerate(english):
        if e.key not in translations or english_index[e.key] != idx:
            continue
        translated = translations[e.key]
        entries = parse(lines)
        present = {t.key: t for t in entries}
        if e.key in present:
            skipped.append((e.key, "already translated, left unchanged"))
            continue
        errors, warnings = check_translation(e.value, translated)
        if errors and not force:
            skipped.append((e.key, "; ".join(errors)))
            continue
        for w in warnings:
            print("WARNING %s: %s: %s" % (os.path.relpath(target), e.key, w), file=sys.stderr)

        new_line = "%s=%s" % (e.raw_key, escape_value(translated))
        block = [new_line]
        group = starts_group(english_lines, english, idx)

        # A new first entry of a group whose later entries already exist goes
        # directly before the first of them, so the group stays together.
        follower = None
        if group:
            for nxt in range(idx + 1, len(english)):
                if starts_group(english_lines, english, nxt):
                    break
                if english[nxt].key in present:
                    follower = present[english[nxt].key]
                    break

        anchor = None
        for prev in range(idx - 1, -1, -1):
            if english[prev].key in present:
                anchor = present[english[prev].key]
                break

        if follower is not None:
            pos = follower.start
        elif anchor is not None:
            pos = anchor.end + 1
            if group:
                block = [""] + group_comments(english_lines, english, idx) + block
        elif entries:
            pos = entries[0].start
            block = block + [""] if group else block
        else:
            pos = len(lines)
            block = [""] + block if lines else block
        lines[pos:pos] = block
        added.append(e.key)

    for key in translations:
        if key not in english_index:
            skipped.append((key, "key is not in the English file"))

    if added:
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    return added, skipped


def cmd_apply(args):
    root = args.root
    locale, new = resolve_locale(root, args.locale)
    with open(args.translations, encoding="utf-8") as f:
        data = json.load(f)
    total_added, total_skipped = 0, 0
    for target, translations in data.items():
        target_abs = os.path.abspath(target)
        expected_name = "messages_%s.properties" % locale
        if os.path.basename(target_abs) != expected_name:
            print("ERROR %s: file name must be %s" % (target, expected_name), file=sys.stderr)
            total_skipped += len(translations)
            continue
        english_path = os.path.join(os.path.dirname(target_abs), ENGLISH_NAME)
        if not os.path.exists(english_path):
            print("ERROR %s: no %s next to it" % (target, ENGLISH_NAME), file=sys.stderr)
            total_skipped += len(translations)
            continue
        added, skipped = apply_file(english_path, target_abs, translations, args.force)
        total_added += len(added)
        total_skipped += len(skipped)
        print("%5d added  %s" % (len(added), target))
        for key, reason in skipped:
            print("SKIPPED %s: %s: %s" % (target, key, reason), file=sys.stderr)
    print("%5d added, %d skipped" % (total_added, total_skipped))
    if total_skipped:
        sys.exit(1)


def cmd_terms(args):
    root = args.root
    locale, _ = resolve_locale(root, args.locale)
    needle = args.text.lower()
    seen = {}
    for path in english_files(root):
        target = target_path(path, locale)
        if not os.path.exists(target):
            continue
        translated = {e.key: e.value for e in parse(read_lines(target))}
        for e in parse(read_lines(path)):
            if needle in e.value.lower() and e.key in translated:
                pair = (e.value, translated[e.key])
                seen.setdefault(pair, os.path.relpath(target))
    pairs = sorted(seen.items(), key=lambda item: (len(item[0][0]), item[0][0]))
    for (english, translation), where in pairs[:args.limit]:
        print("%s\n  => %s    [%s]" % (shorten(english), shorten(translation), where))
    if len(pairs) > args.limit:
        print("... %d more" % (len(pairs) - args.limit))
    if not pairs:
        print("no translated message contains '%s'" % args.text)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("missing", help="list English keys that the locale lacks")
    p.add_argument("locale")
    p.add_argument("--root", default="content")
    p.add_argument("--module", action="append",
                   help="only English files whose path contains this text (repeatable)")
    p.add_argument("--summary", action="store_true", help="print counts only")
    p.set_defaults(func=cmd_missing)

    p = sub.add_parser("apply", help="insert translated entries into locale files")
    p.add_argument("locale")
    p.add_argument("translations", help="JSON file in the shape printed by 'missing'")
    p.add_argument("--root", default="content")
    p.add_argument("--force", action="store_true",
                   help="write entries even when placeholder checks fail")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("terms", help="show how English text containing TEXT is translated")
    p.add_argument("locale")
    p.add_argument("text")
    p.add_argument("--root", default="content")
    p.add_argument("--limit", type=int, default=15)
    p.set_defaults(func=cmd_terms)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
