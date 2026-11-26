---
name: translate-messages
description: Use when English messages in messages.properties files have no translation in a locale file (messages_de.properties, messages_pt_BR.properties, ...), for example after a "Sync English messages" commit, or when asked to translate or update the translations for a language.
argument-hint: <language or locale, e.g. de, pt_BR, German>
---

# Translate missing messages

The English messages are the reference: `content/**/messages.properties`. Each translation sits next to its English file as `messages_<locale>.properties` (`messages_de.properties`, `messages_pt_BR.properties`, `messages_zh_CN.properties`). The files are UTF-8.

The script `scripts/messages.py` does the mechanical work: it finds missing keys, inserts translated entries at the same place as in the English file, escapes values, checks placeholders, and looks up existing terms. You do the translation. Never insert entries by hand and do not write your own parser.

Language requested: `$ARGUMENTS`

## Steps

Run all commands from the repository root, exactly as written (the script path is spelled out in full on purpose; do not put the command into a shell variable).

### 1. Find the locale

If the argument is already a locale suffix that exists (`de`, `pt-br`, `zh_CN`), go to step 2. If it is a language name (`German`), turn it into the locale suffix used by the existing files:

```bash
find content -name 'messages_*.properties' | sed 's/.*messages_//; s/\.properties//' | sort | uniq -c
```

- No argument, or the name fits more than one locale (Chinese: `zh_CN` or `zh_TW`; Portuguese: `pt_BR` or a new `pt`): ask the user.
- If `python3 .agents/skills/translate-messages/scripts/messages.py missing <locale> --summary` prints `NOTE: ... This is a new locale`, stop and ask the user to confirm. A new locale also needs a `contentJar...` task in `build.gradle` (copy an existing one) and a line in the README "Usage" list. Add them only after the user confirms.

### 2. See how much is missing

```bash
python3 .agents/skills/translate-messages/scripts/messages.py missing <locale> --summary
```

It prints the number of missing keys per target file, and marks files that do not exist yet. If the user named modules, filter with `--module io/jmix/<module>/`. The option is a path substring and can be repeated. Keep both slashes so `io/jmix/flowui/` does not also match `searchflowui/`. You can do the following steps for several modules at once with one JSON file.

`NOTE: ... has N keys that are not in the English file:` is followed by those keys. They are old keys, or broken entries (a key that starts with HTML text usually means a missing `\` at the end of the line above it). Mention them in the final report. Do not delete or fix them.

### 3. Decide who translates

- **Up to about 300 missing keys:** translate them yourself, file by file (step 4).
- **More than that:** split the target files into batches of about 200–300 keys and give each batch to a subagent, running in parallel. Ask the user first: say how many subagents and roughly how many keys each one gets. Each subagent receives its list of target files, the locale, and the instruction to follow steps 4–5 of this skill (`.agents/skills/translate-messages/SKILL.md`) for those files only. Batches must not share a file. Each subagent writes its own JSON file name.

### 4. Translate one file (or a small group of files)

1. Get the missing keys as JSON:

   ```bash
   mkdir -p build
   python3 .agents/skills/translate-messages/scripts/messages.py missing <locale> --module io/jmix/<module>/ > build/translate-<locale>-<name>.json
   ```

   `<name>` is the module, or any name for a group of modules. `build/` is ignored by git. The shape is `{"<target file>": {"<key>": "<English value>"}}`. Values are plain text: real characters, no properties escapes.

2. Read context before you translate:
   - The English file around the keys, to see which UI element a message belongs to (the key name and its neighbours tell you: `.title`, `.description`, `.tooltip`, a button, an enum value).
   - The existing target file, to copy its style: formal or informal address ("Sie"/"du", "Вы"/"ты"), capitalization of labels, punctuation, length.
   - Established terms in this locale. For each domain term in the messages (entity, detail view, filter, report, process, ...), look up how it was translated before and use the same word:

     ```bash
     python3 .agents/skills/translate-messages/scripts/messages.py terms <locale> "detail view"
     ```

     It prints English messages that contain the text, with their existing translations, shortest first. Long values are cut at 100 characters.

3. Replace each English value in the JSON with its translation. Keep the same file names and keys. Follow the translation rules below.

   Delete the key `localeDisplayName.en` (from `content/io/jmix/core/messages.properties`) from the JSON. Do not translate it.

4. Insert the translations:

   ```bash
   python3 .agents/skills/translate-messages/scripts/messages.py apply <locale> build/translate-<locale>-<name>.json
   ```

   - `SKIPPED ...: placeholders differ` — fix the translation in the JSON and run `apply` again. Entries already inserted are skipped as "already translated"; that is expected on a second run.
   - `WARNING ... number of HTML tags differs` or `trailing space differs` — check the entry; fix it if it is a mistake.
   - Use `--force` only when the English placeholder list is clearly wrong for the language, and say so in the report.

### 5. Check the result

```bash
python3 .agents/skills/translate-messages/scripts/messages.py missing <locale> --summary   # the files you worked on must not be listed, except core (see below)
git status --short   # new translation files show as ??
git diff --stat      # changed files only
```

If `content/io/jmix/core/messages_<locale>.properties` shows 1 missing key, that is `localeDisplayName.en`, which is not translated on purpose. Do not report it as missing.

Look at the diff of one or two files to check that the new lines sit in the right groups. Leave the changes uncommitted.

## Translation rules

| English contains | What to do |
|---|---|
| `%s`, `%d`, `%1$s`, `{0}`, `{column}`, `${value}`, `{E}` | Keep exactly, same count. Keep the order of plain `%s`; if the language needs another order, rephrase the sentence. |
| HTML (`<b>`, `<br/>`, `<code>...</code>`, `<li>`) | Keep all tags. Translate only the text between them. Do not translate code inside `<code>`. |
| Product, add-on and tech names: Jmix, Jmix-oidc, Vaadin, BPMN, JPQL, JSON, REST, OIDC, LDAP | Keep as they are. |
| Quoted code words: `"from"`, `"join"`, `?`, entity or attribute names | Keep as they are. |
| A key ending in `Format` (`dateFormat`, `doubleFormat`, `excelExporter.dateTimeFormat`) | Not text. Copy the value of the same key from another `messages_<locale>.properties` in this locale if one exists; otherwise use the locale's date and number conventions with the same pattern letters. |
| A trailing space (`remainingTime=...: `) | Keep it. The script writes it as `\u0020`. |
| A line break inside the value | Keep it as `\n` in the JSON string. |
| Text that looks like a test or template leftover (`Foo browser`) | Translate the English value (not the key name) and mention it in the report. |
| The same English text twice in one file | Use the same translation both times. |

Also:

- Translate the meaning for a UI label, not word by word. Keep labels short, about as long as the English.
- Write values as plain JSON strings. Do not add properties escapes (`\u00e9`, a trailing `\`, `\=`); the script escapes what is needed.
- Never change entries that already exist. If you see a wrong or broken existing translation, list it in the report.

## Report

When done, tell the user:

- Number of keys translated per file, and the files that were created.
- Translations you were unsure about, with the English text and the alternatives.
- The `NOTE:` lines from step 2 and any broken existing entries you noticed.
- That the changes are uncommitted.
