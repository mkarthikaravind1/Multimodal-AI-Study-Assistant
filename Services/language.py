"""
Reply language: English / Hindi / Tamil / Hinglish / Tanglish / Auto.

The student picks one in their profile (user_details.preferred_language).
"auto" is resolved HERE, in code, from the text the student wrote (their
question, topic, answer — or the lesson notes), so the model always gets a
concrete instruction like "write in Tanglish" instead of "mirror the user",
which small models follow unreliably.

    note = language_note(user.preferred_language, sample_text)
    → one instruction sentence to add to the prompt ("" never — always explicit)
"""
import re

LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "hinglish": "Hinglish",
    "tanglish": "Tanglish",
    "auto": "Auto",
}
DEFAULT_LANGUAGE = "en"

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_TAMIL = re.compile(r"[஀-௿]")
_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
_WORD = re.compile(r"[a-z]+")

# Distinctive romanised words — common English words ("to", "me", "ka"…) are left
# out on purpose so ordinary English text never looks like Hinglish/Tanglish.
_HINGLISH = {
    "hai", "hain", "kya", "kaise", "kaisa", "kyu", "kyun", "kyon", "nahi", "nahin", "mujhe",
    "samajh", "samjha", "samjhao", "samjhaiye", "batao", "bataiye", "karo", "karna", "karte",
    "mein", "aur", "yaar", "accha", "achha", "theek", "thik", "matlab", "kaun", "kitna",
    "kitne", "hota", "hoti", "hote", "wala", "wali", "hum", "tum", "aap", "apna", "agar",
    "lekin", "kyunki", "phir", "abhi", "bahut", "jaise", "sakta", "sakte", "chahiye", "hoga",
    "isme", "iska", "uska", "kuch", "sab", "bhi", "raha", "rahe", "rahi",
}
_TANGLISH = {
    "enna", "ennaa", "epdi", "eppadi", "enaku", "enakku", "puriyala", "puriyuthu", "puriyudhu",
    "sollu", "sollunga", "solla", "irukku", "iruku", "irukkum", "venum", "vendum", "theriyum",
    "theriyala", "pannu", "panna", "pannunga", "panni", "pannuvanga", "konjam", "romba",
    "ennoda", "unga", "naan", "nee", "idhu", "adhu", "ithu", "athu", "enga", "eppo", "ethuku",
    "edhuku", "yen", "illa", "illai", "seri", "sari", "aana", "appo", "apdi", "ippo", "inga",
    "anga", "kudu", "kodunga", "paaru", "vaa", "poda", "nalla", "thaan", "dhaan", "mattum",
}


def normalize_language(value: str | None) -> str:
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


def detect_language(text: str | None) -> str:
    """
    Best guess at what language `text` is written in:
    "hi" / "ta" (native script), "hinglish" / "tanglish" (romanised), else "en".
    """
    if not text:
        return "en"
    sample = text[:3000]
    letters = len(_LETTER.findall(sample)) or 1
    deva = len(_DEVANAGARI.findall(sample))
    tamil = len(_TAMIL.findall(sample))
    # native script — even mixed with English technical terms
    if max(deva, tamil) / letters >= 0.15:
        return "hi" if deva >= tamil else "ta"

    words = _WORD.findall(sample.lower())
    if not words:
        return "en"
    hin = sum(w in _HINGLISH for w in words)
    tan = sum(w in _TANGLISH for w in words)
    best, hits = ("tanglish", tan) if tan > hin else ("hinglish", hin)
    if hits == 0:
        return "en"
    # a short question needs one marker word ("photosynthesis enna?"),
    # longer text needs at least two and a noticeable share of the words
    if len(words) <= 5 or (hits >= 2 and hits / len(words) >= 0.06):
        return best
    return "en"


def resolve_language(preference: str | None, sample_text: str | None = None) -> str:
    """The concrete language to reply in ("auto" → detected from sample_text)."""
    pref = normalize_language(preference)
    return detect_language(sample_text) if pref == "auto" else pref


_INSTRUCTIONS = {
    "en": "Write your entire response in clear, simple English.",
    "hi": (
        "Write your entire response in Hindi, using Devanagari script. "
        "Keep standard technical and scientific terms, formulas and code in English "
        "(the way Indian teachers usually do), e.g. 'photosynthesis', 'O(n)'."
    ),
    "ta": (
        "Write your entire response in Tamil, using Tamil script. "
        "Keep standard technical and scientific terms, formulas and code in English "
        "(the way Tamil Nadu teachers usually do), e.g. 'photosynthesis', 'O(n)'."
    ),
    "hinglish": (
        "Write your entire response in Hinglish: natural, conversational Hindi mixed with English, "
        "written ONLY in Roman (English) letters — never Devanagari. Keep technical terms in English. "
        "Style example: 'Photosynthesis ek process hai jisme plants sunlight se apna food banate hain.'"
    ),
    "tanglish": (
        "Write your entire response in Tanglish: natural, conversational Tamil mixed with English, "
        "written ONLY in Roman (English) letters — never Tamil script. Keep technical terms in English. "
        "Style example: 'Photosynthesis-na plants sunlight use panni thannoda food-a prepare pannum.'"
    ),
}


def language_instruction(language: str) -> str:
    """Instruction sentence for a CONCRETE language code (not "auto")."""
    return _INSTRUCTIONS.get(language, _INSTRUCTIONS["en"])


def language_note(preference: str | None, sample_text: str | None = None) -> str:
    """Preference (+ text for "auto") → the instruction to put in the prompt."""
    return language_instruction(resolve_language(preference, sample_text))

