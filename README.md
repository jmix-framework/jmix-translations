# Jmix Translations

This repository contains translations for the [Jmix](https://jmix.io) framework.

For more information see Jmix [documentation](https://docs.jmix.io/jmix/localization/framework-translations.html).

## Usage

```groovy
implementation 'io.jmix.translations:jmix-translations-ar'
implementation 'io.jmix.translations:jmix-translations-ckb'
implementation 'io.jmix.translations:jmix-translations-cs'
implementation 'io.jmix.translations:jmix-translations-da'
implementation 'io.jmix.translations:jmix-translations-de'
implementation 'io.jmix.translations:jmix-translations-el'
implementation 'io.jmix.translations:jmix-translations-es'
implementation 'io.jmix.translations:jmix-translations-fr'
implementation 'io.jmix.translations:jmix-translations-it'
implementation 'io.jmix.translations:jmix-translations-nl'
implementation 'io.jmix.translations:jmix-translations-pt-br'
implementation 'io.jmix.translations:jmix-translations-ro'
implementation 'io.jmix.translations:jmix-translations-ru'
implementation 'io.jmix.translations:jmix-translations-tr'
implementation 'io.jmix.translations:jmix-translations-zh-cn'
implementation 'io.jmix.translations:jmix-translations-zh-tw'
```

## Building

Publish all translations to `.m2`:
```
./gradlew publishToMavenLocal
```

## Editing

Make sure that in IntelliJ IDEA *Preferences -> Editor -> File Encodings -> Default encoding for properties files* is set to UTF-8.

## Translating missing messages with an AI agent

The repository has an agent skill that finds English messages with no translation in a locale and translates them. The skill is in `.agents/skills/translate-messages`. `.claude/skills` is a symlink to `.agents/skills`, so Claude Code finds it too.

Requirements: Python 3 (the skill uses `.agents/skills/translate-messages/scripts/messages.py`).

In Claude Code, run the skill with a locale or a language name:

```
/translate-messages de
/translate-messages pt_BR
/translate-messages German
```

In other agents that read skills from `.agents/skills`, ask the agent to use the `translate-messages` skill for a language. You can also limit the work to some modules, for example: "translate missing German messages in flowui and searchflowui".

The agent:

1. Finds the locale. If the language is not clear (for example, Chinese), or it is a new locale, the agent asks you first.
2. Shows how many keys are missing in each file. If there are many, it asks before it splits the work between parallel subagents.
3. Translates the missing messages. It uses existing translations of the same terms in this locale and keeps placeholders (`%s`, `{0}`, `${value}`) and HTML tags.
4. Adds the new entries to the `messages_<locale>.properties` files at the same place as in the English file, and creates files that do not exist yet. It does not change existing entries and does not translate `localeDisplayName.en`.
5. Reports the translations it was unsure about and broken existing entries that it noticed.

The agent does not commit. Review the changes with `git diff` and `git status` (new files are untracked) before you commit.

You can also run the script without an agent:

```
# number of missing keys per file
python3 .agents/skills/translate-messages/scripts/messages.py missing de --summary

# missing keys of some modules as JSON
python3 .agents/skills/translate-messages/scripts/messages.py missing de --module io/jmix/flowui/ --module io/jmix/core/

# existing translations of English messages that contain a text
python3 .agents/skills/translate-messages/scripts/messages.py terms de "detail view"

# add translated entries from a JSON file in the format printed by "missing"
python3 .agents/skills/translate-messages/scripts/messages.py apply de translations.json
```
