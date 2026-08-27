#!/usr/bin/env python3
"""
English -> German offline translator (v2: grammar-aware).

Fully offline: no internet connection or external packages required.

Translation pipeline:

    Input text
        |
        v
    1. Normalize (trim, lowercase, strip trailing punctuation)
        |
        v
    2. Whole-phrase match against PHRASES
        |  (no match)
        v
    3. Sentence-pattern match, e.g.
         "I am <adjective>"      -> Ich bin <adjective>
         "I <verb> <noun>"       -> Ich <verb conjugated> <noun (+ article)>
       using conjugation (VERBS) and gendered-article (NOUNS) tables
        |  (no match)
        v
    4. Word-by-word fallback lookup (WORDS / NOUNS), unknown words are
       left untouched and reported separately.

Because it's dictionary- and rule-based (not a neural model), it works
best for common words, greetings, and simple present-tense sentences --
not for complex grammar or idiomatic text.

Usage:
    python3 translator.py                     # interactive mode
    python3 translator.py "Good morning"      # translate a single phrase
    python3 translator.py --explain "I like football"
                                               # show which rule fired and
                                               # any words that weren't
                                               # recognized
"""

import re
import sys

# ---------------------------------------------------------------------------
# Phrase dictionary: checked first, whole phrase must match (case-insensitive)
# ---------------------------------------------------------------------------
PHRASES = {
    "good morning": "guten Morgen",
    "good evening": "guten Abend",
    "good night": "gute Nacht",
    "good afternoon": "guten Tag",
    "how are you": "wie geht es dir",
    "how are you doing": "wie geht es dir",
    "nice to meet you": "schön dich kennenzulernen",
    "see you later": "bis später",
    "see you soon": "bis bald",
    "see you tomorrow": "bis morgen",
    "i love you": "ich liebe dich",
    "thank you very much": "vielen Dank",
    "thank you so much": "vielen Dank",
    "you are welcome": "gern geschehen",
    "excuse me": "entschuldigung",
    "i am sorry": "es tut mir leid",
    "i'm sorry": "es tut mir leid",
    "what is your name": "wie heißt du",
    "my name is": "ich heiße",
    "where is the bathroom": "wo ist die toilette",
    "how much does this cost": "wie viel kostet das",
    "i do not understand": "ich verstehe nicht",
    "i don't understand": "ich verstehe nicht",
    "can you help me": "kannst du mir helfen",
    "happy birthday": "alles gute zum geburtstag",
}

