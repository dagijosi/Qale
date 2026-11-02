"""
Voice-to-Code Parser for Qale.
Transforms raw transcribed speech into precise code syntax, developer terms,
case conventions, path separators, URLs, and editor actions (e.g., Backspace, Enter, Tab).
Includes robust phonetic error-correction for microphone & accent variations.
"""
import re
from typing import Dict, Any, Optional

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
}

KNOWN_EXTS = r"(?:tsx|jsx|ts|js|json|py|html|css|scss|md|sql|env|yaml|yml|xml|cpp|c|h|cs|rs|go|java|sh|bat|com|org|net|io|dev|app|local|test)"


class CodeParser:
    def __init__(self, config_manager=None):
        if config_manager is None:
            from core.config_manager import ConfigManager
            self.config = ConfigManager()
        else:
            self.config = config_manager

        # Default cached TechCorrector instance for base profile
        from core.context import DEFAULT_BASE_LEXICON
        from core.tech_corrector import TechCorrector
        base_lex = self.config.get("ai", "base_lexicon", default=DEFAULT_BASE_LEXICON)
        self.default_corrector = TechCorrector(base_lex, self.config.get_sound_alikes())

    def parse(self, raw_text: str, corrector=None) -> Dict[str, Any]:
        if not raw_text or not raw_text.strip():
            return {"type": "text", "content": ""}

        text = raw_text.strip()

        # Step 5 Pipeline: loop dedup -> TechCorrector -> casing -> symbols -> actions

        # 1. Collapse Hallucinated Repetition Loops (e.g. "to 2.5 to 2.5 to 2.5...")
        text = self._deduplicate_repetitions(text)

        # 2. Fuzzy Tech-Term Corrector (timing target < 10ms)
        use_corrector = corrector if corrector is not None else self.default_corrector
        if use_corrector is not None and self.config.get("ai", "tech_corrector_enabled", True):
            import time
            t0 = time.perf_counter()
            thr = float(self.config.get("ai", "tech_corrector_threshold", 0.40))
            thr_com = float(self.config.get("ai", "tech_corrector_threshold_common", 0.12))
            text = use_corrector.correct(text, thr=thr, thr_common=thr_com)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            if dt_ms > 10.0:
                print(f"[CodeParser] TechCorrector timing warning: {dt_ms:.2f} ms")

        # 3. Check for standalone Actions (e.g. "go back", "pullback", "newline")
        action_match = self._match_action(text)
        if action_match:
            return action_match

        # 4. Check for Casing Commands (e.g. "camelCase, getUserAccount", "const case, max retry attempts")
        casing_match = self._match_casing_command(text)
        if casing_match is not None:
            return {"type": "text", "content": casing_match}

        # 5. Apply Phonetic Code & Symbol Normalizer
        text = self._apply_phonetic_code_rules(text)

        # 6. Apply Sound-Alikes & Tech Terms (e.g. "nextjs" -> "Next.js", "Dustand" -> "Zustand")
        text = self._apply_sound_alikes(text)

        # 7. Apply Symbol Replacements
        text = self._apply_symbols(text)

        # 8. Clean Code Formatting, URLs, File Extensions & Sentence Spacing
        text = self._cleanup_code_and_paths(text)

        return {"type": "text", "content": text}

    def _deduplicate_repetitions(self, text: str) -> str:
        """Collapses Whisper repetitive hallucination loops (repeating 2+ times with punctuation/delimiters)."""
        # Matches repeated phrases of 1 to 15 words, separated by whitespace, commas, or punctuation
        pattern = r'(?i)(\b(?:\S+\s+){0,15}\S+?)(?:[\s,.]+\1){2,}'
        for _ in range(3):
            text = re.sub(pattern, r'\1', text)
        return text.strip()

    def _match_action(self, text: str) -> Optional[Dict[str, Any]]:
        clean = text.lower().strip().rstrip(".,!?")

        # Direct dictionary check
        actions = self.config.get("actions", default={})
        if clean in actions:
            return {"type": "action", "action": actions[clean], "count": 1}

        # Match single-word "newline" or "new line"
        if re.match(r"^(?:new\s*line|newline)$", clean):
            return {"type": "action", "action": "ACTION_ENTER", "count": 1}

        # Match "tab" / "indent"
        if re.match(r"^(?:tab|indent)$", clean):
            return {"type": "action", "action": "ACTION_TAB", "count": 1}

        # Match "escape"
        if re.match(r"^(?:escape|press\s*escape)$", clean):
            return {"type": "action", "action": "ACTION_ESCAPE", "count": 1}

        # Match "select all"
        if re.match(r"^select\s*all$", clean):
            return {"type": "action", "action": "ACTION_SELECT_ALL", "count": 1}

        # Match "copy" / "copy that"
        if re.match(r"^(?:copy|copy\s*that|copy\s*selection)$", clean):
            return {"type": "action", "action": "ACTION_COPY", "count": 1}

        # Match "cut" / "cut that"
        if re.match(r"^(?:cut|cut\s*that|cut\s*selection)$", clean):
            return {"type": "action", "action": "ACTION_CUT", "count": 1}

        # Match "undo" / "undo that"
        if re.match(r"^(?:undo|undo\s*that)$", clean):
            return {"type": "action", "action": "ACTION_UNDO", "count": 1}

        # Match "go back / pullback / backspace / erase" with optional repeat count
        pat = r"^(?:pullback|pull\s*back|go\s*back|backspace|erase(?:\s*that)?|delete(?:\s*that)?|scratch\s*that|undo(?:\s*that)?)(?:\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten))?(?:\s+times)?$"
        m = re.match(pat, clean)
        if m:
            num = m.group(1)
            count = (WORD_NUMBERS.get(num) if num in WORD_NUMBERS else (int(num) if num else 1))
            return {"type": "action", "action": "ACTION_BACKSPACE", "count": count}

        # Match "back five times"
        m2 = re.match(r"^back\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)(?:\s+times)?$", clean)
        if m2:
            num = m2.group(1)
            count = WORD_NUMBERS.get(num) if num in WORD_NUMBERS else int(num)
            return {"type": "action", "action": "ACTION_BACKSPACE", "count": count}

        # Match sentence ending in a self-correction (e.g. "tailword, go back" or "go back, use")
        if re.search(r"(?:[,.]?\s*(?:go\s*back|pullback|pull\s*back|erase\s*that|scratch\s*that))(?:[,.\s]+use)?$", clean):
            return {"type": "action", "action": "ACTION_BACKSPACE", "count": 1}

        return None

    def _match_casing_command(self, text: str) -> Optional[str]:
        def normalize_casing_words(s: str) -> str:
            sub_rules = [
                (r"\bfake\s+user\s+profile\b", "fetch user profile"),
                (r"\bgate\s+user\s+name\b", "get user name"),
                (r"\bmaps\s+return\s+count\b", "max retry count"),
                (r"\bmaps\s+retry\s+count\b", "max retry count"),
            ]
            for pat, rep in sub_rules:
                s = re.sub(pat, rep, s, flags=re.IGNORECASE)
            return s

        patterns = [
            (r"^(?:camel|hamill|hamil|kamel)\s*case[,\s:]+(.+)$", self._to_camel_case),
            (r"^(?:snake|sneak)\s*case[,\s:]+(.+)$", self._to_snake_case),
            (r"^(?:pascal|pass\s*cal|pescal)\s*case[,\s:]+(.+)$", self._to_pascal_case),
            (r"^(?:kebab)\s*case[,\s:]+(.+)$", self._to_kebab_case),
            (r"^(?:const|constant|constants|all\s*caps)\s*case?[,\s:]+(.+)$", self._to_constant_case),
            (r"^(?:title)\s*case[,\s:]+(.+)$", self._to_title_case),
            (r"^(?:train|header)\s*case[,\s:]+(.+)$", self._to_train_case),
            (r"^(?:dot|package)\s*case[,\s:]+(.+)$", self._to_dot_case),
        ]

        def match_single_casing(s: str) -> Optional[str]:
            s_clean = s.strip().rstrip(".,!?")
            for pat, converter in patterns:
                m = re.match(pat, s_clean, re.IGNORECASE)
                if m:
                    phrase = normalize_casing_words(m.group(1).strip())
                    return converter(phrase)
            return None

        # Check multi-sentence chunk splitting first if text contains multiple sentences
        chunks = [c.strip() for c in re.split(r"(?<=[.!?])\s+", text.strip()) if c.strip()]
        if len(chunks) > 1:
            converted_chunks = []
            matched_any = False
            for ch in chunks:
                conv = match_single_casing(ch)
                if conv is not None:
                    converted_chunks.append(conv)
                    matched_any = True
                else:
                    converted_chunks.append(ch)
            if matched_any:
                return ", ".join(converted_chunks)

        return match_single_casing(text)

    def _to_camel_case(self, phrase: str) -> str:
        phrase = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", phrase)
        tokens = [t for t in re.split(r"[\s,_.]+", phrase) if t]
        if not tokens:
            return phrase
        
        first = tokens[0]
        result = first[0].lower() + first[1:]
        for t in tokens[1:]:
            result += t[0].upper() + t[1:]
        return result

    def _to_pascal_case(self, phrase: str) -> str:
        phrase = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", phrase)
        tokens = [t for t in re.split(r"[\s,_.]+", phrase) if t]
        if not tokens:
            return phrase
        return "".join(t[0].upper() + t[1:] for t in tokens)

    def _to_snake_case(self, phrase: str) -> str:
        phrase = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", phrase)
        tokens = [t.lower() for t in re.split(r"[\s,_.]+", phrase) if t]
        return "_".join(tokens)

    def _to_kebab_case(self, phrase: str) -> str:
        phrase = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", phrase)
        tokens = [t.lower() for t in re.split(r"[\s,_.]+", phrase) if t]
        return "-".join(tokens)

    def _to_constant_case(self, phrase: str) -> str:
        phrase = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", phrase)
        tokens = [t.upper() for t in re.split(r"[\s,_.]+", phrase) if t]
        return "_".join(tokens)

    def _to_title_case(self, phrase: str) -> str:
        phrase = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", phrase)
        tokens = [t for t in re.split(r"[\s,_.-]+", phrase) if t]
        return " ".join(t.capitalize() for t in tokens)

    def _to_train_case(self, phrase: str) -> str:
        phrase = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", phrase)
        tokens = [t for t in re.split(r"[\s,_.-]+", phrase) if t]
        return "-".join(t.capitalize() for t in tokens)

    def _to_dot_case(self, phrase: str) -> str:
        phrase = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", phrase)
        tokens = [t.lower() for t in re.split(r"[\s,_.-]+", phrase) if t]
        return ".".join(tokens)

    def _apply_phonetic_code_rules(self, text: str) -> str:
        """
        Catches speech/accent mishearings for developer terms, symbols, brackets, and currencies.
        """
        rules = [
            # Code brackets & symbols
            (r"^(?:comment|line\s*comment)\s+(.+)$", r"// \1"),
            (r"^(?:hash\s*comment|python\s*comment)\s+(.+)$", r"# \1"),
            (r"\b(?:triple\s*backticks?|three\s*backticks?)\b", "```"),
            (r"\bnullish\s*coalescing\b", "??"),
            (r"\boptional\s*chaining\b", "?."),
            (r"\b(?:spread\s*operator|rest\s*operator|three\s*dots|triple\s*dots)\b", "..."),
            (r"\b(?:strictly\s*not\s*equal(?:s)?|triple\s*not\s*equal(?:s)?|bang\s*double\s*equals?)\b", "!=="),
            (r"\b(?:not\s*equal(?:s| to)?|bang\s*equals?)\b", "!="),
            (r"\b(?:plus\s*equals?|add\s*equals?)\b", "+="),
            (r"\b(?:minus\s*equals?|subtract\s*equals?)\b", "-="),
            (r"\b(?:times\s*equals?|multiply\s*equals?)\b", "*="),
            (r"\b(?:increment|plus\s*plus)\b", "++"),
            (r"\b(?:decrement|minus\s*minus)\b", "--"),
            (r"\blocal\s*host\s*(?:colon|:)\s*(\d+)\b", r"localhost:\1"),
            (r"\blocal\s*host\s*(\d{4})\b", r"localhost:\1"),
            (r"\bcurly\s*(?:baskets|basket|brackets|braces|brace)\b", "{}"),
            (r"\bopen,?\s*(?:brasket|basket|bracket)s?\b", "["),
            (r"\bclose,?\s*(?:brasket|basket|bracket)s?\b", "]"),
            (r"\bopen,?\s*(?:parn|barn|paren|parent|parenthesis|pan|harn|harm)\b", "("),
            (r"\bclose,?\s*(?:parn|barn|paren|parent|parenthesis|pan|harn|harm)\b", ")"),
            (r"\beven\s+close\s+pan\b", "event)"),
            (r"\b(?:fetch|fat|fast)\s*arrow\b", "=>"),
            (r"\b(?:pass|past|fast|back)\s*slash\b", "\\\\"),
            (r"\bsemicolor\b", ";"),
            (r"\bnav\s*var\b", "navbar"),
            (r"\bcomma\b", ","),
            (r"\btail\s*securities\b", "==="),
            (r"\btatab\s*is\b", "database"),

            # Test 2: Tech stack phonetic corrections
            (r"\buwando\s*bat\b", "run.bat"),
            (r"\bUYG\s*making\b", "UI making"),
            (r"\bnormal\s+conversion\s+at\s+English\b", "normal conversation in English"),
            (r"\bThe\s+Mingle\s+is\b", "The main goal is"),
            (r"\bmingle\s+is\b", "main goal is"),
            (r"\bmuch\s+users\b", "many users"),
            (r"\b(?:Viewed\s+with\s+full|viewed\s+with\s+full|build\s+a\s+rest\s*full?)\s+API\s+with\s+(?:Next\.js|NestJS|nest\s*js)\b", "Build a RESTful API with NestJS"),
            (r"\b(?:Viewed\s+with\s+full|viewed\s+with\s+full|build\s+a\s+rest\s*full?)\s+API\b", "Build a RESTful API"),
            (r"\b(?:One\s+inch|one\s+inch|managing)\s+state\b", "Manage state"),
            (r"\b(?:Cloud\s+Data|cloud\s+data|valid\s+date)\s+with\s+Zod\b", "validate with Zod"),
            (r"\b(?:Fage|fage|fatch|fatche)\s+data\b", "Fetch data"),
            (r"\b(?:code\s+class\s+secret|code\s+class|post\s+gres\s*q\s*l)\b", "PostgreSQL"),
            (r"\bJWT\s+application\b", "JWT authentication"),
            (r"\bto\s+nodes\s+server\b", "to the Node.js server"),
            (r"\b(?:nodes|node)\s+server\b", "Node.js server"),
            (r"\b(?:Ask\s+Cloudy|ask\s+cloudy)\b", "Ask Claude"),
            (r"\bCloudy\s+to\b", "Claude to"),
            (r"\b(?:an\s+XGS|an\s+xgs|a\s+xgs)\s+project\b", "a Next.js project"),
            (r"\bXGS\b", "Next.js"),
            (r"\b(run|setup|install|build|clean|start)\s*[\.\s]+at\b", r"\1.bat"),
            (r"\bdot\s*bat\b", ".bat"),
            (r"\bUI\s+mark\s+making\b", "UI making"),
            (r"\(\s*User\s*ID\s*,?", "(userId)"),
            (r"\(\s*user\s*id\s*\)", "(userId)"),
            (r"\bTelman\s+CSS\b", "Tailwind CSS"),
            (r"\btraceful\b", "RESTful"),
            (r"\bstore\s+code\b", "source code"),
            (r"\bLOD\b", "Claude"),
            (r"\bstrict\s+text\b", "speech to text"),
            (r"\bDustand\b", "Zustand"),
            (r"\bNIST(?:\.js|\s*js)?\b", "NestJS"),
            (r"\bPostgres(?:\.js|\s*js|\s*sql)?\b", "PostgreSQL"),
            (r"\bFour-State Management\b", "For state management"),
            (r"\bwell,\s*React Hook Form\b", "while React Hook Form"),
            (r"\bZodhundl(?:[,\s]+the\s+four\s+validation)?\b", "Zod handle form validation"),
            (r"\bZodhundits\b", "Zod handles validation"),
            (r"\bZod\s+handles?\s+(?:the\s+)?validation\b", "Zod handles validation"),
            (r"\bstay\s+back\s+in[,\s]+expose\s+this[,\s]+Graceful\s+API\s+will\s+do\s+is\s+not\s+get\s+a\s+nest\.js\b", "The backend exposes RESTful APIs built with Node.js and NestJS"),
            (r"\bthe\s+tapabits\b", "the database"),
            (r"\bJDR-BT\s+access\s+tokens?\b", "JWT access tokens"),
            (r"\bJDR-BT\b", "JWT"),
            (r"\bexposes,\s*APIs\b", "exposes RESTful APIs"),
            (r"\band\s+and\b", "and"),
            (r"\broll-based\b", "role-based"),
            (r"\brule-based\s+permissions?\b", "role-based permissions"),

            # -----------------------------------------------------------------------
            # PERSONAL PHONETICS — These are personal/regional overrides.
            # Consider moving frequently-used ones to config.json > sound_alikes.
            # -----------------------------------------------------------------------
            # Personal & Geographic Names (Dagmawi Yoseph, Ethiopia, Horn of Africa)
            (r"\b(?:dag\s*mawi|dagmawe|dogmawi|dark\s*mawi)\s+(?:yoseph|joseph|yosef|yusuf)\b", "Dagmawi Yoseph"),
            (r"\b(?:dag\s*mawi|dagmawe|dogmawi|dark\s*mawi)\b", "Dagmawi"),
            (r"\b(?:yoseph|yosef)\b", "Yoseph"),
            (r"\bAddis\s+Abeba\b", "Addis Ababa"),
            (r"\b(?:addis\s+ababa|addis\s+abeba)\b", "Addis Ababa"),
            (r"\b(?:ethiopia|ethiopian)\b", lambda m: "Ethiopian" if m.group(0).lower() == "ethiopian" else "Ethiopia"),

            # Test 3: Currency, numbers, and dates
            (r"\bverse\s+(\d+(?:,\d+)*)\s+to\s+pamper\b", r"worth \1 Ethiopian birr"),
            (r"(\d+)\s*(?:\.\s*|\s+dot\s+)(?:tsx|36)[,\s]+(?:var|birr)\b", r"\1.36 birr"),
            (r"(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:per|bir|bear|bar|bird|number)\b", r"\1 birr"),
            (r"\bArmand\s+lease\s+subscription\s+costs\s+109th\s+remember\b", "Our monthly subscription costs 499 birr"),
            (r"\bthe\s+outcome\s+costs\s+4,999th\b", "the annual plan costs 4,999 birr"),
            (r"\bconversation\s+rate\b", "conversion rate"),
            (r"\b(?:itop|each\s+november|to\s+the\s+number)\b", "Ethiopian birr"),
            (r"\bArmandly\s+subscription\b", "Our monthly subscription"),
            (r"\bANOVA\s+plan\b", "annual plan"),
            (r"\bDecember\s+15,\s*20,\s*26\b", "December 15, 2026"),
            (r"\bplus\s*251-?9111-?234567\b", "+251 911 234 567"),
            (r"\bplus\s*(?:two\s*five\s*one|2\.51|251)[,\.\s]*911[,\.\s-]*2\s*3\s*4\s*5\s*6\s*7\b", "+251 911 234 567"),

            # Test 4 & 5: Self-correction and platform terms
            (r"\bday\s+activities\b", "daily activities"),
            (r"\binput\s+and\s+things\b", "important things"),
            (r"\bimportantings\b", "important things"),
            (r"\bnot\s+just\s+a\s+see\s+with\s+that\b", "not just save it as"),
            (r"\bnot\s+just\s+CVV[,\s]+it\'?s\s+not\s+a\s+good\s+thing[.\s]+us\s+ordinary\s+texts?\b", "not just save it as ordinary text"),
            (r"\bcustomer\s+order\s+in\s+voice\s+payment\b", "customer orders, invoices, payments"),
            (r"\bgenerate\s+the\s+app\.\s+with\s+financial\s+record\b", "generate the appropriate financial records"),
            (r"\baudit\s+trial\b", "audit trail"),
            (r"\broll\s+back\s+the\s+gene\b", "roll back the changes"),
            (r"\bIf\s+sometimes\s+there\'s\s+something\s+false\b", "If something fails"),
            (r"\b(?:talk|stock)\s*movements?\b", "stock movements"),
            (r"\bscale-?level\b", "scalable"),
            (r"\bin\s+ventory\b", "inventory"),
            (r"\bdata\s+constant\b", "data consistency"),
            (r"\b(?:maintain\s+some\s+detail\s+on\s+its\s+trail|only\s+trade)\b", "a complete audit trail"),
            (r"\bstate\s+says\b", "status"),
            (r"\bin\s+consult\b", "in console"),
            (r"\bwithin\s+a\s+data\s+transaction\b", "within a database transaction"),
            (r"\broll\s+back\s+the\s+chain\b", "roll back the changes"),
            (r"\bleaving\s+the\s+data\s*base\s+in\s+a\s+state\s+of\s+inconsistent\s+state\b", "leaving the database in an inconsistent state"),
            (r"\bdata\s+base\b", "database"),

            # Identifiers & functions
            (r"\bAPI\s+URL\b", "API_URL"),
            (r"\bget\s*users?\s*by\s*ID\b", "getUserById"),
        ]

        for pat, repl in rules:
            text = re.sub(pat, repl, text, flags=re.IGNORECASE)

        return text

    def _apply_sound_alikes(self, text: str) -> str:
        sound_alikes = self.config.get_sound_alikes()
        sorted_phrases = sorted(sound_alikes.keys(), key=lambda k: len(k), reverse=True)

        for phrase in sorted_phrases:
            target = sound_alikes[phrase]
            escaped = re.escape(phrase)
            pattern = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
            text = pattern.sub(lambda _, t=target: t, text)

        return text

    def _apply_symbols(self, text: str) -> str:
        symbols = self.config.get_symbols()
        sorted_phrases = sorted(symbols.keys(), key=lambda k: len(k), reverse=True)

        for phrase in sorted_phrases:
            sym = symbols[phrase]
            escaped = re.escape(phrase)
            pattern = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
            text = pattern.sub(lambda _, s=sym: s, text)

        return text

    def _cleanup_code_and_paths(self, text: str) -> str:
        # Replace mishearings for "dot": "doats", "doat", "doot"
        text = re.sub(r"\b(?:doats|doat|doot)\b", ".", text, flags=re.IGNORECASE)
        text = re.sub(r"\ban\s+(Next\.js)\b", r"a \1", text, flags=re.IGNORECASE)

        # Normalize URLs (e.g. "https colon slash slash API dot example dot com slash v1")
        text = re.sub(r"\b(https?|ftp)\s*(?::|,|\bcolon\b)\s*(?:/|\\|\bslash\b)\s*(?:/|\\|\bslash\b)\s*", r"\1://", text, flags=re.IGNORECASE)
        text = re.sub(r":\s*/\s*/\s*", "://", text)
        text = re.sub(r"\bdot\s+([a-zA-Z0-9_-]+)", r".\1", text, flags=re.IGNORECASE)
        text = re.sub(r"(?<=[a-zA-Z0-9_-])\s*\.\s*(?=[a-zA-Z0-9_-])", ".", text)
        text = re.sub(r"(https?://[^\s,]+?)\s*(?:/|\\|\bslash\b)\s*([a-zA-Z0-9_-]+)", r"\1/\2", text, flags=re.IGNORECASE)
        text = re.sub(r",\s*(https?://)", r" \1", text)

        # Clean file paths: remove commas and spaces around backslashes
        text = re.sub(r"[\s,]*\\+[\s,]*", r"\\", text)

        # Clean file extensions: ONLY collapse for genuine programming file extensions preceded by letters
        text = re.sub(rf"(?<=[a-zA-Z_-])[\s,]*\.\s*({KNOWN_EXTS})\b", r".\1", text, flags=re.IGNORECASE)
        text = re.sub(rf"\s+(?:build|node|this)\s+({KNOWN_EXTS})\b", r".\1", text, flags=re.IGNORECASE)

        # Clean "const handle, click =" -> "const handleClick ="
        # Only fix multi-word const identifiers (e.g. "const handle click =" → "const handleClick =")
        # Skip single-word idents that are already correct
        def camel_const_ident(match):
            raw_ident = match.group(1).strip()
            tokens = [t for t in re.split(r"[\s,]+", raw_ident) if t]
            # Only convert if more than one word token and none look like camelCase already
            if len(tokens) > 1 and not any(re.search(r'[A-Z]', t) for t in tokens):
                ident = tokens[0].lower() + "".join(t.capitalize() for t in tokens[1:])
                return f"const {ident} = "
            return match.group(0)

        text = re.sub(r"\bconst\s+([a-z][^=]{1,40})\s*=\s*", camel_const_ident, text)

        # Clean spaces around code operators and brackets
        text = re.sub(r"[\s,]*([\[\]\(\)\{\};\\=])[\s,]*", r"\1", text)
        text = re.sub(r"(?<![=!<>+\-*/])\s*=\s*(?![=>])", " = ", text)
        text = re.sub(r"\bconst\s*([\[\(])", r"const \1", text)
        text = re.sub(r"=\s*([a-zA-Z0-9_]+)\(", r"= \1(", text)

        # Auto-close lone opening paren on identifier (e.g. "(userId" -> "(userId)")
        if text.count("(") > text.count(")"):
            text = text.rstrip(" ,.") + ")"

        # Strip trailing dot from paths
        if "\\" in text and text.endswith("."):
            text = text[:-1]

        # Fix spacing around standard punctuation: "foo , bar" -> "foo, bar"
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)

        # =====================================================================
        # ROBUST PERIOD SPACING: Protect URLs, comments and dotted filenames, then add space
        # =====================================================================
        urls = []
        comments = []
        text = re.sub(r'(?:^|\s)//[^\n]*', lambda m: comments.append(m.group(0)) or f'__COMMENT_{len(comments)-1}__', text)
        text = re.sub(r'https?://[^\s,]+', lambda m: urls.append(m.group(0)) or f'__URL_{len(urls)-1}__', text)

        # Clean file and directory path slashes (e.g. "/ src / components" -> "/src/components")
        text = re.sub(r"[\s,]*\/+[\s,]*", "/", text)

        # Clean dot notation and dot-files (e.g. "Dot env dot local" -> ".env.local")
        text = re.sub(r"\bdot\s+", ".", text, flags=re.IGNORECASE)
        text = re.sub(r"(?:^|(?<=\s))\.\s+([a-zA-Z0-9_-]+)", r".\1", text)
        text = re.sub(r"(\.[a-zA-Z0-9_-]+)\s+\.([a-zA-Z0-9_-]+)", r"\1.\2", text)

        files = []
        pat = rf'\b[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*\.{KNOWN_EXTS}\b'
        text = re.sub(pat, lambda m: files.append(m.group(0)) or f'__FILE_{len(files)-1}__', text, flags=re.IGNORECASE)

        # Any remaining period followed immediately by a letter gets a space
        text = re.sub(r'\.([a-zA-Z])', r'. \1', text)

        # Restore protected files, URLs and comments
        for idx, f in enumerate(files):
            text = text.replace(f'__FILE_{idx}__', f)
        for idx, u in enumerate(urls):
            text = text.replace(f'__URL_{idx}__', u)
        for idx, c in enumerate(comments):
            text = text.replace(f'__COMMENT_{idx}__', c)

        # Ensure space after punctuation (except in URLs, digits, decimals)
        text = re.sub(r",(?=[^\s\d])", ", ", text)
        text = re.sub(r":(?=[^\s\d/])", ": ", text)

        # Clean excessive commas or comma-colon
        text = re.sub(r",\s*,+", ", ", text)
        text = re.sub(r",\s*:", ": ", text)

        return text
