"""
Fuzzy Tech-Term Corrector for Qale.
Combines phonetic normalization and Levenshtein distance against a curated
developer lexicon, strictly gating common English words so standard vocabulary
is never corrupted.
"""
import re
import time
from typing import Dict, List, Optional, Tuple
from whisper.tokenizer import get_tokenizer

# Lazy-loaded singleton Whisper tokenizer for common English word detection
_tok = None

def get_whisper_tok():
    global _tok
    if _tok is None:
        _tok = get_tokenizer(multilingual=False)
    return _tok

def is_common(word: str) -> bool:
    """A word counts as common English if the Whisper tokenizer encodes ' word' as a single token."""
    tok = get_whisper_tok()
    return len(tok.encode(" " + word.lower())) == 1

_RULES = [
    ("ph", "f"), ("ght", "t"), ("kn", "n"), ("wr", "r"), ("ck", "k"),
    ("qu", "kw"), ("x", "ks"), ("tch", "ch"), ("sh", "x"), ("ch", "x"),
    ("th", "0"), ("dg", "j"), ("c(?=[eiy])", "s"), ("c", "k"), ("q", "k"),
    ("z", "s"), ("v", "f"), ("w", ""), ("h", "")
]

def phon_key(s: str) -> str:
    """Generates phonetic representation key for fuzzy pronunciation matching."""
    s = re.sub(r"[^a-z]", "", s.lower())
    for pat, rep in _RULES:
        s = re.sub(pat, rep, s)
    if not s:
        return s
    # Keep first letter, remove vowels from rest
    s = s[0] + re.sub(r"[aeiouy]", "", s[1:])
    # Collapse duplicate consecutive characters
    return re.sub(r"(.)\1+", r"\1", s)

def lev(a: str, b: str, cap: int = 99) -> int:
    """Fast bounded Levenshtein edit distance."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

_PUNCT = re.compile(r"^(\W*)(.*?)(\W*)$")
_CONNECTORS = {"and", "or", "in", "on", "at", "to", "for", "from", "with", "by", "of", "the", "a", "an", "is", "it", "not", "so", "as"}


class TechCorrector:
    def __init__(self, lexicon: List[str], learned: Optional[Dict[str, str]] = None):
        self.entries: List[Tuple[str, str, str]] = [
            (t, phon_key(t), re.sub(r"[^a-z]", "", t.lower()))
            for t in lexicon
        ]
        self.exact = {e[2] for e in self.entries}
        # Sort learned mappings by key length descending so multi-word phrases match first
        self.learned = dict(
            sorted((learned or {}).items(), key=lambda kv: len(kv[0]), reverse=True)
        )

    def _score(self, span: str) -> Tuple[float, Optional[str]]:
        flat = re.sub(r"[^a-z]", "", span.lower())
        k = phon_key(span)
        best: Tuple[float, Optional[str]] = (1.0, None)

        for term, tk, tflat in self.entries:
            # Terms must match spans with the same word count to avoid swallowing prepositions (e.g. 'by', 'in')
            if len(term.split()) != len(span.split()):
                continue
            if abs(len(tk) - len(k)) > 1:
                continue
            if abs(len(flat) - len(tflat)) > 2:
                continue
            pd = lev(k, tk) / max(len(k), len(tk), 1)
            cd = lev(flat, tflat) / max(len(flat), len(tflat), 1)
            s = 0.6 * pd + 0.4 * cd
            if s < best[0]:
                best = (s, term)
        return best

    def correct(self, text: str, thr: float = 0.40, thr_common: float = 0.12) -> str:
        """
        Applies exact learned phrase fixes followed by phonetic non-word correction.
        Standard English words are strictly protected unless score <= thr_common.
        """
        if not text:
            return ""

        t0 = time.perf_counter()

        # 1. Apply explicit learned replacements (case-insensitive)
        for k, v in self.learned.items():
            text = re.sub(rf"\b{re.escape(k)}\b", v, text, flags=re.IGNORECASE)

        # 2. Phonetic token matching
        words = text.split()
        out = []
        i = 0
        while i < len(words):
            hit = False
            for n in (3, 2, 1):
                if i + n > len(words):
                    continue
                parts = [_PUNCT.match(w).groups() for w in words[i : i + n]]
                if n > 1 and (parts[0][1].lower() in _CONNECTORS or parts[-1][1].lower() in _CONNECTORS):
                    continue
                core = " ".join(p[1] for p in parts)
                flat = re.sub(r"[^a-z]", "", core.lower())
                if len(flat) < 4 or flat in self.exact:
                    continue
                score, term = self._score(core)
                allc = all(is_common(p[1]) for p in parts)
                effective_thr = thr_common if allc else thr
                if term and score <= effective_thr:
                    out.append(parts[0][0] + term + parts[-1][2])
                    i += n
                    hit = True
                    break
            if not hit:
                out.append(words[i])
                i += 1

        res = " ".join(out)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        # Timing log (target < 10 ms)
        # Only log when substantial work or in debug
        return res