# ---------------------------------------------------------------------------
# Word dictionary: fallback used word-by-word when no phrase/pattern matches.
# Nouns live separately in NOUNS (see below) so they can carry gender info.
# ---------------------------------------------------------------------------
WORDS = {
    # greetings / basics
    "hello": "hallo", "hi": "hallo", "bye": "tschüss", "goodbye": "auf Wiedersehen",
    "yes": "ja", "no": "nein", "please": "bitte", "thanks": "danke", "thank": "danke",
    "sorry": "entschuldigung", "welcome": "willkommen", "ok": "okay",

    # pronouns
    "i": "ich", "you": "du", "he": "er", "she": "sie", "it": "es",
    "we": "wir", "they": "sie", "me": "mich", "him": "ihn", "her": "sie",
    "us": "uns", "them": "sie", "my": "mein", "your": "dein", "his": "sein",
    "our": "unser", "their": "ihr",

    # question words
    "what": "was", "who": "wer", "where": "wo", "when": "wann",
    "why": "warum", "how": "wie", "which": "welche",

    # common verbs (base/infinitive-ish forms for the word-by-word fallback;
    # conjugated forms for sentence patterns live in VERBS below)
    "am": "bin", "is": "ist", "are": "sind", "was": "war", "were": "waren",
    "be": "sein", "have": "haben", "has": "hat", "had": "hatte",
    "do": "tun", "does": "tut", "did": "tat", "go": "gehen", "goes": "geht",
    "went": "ging", "come": "kommen", "came": "kam", "want": "wollen",
    "wants": "will", "need": "brauchen", "like": "mögen", "love": "lieben",
    "know": "wissen", "think": "denken", "see": "sehen", "say": "sagen",
    "eat": "essen", "drink": "trinken", "sleep": "schlafen", "work": "arbeiten",
    "live": "leben", "speak": "sprechen", "understand": "verstehen",
    "help": "helfen", "give": "geben", "take": "nehmen", "make": "machen",
    "find": "finden", "buy": "kaufen", "read": "lesen", "write": "schreiben",
    "learn": "lernen", "play": "spielen", "can": "kann", "will": "wird",
    "would": "würde", "should": "sollte", "must": "muss",

    # numbers
    "one": "eins", "two": "zwei", "three": "drei", "four": "vier",
    "five": "fünf", "six": "sechs", "seven": "sieben", "eight": "acht",
    "nine": "neun", "ten": "zehn",

    # days
    "monday": "Montag", "tuesday": "Dienstag", "wednesday": "Mittwoch",
    "thursday": "Donnerstag", "friday": "Freitag", "saturday": "Samstag",
    "sunday": "Sonntag",

    # adjectives
    "good": "gut", "bad": "schlecht", "big": "groß", "small": "klein",
    "new": "neu", "old": "alt", "happy": "glücklich", "sad": "traurig",
    "beautiful": "schön", "hot": "heiß", "cold": "kalt", "fast": "schnell",
    "slow": "langsam", "easy": "einfach", "difficult": "schwierig",
    "tired": "müde", "hungry": "hungrig", "thirsty": "durstig",

    # connectors / misc
    "and": "und", "or": "oder", "but": "aber", "with": "mit", "without": "ohne",
    "for": "für", "to": "zu", "from": "von", "in": "in", "on": "auf",
    "at": "an", "not": "nicht", "very": "sehr", "today": "heute",
    "tomorrow": "morgen", "yesterday": "gestern", "now": "jetzt",
    "here": "hier", "there": "dort", "the": "der", "a": "ein", "an": "ein",
}

# ---------------------------------------------------------------------------
# Noun dictionary: noun -> (article, German translation).
# The article carries the noun's grammatical gender (der/die/das) so
# sentence patterns can build "ein Buch" / "das Buch" correctly instead of
# always defaulting to "der".
# ---------------------------------------------------------------------------
NOUNS = {
    "house": ("das", "Haus"), "car": ("das", "Auto"), "book": ("das", "Buch"),
    "water": ("das", "Wasser"), "food": ("das", "Essen"), "friend": ("der", "Freund"),
    "family": ("die", "Familie"), "day": ("der", "Tag"), "night": ("die", "Nacht"),
    "morning": ("der", "Morgen"), "evening": ("der", "Abend"), "week": ("die", "Woche"),
    "year": ("das", "Jahr"), "time": ("die", "Zeit"), "man": ("der", "Mann"),
    "woman": ("die", "Frau"), "child": ("das", "Kind"), "city": ("die", "Stadt"),
    "country": ("das", "Land"), "world": ("die", "Welt"), "school": ("die", "Schule"),
    "money": ("das", "Geld"), "name": ("der", "Name"), "dog": ("der", "Hund"),
    "cat": ("die", "Katze"), "sun": ("die", "Sonne"), "moon": ("der", "Mond"),
    "table": ("der", "Tisch"), "chair": ("der", "Stuhl"), "door": ("die", "Tür"),
    "window": ("das", "Fenster"), "phone": ("das", "Telefon"), "computer": ("der", "Computer"),
    "music": ("die", "Musik"), "language": ("die", "Sprache"), "question": ("die", "Frage"),
    "answer": ("die", "Antwort"), "football": ("der", "Fußball"), "coffee": ("der", "Kaffee"),
    "tea": ("der", "Tee"), "beer": ("das", "Bier"), "job": ("der", "Job"),
}

