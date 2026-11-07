"""Deterministic CV chunking and rule-based criterion matching.

This module deliberately contains no LLM calls.  It converts the redacted CV
text into addressable chunks, derives a small requirement specification from
an approved rubric item, retrieves candidate chunks lexically, and returns a
decision only when a transparent rule is strong enough.  Unresolved criteria
are returned to the caller for the existing strict-schema LLM fallback.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.core.config import settings

RULES_VERSION = settings.DETERMINISTIC_RULES_VERSION

# Canonical concept -> accepted surface forms.  Keys and values are compared
# after normalize_text(), so accents/case/punctuation do not matter.
TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "javascript": ("javascript", "js"),
    "typescript": ("typescript", "ts"),
    "nodejs": ("nodejs", "node js", "node"),
    "react": ("react", "reactjs", "react js"),
    "angular": ("angular", "angularjs"),
    "vue": ("vue", "vuejs", "vue js"),
    "python": ("python",),
    "java": ("java",),
    "golang": ("golang", "go language"),
    "rust": ("rust",),
    "sql": ("sql", "structured query language"),
    "postgresql": ("postgresql", "postgres"),
    "mysql": ("mysql",),
    "mongodb": ("mongodb", "mongo"),
    "redis": ("redis",),
    "docker": ("docker",),
    "kubernetes": ("kubernetes", "k8s"),
    "aws": ("aws", "amazon web services"),
    "gcp": ("gcp", "google cloud", "google cloud platform"),
    "azure": ("azure", "microsoft azure"),
    "machine learning": ("machine learning", "ml"),
    "deep learning": ("deep learning",),
    "natural language processing": ("natural language processing", "nlp"),
    "data analysis": ("data analysis", "data analytics"),
    "microsoft excel": ("microsoft excel", "excel"),
    "power bi": ("power bi",),
    "testing": ("testing", "test automation", "automated testing", "qa"),
    "selenium": ("selenium",),
    "fastapi": ("fastapi",),
    "django": ("django",),
    "flask": ("flask",),
    "spring": ("spring", "spring boot"),
    "dotnet": ("dotnet", "dot net", "asp net"),
    "csharp": ("csharp", "c sharp"),
    "cplusplus": ("cplusplus", "c plus plus"),
    "english": ("english", "tieng anh"),
    "vietnamese": ("vietnamese", "tieng viet"),
    "japanese": ("japanese", "tieng nhat"),
    "korean": ("korean", "tieng han"),
    "chinese": ("chinese", "tieng trung", "mandarin"),
    "french": ("french", "tieng phap"),
    "german": ("german", "tieng duc"),
}

_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canonical, _variants in TERM_ALIASES.items():
    _ALIAS_TO_CANONICAL[_canonical] = _canonical
    for _variant in _variants:
        _ALIAS_TO_CANONICAL[_variant] = _canonical

SECTION_HEADINGS: dict[str, str] = {
    "summary": "SUMMARY",
    "professional summary": "SUMMARY",
    "profile": "SUMMARY",
    "objective": "SUMMARY",
    "career objective": "SUMMARY",
    "tom tat": "SUMMARY",
    "muc tieu nghe nghiep": "SUMMARY",
    "work experience": "WORK",
    "professional experience": "WORK",
    "employment history": "WORK",
    "work history": "WORK",
    "career history": "WORK",
    "experience": "WORK",
    "kinh nghiem": "WORK",
    "kinh nghiem lam viec": "WORK",
    "projects": "PROJECT",
    "project experience": "PROJECT",
    "selected projects": "PROJECT",
    "personal projects": "PROJECT",
    "du an": "PROJECT",
    "skills": "SKILL",
    "technical skills": "SKILL",
    "core skills": "SKILL",
    "technical expertise": "SKILL",
    "competencies": "SKILL",
    "core competencies": "SKILL",
    "ky nang": "SKILL",
    "ky nang ky thuat": "SKILL",
    "education": "EDUCATION",
    "academic background": "EDUCATION",
    "educational background": "EDUCATION",
    "hoc van": "EDUCATION",
    "trinh do hoc van": "EDUCATION",
    "certifications": "CERTIFICATION",
    "certification": "CERTIFICATION",
    "certificates": "CERTIFICATION",
    "certificate": "CERTIFICATION",
    "licenses": "CERTIFICATION",
    "chung chi": "CERTIFICATION",
    "languages": "LANGUAGE",
    "language": "LANGUAGE",
    "language skills": "LANGUAGE",
    "language proficiency": "LANGUAGE",
    "ngoai ngu": "LANGUAGE",
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "candidate", "candidates",
    "can", "capability", "degree", "developer", "development", "engineer",
    "experience", "experienced", "for", "from", "in", "including", "is",
    "knowledge", "level", "minimum", "of", "on", "or", "plus", "proficiency",
    "proficient", "proven", "required", "requirement", "requirements", "skill",
    "skills", "strong", "the", "to", "using", "with", "work", "working",
    "year", "years", "nam", "kinh", "nghiem", "ky", "nang", "ung", "vien",
    "co", "trong", "va", "voi", "ve", "cac", "duoc", "cho", "tu",
}

GENERIC_TERMS = {
    "bachelor", "master", "phd", "degree", "university", "college", "school",
    "certificate", "certification", "certified", "license", "language",
    "english", "vietnamese", "japanese", "korean", "chinese", "french", "german",
}

LANGUAGE_NAMES = (
    "english", "vietnamese", "japanese", "korean", "chinese", "mandarin",
    "french", "german", "spanish",
)

DEGREE_PATTERNS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (5, ("phd", "ph d", "doctorate", "doctoral degree", "tien si")),
    (4, ("master", "masters", "msc", "mba", "meng", "thac si")),
    (3, ("bachelor", "bachelors", "bsc", "beng", "bs", "ba", "cu nhan")),
    (2, ("associate degree", "cao dang")),
    (1, ("high school", "thpt", "trung hoc pho thong")),
)

CEFR_RANK = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6}
QUALITATIVE_LANGUAGE_RANK = {
    "basic": 1,
    "elementary": 2,
    "intermediate": 3,
    "professional": 4,
    "fluent": 5,
    "advanced": 5,
    "native": 6,
    "bilingual": 6,
}


def normalize_text(value: Any) -> str:
    """Normalize for deterministic lexical matching.

    Accents are removed and punctuation becomes whitespace.  A few symbols
    with semantic value (C++, C#, .NET, Node.js) are expanded first so they
    do not collapse into meaningless one-letter tokens.
    """
    text = str(value or "").lower()
    text = re.sub(r"c\+\+", " cplusplus ", text)
    text = re.sub(r"c#", " csharp ", text)
    text = re.sub(r"(?<![a-z0-9])\.net(?![a-z0-9])", " dotnet ", text)
    text = re.sub(r"node\.js", " nodejs ", text)
    text = re.sub(r"react\.js", " reactjs ", text)
    text = re.sub(r"vue\.js", " vuejs ", text)
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    alnum = "".join(ch if ch.isalnum() else " " for ch in without_accents)
    return " ".join(alnum.split())


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    phrase = normalize_text(phrase)
    if not phrase:
        return False
    return f" {phrase} " in f" {normalized_text} "


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    text: str
    page_number: int | None
    char_start: int
    char_end: int
    section: str = "OTHER"

    @property
    def normalized(self) -> str:
        return normalize_text(self.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "page_number": self.page_number,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "section": self.section,
        }


@dataclass(frozen=True)
class TermGroup:
    label: str
    variants: tuple[str, ...]


@dataclass(frozen=True)
class RequirementSpec:
    criterion_id: str
    name: str
    category: str
    kind: str
    terms: tuple[TermGroup, ...] = ()
    min_years: float | None = None
    required_degree_level: int | None = None
    required_languages: tuple[str, ...] = ()
    required_ielts: float | None = None
    required_toeic: int | None = None
    required_cefr: str | None = None
    required_language_rank: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "name": self.name,
            "category": self.category,
            "kind": self.kind,
            "terms": [
                {"label": term.label, "variants": list(term.variants)}
                for term in self.terms
            ],
            "min_years": self.min_years,
            "required_degree_level": self.required_degree_level,
            "required_languages": list(self.required_languages),
            "required_ielts": self.required_ielts,
            "required_toeic": self.required_toeic,
            "required_cefr": self.required_cefr,
            "required_language_rank": self.required_language_rank,
            "rule_version": RULES_VERSION,
        }


@dataclass
class _Candidate:
    chunk: DocumentChunk
    matched_labels: list[str] = field(default_factory=list)
    coverage: float = 0.0
    strength: float = 0.0


class DeterministicMatchingEngine:
    """Chunk, retrieve and decide measurable criteria without an LLM."""

    VERSION = RULES_VERSION

    # ------------------------------------------------------------------ text
    @staticmethod
    def _detect_heading(line: str) -> str | None:
        cleaned = line.strip().rstrip(":").strip()
        normalized = normalize_text(cleaned)
        if not normalized or len(cleaned) > 80:
            return None
        if normalized in SECTION_HEADINGS:
            return SECTION_HEADINGS[normalized]
        # Short all-caps headings such as "WORK EXPERIENCE" are covered by the
        # exact map above; also accept a known heading followed by a colon.
        for heading, section in SECTION_HEADINGS.items():
            if (normalized == heading or normalized.startswith(heading + " ")) and (
                line.strip().endswith(":") or cleaned.isupper() or len(normalized.split()) <= 4
            ):
                return section
        return None

    def chunk_document(self, text: str, max_chars: int = 900) -> list[DocumentChunk]:
        if max_chars < 100:
            raise ValueError("max_chars must be at least 100")
        source = text or ""
        raw: list[tuple[int, int, int | None, str]] = []
        page_number: int | None = None
        section = "OTHER"
        paragraph: list[tuple[int, int]] = []

        def flush_paragraph() -> None:
            if not paragraph:
                return
            start, end = paragraph[0][0], paragraph[-1][1]
            self._append_split(source, start, end, page_number, section, max_chars, raw)
            paragraph.clear()

        offset = 0
        for line in source.splitlines(True):
            content = line.rstrip("\r\n")
            line_start, line_end = offset, offset + len(content)
            offset += len(line)
            marker = re.fullmatch(r"\s*--- Page (\d+) ---\s*", content)
            if marker:
                flush_paragraph()
                page_number = int(marker.group(1))
                continue
            if not content.strip():
                flush_paragraph()
                continue
            inline_heading = re.match(r"\s*([^:]{2,50}):\s*(.+)$", content)
            if inline_heading and normalize_text(inline_heading.group(1)) in SECTION_HEADINGS:
                flush_paragraph()
                section = SECTION_HEADINGS[normalize_text(inline_heading.group(1))]
                paragraph.append((line_start + inline_heading.start(2), line_end))
                continue
            heading = self._detect_heading(content)
            if heading:
                flush_paragraph()
                section = heading
                continue
            paragraph.append((line_start, line_end))
        flush_paragraph()

        return [
            DocumentChunk(
                chunk_id=f"chunk-{index:04d}",
                text=source[start:end],
                page_number=page,
                char_start=start,
                char_end=end,
                section=chunk_section,
            )
            for index, (start, end, page, chunk_section) in enumerate(raw, start=1)
        ]

    @staticmethod
    def _append_split(
        source: str,
        start: int,
        end: int,
        page_number: int | None,
        section: str,
        max_chars: int,
        out: list[tuple[int, int, int | None, str]],
    ) -> None:
        if end - start <= max_chars:
            if source[start:end].strip():
                out.append((start, end, page_number, section))
            return
        segment = source[start:end]
        sentences: list[tuple[int, int]] = []
        for match in re.finditer(r"[^.!?;\n]+(?:[.!?;]+|$)", segment):
            chunk_start, chunk_end = match.span()
            while chunk_start < chunk_end and segment[chunk_start].isspace():
                chunk_start += 1
            while chunk_end > chunk_start and segment[chunk_end - 1].isspace():
                chunk_end -= 1
            if chunk_end > chunk_start:
                sentences.append((start + chunk_start, start + chunk_end))
        current: tuple[int, int] | None = None
        for sentence_start, sentence_end in sentences:
            if sentence_end - sentence_start > max_chars:
                if current:
                    out.append((current[0], current[1], page_number, section))
                    current = None
                word_start: int | None = None
                word_end = sentence_start
                for word in re.finditer(r"\S+", source[sentence_start:sentence_end]):
                    ws, we = sentence_start + word.start(), sentence_start + word.end()
                    if word_start is not None and we - word_start > max_chars:
                        out.append((word_start, word_end, page_number, section))
                        word_start = ws
                    if word_start is None:
                        word_start = ws
                    word_end = we
                if word_start is not None:
                    out.append((word_start, word_end, page_number, section))
                continue
            if current and sentence_end - current[0] > max_chars:
                out.append((current[0], current[1], page_number, section))
                current = (sentence_start, sentence_end)
            elif current:
                current = (current[0], sentence_end)
            else:
                current = (sentence_start, sentence_end)
        if current:
            out.append((current[0], current[1], page_number, section))

    # ---------------------------------------------------------- requirements
    @staticmethod
    def _add_term(groups: dict[str, TermGroup], phrase: Any) -> None:
        normalized = normalize_text(phrase)
        if not normalized or len(normalized) < 2:
            return
        canonical = _ALIAS_TO_CANONICAL.get(normalized)
        variants = {normalized}
        if canonical:
            variants.update(TERM_ALIASES[canonical])
            label = canonical
        else:
            label = normalized
            # A multi-word phrase should also retrieve on its meaningful
            # constituent tokens, e.g. "Python programming" -> "python".
            for token in normalized.split():
                if len(token) >= 3 and token not in STOPWORDS:
                    variants.add(token)
                    if token in _ALIAS_TO_CANONICAL:
                        variants.update(TERM_ALIASES[_ALIAS_TO_CANONICAL[token]])
        if label in GENERIC_TERMS and label not in TERM_ALIASES:
            return
        if label in groups:
            merged = tuple(sorted(set(groups[label].variants) | variants))
            groups[label] = TermGroup(label=label, variants=merged)
        else:
            groups[label] = TermGroup(label=label, variants=tuple(sorted(variants)))

    @staticmethod
    def _parse_min_years(combined: str) -> float | None:
        normalized = normalize_text(combined)
        values: list[float] = []
        for match in re.finditer(
            r"(\d+(?:[.,]\d+)?)\s*(?:-|to)\s*(\d+(?:[.,]\d+)?)\s*(?:years?|yrs?|nam)\b",
            normalized,
        ):
            values.append(float(match.group(1).replace(",", ".")))
        for match in re.finditer(
            r"(\d+(?:[.,]\d+)?)\s*\+?\s*(?:years?|yrs?|nam)\b", normalized
        ):
            values.append(float(match.group(1).replace(",", ".")))
        return max(values) if values else None

    @staticmethod
    def _required_degree_level(normalized: str) -> int | None:
        for level, patterns in DEGREE_PATTERNS:
            if any(_contains_phrase(normalized, pattern) for pattern in patterns):
                return level
        if "degree" in normalized.split() or "bang dai hoc" in normalized:
            return 3
        return None

    @staticmethod
    def _degree_level_in(normalized: str) -> int | None:
        levels = [
            level
            for level, patterns in DEGREE_PATTERNS
            if any(_contains_phrase(normalized, pattern) for pattern in patterns)
        ]
        if levels:
            return max(levels)
        if _contains_phrase(normalized, "university") or _contains_phrase(normalized, "college"):
            return 3
        return None

    def build_requirement_spec(self, criterion: dict[str, Any]) -> RequirementSpec:
        name = str(criterion.get("name") or "")
        description = str(criterion.get("description") or "")
        combined = f"{name}. {description}"
        normalized = normalize_text(combined)

        raw_keywords = criterion.get("expected_evidence_keywords") or []
        if isinstance(raw_keywords, str):
            try:
                import json

                parsed = json.loads(raw_keywords)
                raw_keywords = parsed if isinstance(parsed, list) else [raw_keywords]
            except (ValueError, TypeError):
                raw_keywords = [raw_keywords]

        groups: dict[str, TermGroup] = {}
        for keyword in raw_keywords if isinstance(raw_keywords, list) else []:
            self._add_term(groups, keyword)
        self._add_term(groups, name)
        # Scan the criterion text for known concepts (aliases cover both the
        # JD and CV surface forms, e.g. JD "JS" versus CV "JavaScript").
        for canonical, variants in TERM_ALIASES.items():
            if any(_contains_phrase(normalized, variant) for variant in variants):
                self._add_term(groups, canonical)
        if not groups:
            for token in normalized.split():
                if len(token) >= 3 and token not in STOPWORDS and token not in GENERIC_TERMS:
                    self._add_term(groups, token)
                if len(groups) >= 6:
                    break

        min_years = self._parse_min_years(combined)
        required_degree = self._required_degree_level(normalized)
        required_languages = tuple(
            language for language in LANGUAGE_NAMES if _contains_phrase(normalized, language)
        )
        ielts = re.search(r"ielts\s*(?:band\s*)?(\d+(?:[.,]\d+)?)", normalized)
        toeic = re.search(r"toeic\s*(\d{3,4})", normalized)
        cefr = re.search(r"\b([abc][12])\b", normalized)
        qualitative_rank = None
        for label, rank in QUALITATIVE_LANGUAGE_RANK.items():
            if _contains_phrase(normalized, label):
                qualitative_rank = rank if qualitative_rank is None else max(qualitative_rank, rank)

        has_certification = any(
            marker in normalized
            for marker in ("certif", "licence", "license", "chung chi")
        )
        has_degree = required_degree is not None or any(
            marker in normalized for marker in ("degree", "bachelor", "master", "phd", "cu nhan", "thac si", "tien si")
        )
        has_language = bool(required_languages) and any(
            marker in normalized
            for marker in ("language", "ielts", "toeic", "cefr", "fluent", "proficiency",
                           "communication", "tieng", "ngoai ngu", "giao tiep")
        )

        if has_language:
            kind = "LANGUAGE"
        elif has_certification:
            kind = "CERTIFICATION"
        elif has_degree:
            kind = "DEGREE"
        elif min_years is not None:
            kind = "YEARS"
        else:
            kind = "SKILL"

        return RequirementSpec(
            criterion_id=str(criterion.get("criterion_id") or ""),
            name=name,
            category=str(criterion.get("category") or ""),
            kind=kind,
            terms=tuple(list(groups.values())[:12]),
            min_years=min_years,
            required_degree_level=required_degree if kind == "DEGREE" else None,
            required_languages=required_languages if kind == "LANGUAGE" else (),
            required_ielts=float(ielts.group(1).replace(",", ".")) if ielts else None,
            required_toeic=int(toeic.group(1)) if toeic else None,
            required_cefr=cefr.group(1).upper() if cefr else None,
            required_language_rank=qualitative_rank if kind == "LANGUAGE" else None,
        )

    # ------------------------------------------------------------- durations
    @staticmethod
    def _explicit_years_in(text: str) -> list[float]:
        normalized = normalize_text(text)
        values = [
            float(match.group(1).replace(",", "."))
            for match in re.finditer(
                r"(\d+(?:[.,]\d+)?)\s*\+?\s*(?:years?|yrs?|nam)\b", normalized
            )
        ]
        number_words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
        }
        for match in re.finditer(
            r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
            r"(?:years?|yrs?)\b", normalized
        ):
            values.append(float(number_words[match.group(1)]))
        return values

    @staticmethod
    def _date_intervals_in(text: str, current_year: int) -> list[tuple[int, int]]:
        """Return [start_month, end_month) intervals from date ranges."""
        lowered = str(text or "").lower()
        intervals: list[tuple[int, int]] = []
        pattern = re.compile(
            r"(?:(0?[1-9]|1[0-2])\s*/\s*)?(20\d{2})\s*(?:-|–|—|\bto\b|\buntil\b)\s*"
            r"(?:(0?[1-9]|1[0-2])\s*/\s*)?(20\d{2}|present|now|current|nay|hien nay)"
        )
        for match in pattern.finditer(lowered):
            start_month = int(match.group(1)) if match.group(1) else 1
            start = int(match.group(2)) * 12 + (start_month - 1)
            end_token = match.group(4)
            if end_token.isdigit():
                end_month = int(match.group(3)) if match.group(3) else 12
                end = int(end_token) * 12 + end_month
            else:
                end = current_year * 12 + 12
            if end > start:
                intervals.append((start, end))
        return intervals

    @staticmethod
    def _merged_interval_years(intervals: list[tuple[int, int]]) -> float:
        if not intervals:
            return 0.0
        total_months = 0
        ordered_intervals = sorted(intervals)
        current_start, current_end = ordered_intervals[0]
        for start, end in ordered_intervals[1:]:
            if start <= current_end:
                current_end = max(current_end, end)
            else:
                total_months += current_end - current_start
                current_start, current_end = start, end
        total_months += current_end - current_start
        return round(total_months / 12, 2)

    @staticmethod
    def _iter_strings(value: Any):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from DeterministicMatchingEngine._iter_strings(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from DeterministicMatchingEngine._iter_strings(item)

    def candidate_years_experience(
        self,
        candidate_profile: dict[str, Any] | None,
        chunks: list[DocumentChunk],
        relevant_chunk_ids: set[str] | None = None,
    ) -> float | None:
        candidates: list[float] = []
        profile = candidate_profile or {}
        total = profile.get("total_years_experience")
        try:
            total_value = float(total)
            if total_value > 0:
                candidates.append(total_value)
        except (TypeError, ValueError):
            pass
        for value in self._iter_strings(profile):
            candidates.extend(self._explicit_years_in(value))
            intervals = self._date_intervals_in(value, date.today().year)
            if intervals:
                candidates.append(self._merged_interval_years(intervals))

        relevant = [
            chunk for chunk in chunks
            if (relevant_chunk_ids is None or chunk.chunk_id in relevant_chunk_ids)
            and chunk.section in {"WORK", "PROJECT", "SUMMARY"}
        ]
        for chunk in relevant:
            candidates.extend(self._explicit_years_in(chunk.text))
        intervals: list[tuple[int, int]] = []
        for chunk in relevant:
            intervals.extend(self._date_intervals_in(chunk.text, date.today().year))
        if intervals:
            candidates.append(self._merged_interval_years(intervals))
        return max(candidates) if candidates else None

    # -------------------------------------------------------------- matching
    @staticmethod
    def _matched_labels(spec: RequirementSpec, normalized_chunk: str) -> list[str]:
        return [
            term.label
            for term in spec.terms
            if any(_contains_phrase(normalized_chunk, variant) for variant in term.variants)
        ]

    @staticmethod
    def _section_factor(kind: str, section: str) -> float:
        relevant = {
            "SKILL": {"WORK", "PROJECT", "SKILL"},
            "YEARS": {"WORK", "PROJECT"},
            "DEGREE": {"EDUCATION"},
            "CERTIFICATION": {"CERTIFICATION", "WORK"},
            "LANGUAGE": {"LANGUAGE"},
        }.get(kind, set())
        if section in relevant:
            return 1.0
        if section == "SUMMARY":
            return 0.82
        if section == "OTHER":
            return 0.72
        return 0.45

    def _candidates(self, spec: RequirementSpec, chunks: list[DocumentChunk]) -> list[_Candidate]:
        candidates: list[_Candidate] = []
        total_terms = max(1, len(spec.terms))
        for chunk in chunks:
            matched = self._matched_labels(spec, chunk.normalized)
            if not matched:
                continue
            coverage = len(matched) / total_terms
            strength = 0.30 + 0.62 * coverage * self._section_factor(spec.kind, chunk.section)
            if chunk.section in {"WORK", "PROJECT", "SKILL", "EDUCATION", "CERTIFICATION", "LANGUAGE"}:
                strength += 0.04
            candidates.append(_Candidate(
                chunk=chunk,
                matched_labels=matched,
                coverage=round(coverage, 4),
                strength=round(min(0.97, strength), 4),
            ))
        candidates.sort(key=lambda item: (-item.strength, -item.coverage, item.chunk.chunk_id))
        return candidates

    @staticmethod
    def _best_quote(candidate: _Candidate, spec: RequirementSpec) -> str:
        text = candidate.chunk.text
        sentences = []
        for match in re.finditer(r"[^.!?;\n]+(?:[.!?;]+|$)", text):
            sentence = match.group(0).strip()
            if sentence:
                sentences.append(sentence)
        if len(sentences) <= 1:
            return text.strip()[:340]

        def sentence_score(sentence: str) -> tuple[int, int, int]:
            normalized = normalize_text(sentence)
            matched = sum(
                1 for term in spec.terms
                if any(_contains_phrase(normalized, variant) for variant in term.variants)
            )
            signals = 0
            if DeterministicMatchingEngine._explicit_years_in(sentence):
                signals += 1
            if DeterministicMatchingEngine._degree_level_in(normalized) is not None:
                signals += 1
            if re.search(r"ielts|toeic|\b[abc][12]\b", normalized):
                signals += 1
            return matched, signals, -len(sentence)

        return max(sentences, key=sentence_score)

    @staticmethod
    def _finding(
        spec: RequirementSpec,
        candidate: _Candidate,
        outcome: str,
        strength: float,
        reasoning: str,
    ) -> dict[str, Any]:
        strength = round(min(0.99, max(0.0, strength)), 3)
        return {
            "criterion_id": spec.criterion_id,
            "outcome": outcome,
            "confidence": strength,
            "confidence_band": "HIGH" if strength >= 0.85 else "MEDIUM" if strength >= 0.65 else "LOW",
            "evidence_strength": strength,
            "decision_source": "RULE",
            "rule_version": RULES_VERSION,
            "evidence_chunk_id": candidate.chunk.chunk_id,
            "reasoning": reasoning,
            "evidence": {
                "verbatim_quote": DeterministicMatchingEngine._best_quote(candidate, spec),
                "page_number": candidate.chunk.page_number,
                "chunk_id": candidate.chunk.chunk_id,
                "char_start": candidate.chunk.char_start,
                "char_end": candidate.chunk.char_end,
            },
            "requires_verification": False,
        }

    def _evaluate_years(
        self,
        spec: RequirementSpec,
        chunks: list[DocumentChunk],
        candidate_profile: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        candidates = self._candidates(spec, chunks)
        relevant_ids = {candidate.chunk.chunk_id for candidate in candidates} or None
        years = self.candidate_years_experience(candidate_profile, chunks, relevant_ids)
        if years is None or spec.min_years is None:
            return None
        evidence_pool = candidates or [
            _Candidate(chunk=chunk, matched_labels=[], coverage=0.0, strength=0.6)
            for chunk in chunks if chunk.section in {"WORK", "PROJECT"}
        ]
        if not evidence_pool:
            return None

        def evidence_rank(candidate: _Candidate) -> tuple[int, float, str]:
            has_duration = 1 if (
                self._explicit_years_in(candidate.chunk.text)
                or self._date_intervals_in(candidate.chunk.text, date.today().year)
            ) else 0
            return has_duration, candidate.strength, candidate.chunk.chunk_id

        best = max(evidence_pool, key=evidence_rank)
        matched_text = ", ".join(best.matched_labels) if best.matched_labels else "experience history"
        if years >= spec.min_years:
            outcome = "STRONG_MATCH" if years >= spec.min_years + 2 or years >= spec.min_years * 1.5 else "MATCH"
            return self._finding(
                spec, best, outcome, max(best.strength, 0.88),
                f"Deterministic years rule: approximately {years:g} years found for "
                f"{matched_text}; requirement is {spec.min_years:g} years.",
            )
        return self._finding(
            spec, best, "NO_MATCH", max(best.strength, 0.8),
            f"Deterministic years rule: approximately {years:g} years found for "
            f"{matched_text}; requirement is {spec.min_years:g} years.",
        )

    def _evaluate_degree(
        self,
        spec: RequirementSpec,
        chunks: list[DocumentChunk],
        candidate_profile: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        required = spec.required_degree_level or 3
        education_chunks = [chunk for chunk in chunks if chunk.section == "EDUCATION"]
        best_chunk: DocumentChunk | None = None
        highest: int | None = None
        for pool in (education_chunks, chunks):
            for chunk in pool:
                level = self._degree_level_in(chunk.normalized)
                if level is not None and (highest is None or level > highest):
                    highest, best_chunk = level, chunk
            if highest is not None:
                break
        profile_levels = [
            level for value in self._iter_strings((candidate_profile or {}).get("education"))
            if (level := self._degree_level_in(normalize_text(value))) is not None
        ]
        if profile_levels:
            highest = max([highest or 0, *profile_levels])
        if highest is None or best_chunk is None:
            return None
        candidate = _Candidate(
            chunk=best_chunk, matched_labels=self._matched_labels(spec, best_chunk.normalized),
            coverage=1.0, strength=0.9,
        )
        if highest >= required:
            outcome = "STRONG_MATCH" if highest > required else "MATCH"
            return self._finding(
                spec, candidate, outcome, 0.92,
                f"Deterministic degree rule: education evidence reaches level {highest}; "
                f"requirement level is {required}.",
            )
        return self._finding(
            spec, candidate, "NO_MATCH", 0.78,
            f"Deterministic degree rule: highest education evidence is level {highest}; "
            f"requirement level is {required}.",
        )

    @staticmethod
    def _language_level_in(text: str) -> dict[str, float | int | str]:
        normalized = normalize_text(text)
        result: dict[str, float | int | str] = {}
        ielts = re.search(r"ielts\s*(?:band\s*)?(\d+(?:[.,]\d+)?)", normalized)
        toeic = re.search(r"toeic\s*(\d{3,4})", normalized)
        cefr = re.search(r"\b([abc][12])\b", normalized)
        if ielts:
            result["ielts"] = float(ielts.group(1).replace(",", "."))
        if toeic:
            result["toeic"] = int(toeic.group(1))
        if cefr:
            result["cefr"] = cefr.group(1).upper()
        for label, rank in QUALITATIVE_LANGUAGE_RANK.items():
            if _contains_phrase(normalized, label):
                result["rank"] = max(int(result.get("rank", 0)), rank)
        return result

    def _evaluate_language(
        self,
        spec: RequirementSpec,
        chunks: list[DocumentChunk],
    ) -> dict[str, Any] | None:
        candidates = [
            candidate for candidate in self._candidates(spec, chunks)
            if not spec.required_languages
            or any(language in candidate.matched_labels or _contains_phrase(candidate.chunk.normalized, language)
                   for language in spec.required_languages)
        ]
        if not candidates:
            return None
        # Prefer language-section chunks, then chunks carrying a level.
        def rank(candidate: _Candidate) -> tuple[int, int, float, str]:
            level = self._language_level_in(candidate.chunk.text)
            return (
                1 if candidate.chunk.section == "LANGUAGE" else 0,
                1 if level else 0,
                candidate.strength,
                candidate.chunk.chunk_id,
            )

        best = max(candidates, key=rank)
        level = self._language_level_in(best.chunk.text)
        language_text = ", ".join(spec.required_languages) or "the required language"

        comparisons: list[tuple[bool, bool]] = []  # (has_both, satisfied)
        if spec.required_ielts is not None:
            comparisons.append(("ielts" in level, bool(level.get("ielts", 0) >= spec.required_ielts) if "ielts" in level else False))
        if spec.required_toeic is not None:
            comparisons.append(("toeic" in level, bool(level.get("toeic", 0) >= spec.required_toeic) if "toeic" in level else False))
        if spec.required_cefr is not None:
            comparisons.append(("cefr" in level, CEFR_RANK.get(str(level.get("cefr", "")).lower(), 0) >= CEFR_RANK[spec.required_cefr.lower()] if "cefr" in level else False))
        if spec.required_language_rank is not None:
            comparisons.append(("rank" in level, int(level.get("rank", 0)) >= spec.required_language_rank if "rank" in level else False))

        if comparisons:
            if not any(has_both for has_both, _ in comparisons):
                return None  # A level is required but none is stated: let LLM/HR decide.
            satisfied = any(satisfied for has_both, satisfied in comparisons if has_both)
            if satisfied:
                return self._finding(
                    spec, best, "MATCH", max(best.strength, 0.86),
                    f"Deterministic language rule: {language_text} level evidence meets the requirement.",
                )
            return self._finding(
                spec, best, "NO_MATCH", max(best.strength, 0.78),
                f"Deterministic language rule: {language_text} level evidence is below the requirement.",
            )
        return self._finding(
            spec, best, "MATCH", max(best.strength, 0.8),
            f"Deterministic language rule: {language_text} is evidenced in the CV.",
        )

    def _evaluate_generic(
        self,
        spec: RequirementSpec,
        chunks: list[DocumentChunk],
    ) -> dict[str, Any] | None:
        candidates = self._candidates(spec, chunks)
        if not candidates:
            return None
        best = candidates[0]
        if best.coverage < 0.5 or best.strength < 0.58:
            return None
        quote = self._best_quote(best, spec)
        duration_years = self._explicit_years_in(quote)
        strong = (
            (duration_years and max(duration_years) >= 3)
            or (len(best.matched_labels) >= 2 and best.coverage >= 0.8
                and best.chunk.section in {"WORK", "PROJECT"})
        )
        outcome = "STRONG_MATCH" if strong else "MATCH"
        kind_label = "certification" if spec.kind == "CERTIFICATION" else "skill"
        return self._finding(
            spec, best, outcome, best.strength,
            f"Deterministic {kind_label} rule: matched {', '.join(best.matched_labels)} "
            f"in {best.chunk.section} evidence ({best.chunk.chunk_id}).",
        )

    def evaluate_criterion(
        self,
        criterion: dict[str, Any],
        chunks: list[DocumentChunk],
        candidate_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        spec = self.build_requirement_spec(criterion)
        if spec.kind == "YEARS":
            return self._evaluate_years(spec, chunks, candidate_profile)
        if spec.kind == "DEGREE":
            return self._evaluate_degree(spec, chunks, candidate_profile)
        if spec.kind == "LANGUAGE":
            return self._evaluate_language(spec, chunks)
        return self._evaluate_generic(spec, chunks)

    def evaluate_criteria(
        self,
        cv_text: str,
        criteria: list[dict[str, Any]],
        candidate_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return decisive rule findings plus the criteria left for fallback."""
        chunks = self.chunk_document(cv_text or "")
        findings: list[dict[str, Any]] = []
        unresolved: list[str] = []
        for criterion in criteria:
            finding = self.evaluate_criterion(criterion, chunks, candidate_profile)
            if finding:
                findings.append(finding)
            else:
                unresolved.append(str(criterion.get("criterion_id") or ""))
        return {
            "findings": findings,
            "unresolved_criterion_ids": unresolved,
            "chunks": [chunk.to_dict() for chunk in chunks],
            "candidate_years_experience": self.candidate_years_experience(candidate_profile, chunks),
            "rule_version": RULES_VERSION,
        }


deterministic_matcher = DeterministicMatchingEngine()