# ---------------------------------------------------------------------------
# Verb conjugation table used by sentence patterns.
# Keys are conjugation "slots": ich, du, er (also used for sie/es-singular),
# wir, ihr, sie (also used for the formal "Sie" / they-plural).
# ---------------------------------------------------------------------------
VERBS = {
    "be":     {"ich": "bin",     "du": "bist",     "er": "ist",     "wir": "sind",    "ihr": "seid",   "sie": "sind"},
    "have":   {"ich": "habe",    "du": "hast",     "er": "hat",     "wir": "haben",   "ihr": "habt",   "sie": "haben"},
    "make":   {"ich": "mache",   "du": "machst",   "er": "macht",   "wir": "machen",  "ihr": "macht",  "sie": "machen"},
    "go":     {"ich": "gehe",    "du": "gehst",    "er": "geht",    "wir": "gehen",   "ihr": "geht",   "sie": "gehen"},
    "come":   {"ich": "komme",   "du": "kommst",   "er": "kommt",   "wir": "kommen",  "ihr": "kommt",  "sie": "kommen"},
    "play":   {"ich": "spiele",  "du": "spielst",  "er": "spielt",  "wir": "spielen", "ihr": "spielt", "sie": "spielen"},
    "read":   {"ich": "lese",    "du": "liest",    "er": "liest",   "wir": "lesen",   "ihr": "lest",   "sie": "lesen"},
    "write":  {"ich": "schreibe", "du": "schreibst", "er": "schreibt", "wir": "schreiben", "ihr": "schreibt", "sie": "schreiben"},
    "eat":    {"ich": "esse",    "du": "isst",     "er": "isst",    "wir": "essen",   "ihr": "esst",   "sie": "essen"},
    "drink":  {"ich": "trinke",  "du": "trinkst",  "er": "trinkt",  "wir": "trinken", "ihr": "trinkt", "sie": "trinken"},
    "learn":  {"ich": "lerne",   "du": "lernst",   "er": "lernt",   "wir": "lernen",  "ihr": "lernt",  "sie": "lernen"},
    "speak":  {"ich": "spreche", "du": "sprichst", "er": "spricht", "wir": "sprechen", "ihr": "sprecht", "sie": "sprechen"},
    "like":   {"ich": "mag",     "du": "magst",    "er": "mag",     "wir": "mögen",   "ihr": "mögt",   "sie": "mögen"},
    "love":   {"ich": "liebe",   "du": "liebst",   "er": "liebt",   "wir": "lieben",  "ihr": "liebt",  "sie": "lieben"},
    "need":   {"ich": "brauche", "du": "brauchst", "er": "braucht", "wir": "brauchen", "ihr": "braucht", "sie": "brauchen"},
    "want":   {"ich": "möchte",  "du": "möchtest", "er": "möchte",  "wir": "möchten", "ihr": "möchtet", "sie": "möchten"},
    "know":   {"ich": "weiß",    "du": "weißt",    "er": "weiß",    "wir": "wissen",  "ihr": "wisst",  "sie": "wissen"},
    "see":    {"ich": "sehe",    "du": "siehst",   "er": "sieht",   "wir": "sehen",   "ihr": "seht",   "sie": "sehen"},
    "help":   {"ich": "helfe",   "du": "hilfst",   "er": "hilft",   "wir": "helfen",  "ihr": "helft",  "sie": "helfen"},
    "work":   {"ich": "arbeite", "du": "arbeitest", "er": "arbeitet", "wir": "arbeiten", "ihr": "arbeitet", "sie": "arbeiten"},
    "understand": {"ich": "verstehe", "du": "verstehst", "er": "versteht", "wir": "verstehen", "ihr": "versteht", "sie": "verstehen"},
    "buy":    {"ich": "kaufe",   "du": "kaufst",   "er": "kauft",   "wir": "kaufen",  "ihr": "kauft",  "sie": "kaufen"},
    "find":   {"ich": "finde",   "du": "findest",  "er": "findet",  "wir": "finden",  "ihr": "findet", "sie": "finden"},
}

# Irregular English 3rd-person-singular forms that don't just add "s"
# (used to normalize "has"/"goes"/"does" etc. back to a base verb).
IRREGULAR_3RD_PERSON = {
    "has": "have", "does": "do", "goes": "go", "says": "say",
    "watches": "watch", "washes": "wash", "catches": "catch",
}

# German subject pronouns, and which VERBS conjugation slot each maps to.
PRONOUN_DE = {
    "i": "ich", "you": "du", "he": "er", "she": "sie", "it": "es",
    "we": "wir", "they": "sie",
}
PRONOUN_CONJ_KEY = {
    "i": "ich", "you": "du", "he": "er", "she": "er", "it": "er",
    "we": "wir", "they": "sie",
}


def translate_word(word: str) -> str:
    """Translate a single word, preserving punctuation and capitalization."""
    match = re.match(r"^([^\w]*)([\w']+)([^\w]*)$", word, re.UNICODE)
    if not match:
        return word
    prefix, core, suffix = match.groups()
    lower = core.lower()

    if lower in WORDS:
        translated = WORDS[lower]
    elif lower in NOUNS:
        translated = NOUNS[lower][1]
    else:
        return word  # leave unknown words untouched

    if core[0].isupper():
        translated = translated[0].upper() + translated[1:]
    return f"{prefix}{translated}{suffix}"


def _normalize_verb(token: str) -> str:
    """Map a surface verb form (likes, plays, has, ...) to its VERBS key."""
    if token in VERBS:
        return token
    if token in IRREGULAR_3RD_PERSON:
        return IRREGULAR_3RD_PERSON[token]
    if token.endswith("s") and token[:-1] in VERBS:
        return token[:-1]
    return token


def _split_trailing_punct(token: str):
    match = re.match(r"^(.*?)([.!?]*)$", token, re.UNICODE)
    return match.group(1), match.group(2)


def try_pattern_translate(text: str):
    """
    Attempt sentence-pattern translation:
        "I am <adjective>"          -> Ich bin <adjective>
        "<pronoun> <verb> <noun>"   -> <Pronoun> <verb conjugated> <noun>

    Returns (translation, rule_description, unknown_words) or None if no
    pattern matched.
    """
    stripped = text.strip()
    if not stripped:
        return None

    tokens = stripped.split()
    lower_tokens = [t.lower() for t in tokens]
    if len(lower_tokens) < 3:
        return None

    subj = lower_tokens[0]
    if subj not in PRONOUN_DE:
        return None

    verb_raw = lower_tokens[1]
    conj_key = PRONOUN_CONJ_KEY[subj]
    subject_de = PRONOUN_DE[subj]

    # --- Pattern: pronoun + am/is/are + adjective -------------------------
    if verb_raw in ("am", "is", "are"):
        adj_tokens = tokens[2:]
        last, punct = _split_trailing_punct(adj_tokens[-1])
        adj_phrase = " ".join(adj_tokens[:-1] + [last]).lower()
        if adj_phrase in WORDS and adj_phrase not in ("the", "a", "an"):
            verb_de = VERBS["be"][conj_key]
            sentence = f"{subject_de.capitalize()} {verb_de} {WORDS[adj_phrase]}{punct}"
            return sentence, "Sentence pattern: pronoun + be + adjective", []
        return None

    # --- Pattern: pronoun + verb + (article) + noun ------------------------
    base_verb = _normalize_verb(verb_raw)
    if base_verb not in VERBS:
        return None

    rest = lower_tokens[2:]
    had_article = None
    if rest and rest[0] in ("a", "an", "the"):
        had_article = rest[0]
        rest = rest[1:]
    if not rest:
        return None

    last_raw, punct = _split_trailing_punct(rest[-1])
    noun_tokens = rest[:-1] + [last_raw]
    noun_key = " ".join(noun_tokens)
    verb_de = VERBS[base_verb][conj_key]

    if noun_key in NOUNS:
        # Known noun: build a grammatically correct object with article.
        article_de, noun_de = NOUNS[noun_key]
        if had_article in ("a", "an"):
            object_de = ("eine " if article_de == "die" else "ein ") + noun_de
        elif had_article == "the":
            object_de = f"{article_de} {noun_de}"
        else:
            object_de = noun_de
        sentence = f"{subject_de.capitalize()} {verb_de} {object_de}{punct}"
        return sentence, "Sentence pattern: pronoun + conjugated verb + noun", []

    # Unknown noun: still get the verb conjugation right (the part rules
    # can guarantee) and fall back word-by-word for the object, flagging
    # whatever isn't recognized instead of losing the sentence entirely.
    translated_rest = []
    unknown = []
    if had_article:
        translated_rest.append(WORDS.get(had_article, had_article))
    for tok in noun_tokens:
        translated = translate_word(tok)
        translated_rest.append(translated)
        if translated == tok and tok.lower() not in WORDS and tok.lower() not in NOUNS:
            unknown.append(tok)
    sentence = f"{subject_de.capitalize()} {verb_de} {' '.join(translated_rest)}{punct}"
    return sentence, "Sentence pattern: pronoun + conjugated verb (object unrecognized)", unknown


def translate_explain(text: str) -> dict:
    """
    Translate text and return a dict with:
        translation   - the German output
        method        - list of rules/steps that were applied
        unknown_words - English words that couldn't be translated
    """
    stripped = text.strip()
    lower = stripped.lower().rstrip(".!? ")

    # 1. Whole-phrase match
    if lower in PHRASES:
        result = PHRASES[lower]
        result = result[0].upper() + result[1:]
        return {"translation": result, "method": ["Phrase match"], "unknown_words": []}

    # 2. Sentence-pattern match (grammar rules)
    pattern_result = try_pattern_translate(stripped)
    if pattern_result is not None:
        translation, rule, unknown = pattern_result
        return {"translation": translation, "method": [rule], "unknown_words": unknown}

    # 3. Word-by-word fallback
    words = stripped.split(" ")
    translated_words = []
    unknown_words = []
    for w in words:
        translated = translate_word(w)
        translated_words.append(translated)
        match = re.match(r"^([^\w]*)([\w']+)([^\w]*)$", w, re.UNICODE)
        if match:
            core_lower = match.group(2).lower()
            if core_lower not in WORDS and core_lower not in NOUNS:
                unknown_words.append(match.group(2))

    return {
        "translation": " ".join(translated_words),
        "method": ["Word-by-word fallback"],
        "unknown_words": unknown_words,
    }


def translate(text: str) -> str:
    """Translate an English sentence/phrase into German."""
    return translate_explain(text)["translation"]


def print_explained(text: str) -> None:
    info = translate_explain(text)
    print("DE>", info["translation"])
    print("Method:", " -> ".join(info["method"]))
    if info["unknown_words"]:
        print("⚠ Unknown words:", ", ".join(info["unknown_words"]))
    else:
        print("✓ All words recognized")


def main():
    args = sys.argv[1:]
    explain = False
    if args and args[0] in ("--explain", "-e"):
        explain = True
        args = args[1:]

    if args:
        text = " ".join(args)
        if explain:
            print_explained(text)
        else:
            print(translate(text))
        return

    print("English -> German Offline Translator")
    print("Type a sentence and press Enter. Type 'quit' to exit.")
    print("Type 'explain <sentence>' to see which rule was used.\n")
    while True:
        try:
            text = input("EN> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in ("quit", "exit"):
            break
        if text.lower().startswith("explain "):
            print_explained(text[len("explain "):])
        else:
            print("DE>", translate(text))


if __name__ == "__main__":
    main()
