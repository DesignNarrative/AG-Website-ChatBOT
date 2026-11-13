"""
Abhinav Group AI Chatbot — Knowledge Chunker (Phase 4)
Splits text into overlapping chunks suitable for RAG retrieval.

Strategy:
  - 400-token chunks with 80-token overlap
  - Respect paragraph boundaries — never split mid-sentence
  - Tag each chunk with project, category, language, and verification status
  - Only approved chunks are used at query time
"""
from __future__ import annotations

import hashlib
import re
from typing import List, Optional


# Approximate tokens — 1 token ≈ 4 chars for English, ~2 for Hindi/Devanagari
def _char_budget(tokens: int, lang: str = "en") -> int:
    return tokens * 2 if lang == "hi" else tokens * 4


CHUNK_TOKENS   = 400
OVERLAP_TOKENS = 80
MIN_CHUNK_TOKENS = 50   # Discard tiny fragments


class TextChunk:
    """A single chunk of text ready to be embedded and stored."""

    def __init__(
        self,
        content: str,
        source_id: str,
        chunk_index: int,
        project_name: Optional[str] = None,
        category: str = "general_realestate",
        language: str = "en",
        is_verified_fact: bool = False,
        metadata: Optional[dict] = None,
    ):
        self.content         = content.strip()
        self.source_id       = source_id
        self.chunk_index     = chunk_index
        self.project_name    = project_name
        self.category        = category
        self.language        = language
        self.is_verified_fact = is_verified_fact
        self.metadata        = metadata or {}
        self.content_hash    = hashlib.sha256(self.content.encode()).hexdigest()

    def __repr__(self) -> str:
        return f"<TextChunk [{self.category}] {len(self.content)}ch>"


class KnowledgeChunker:
    """
    Splits raw text into overlapping chunks for RAG indexing.

    Usage:
        chunker = KnowledgeChunker()
        chunks = chunker.chunk_text(
            text="...",
            source_id="source-uuid",
            project_name="Samsara",
            category="project_overview",
        )
    """

    def __init__(
        self,
        chunk_tokens: int = CHUNK_TOKENS,
        overlap_tokens: int = OVERLAP_TOKENS,
        min_tokens: int = MIN_CHUNK_TOKENS,
    ):
        self.chunk_tokens   = chunk_tokens
        self.overlap_tokens = overlap_tokens
        self.min_tokens     = min_tokens

    def chunk_text(
        self,
        text: str,
        source_id: str,
        project_name: Optional[str] = None,
        category: str = "general_realestate",
        language: str = "en",
        is_verified_fact: bool = False,
        metadata: Optional[dict] = None,
    ) -> List[TextChunk]:
        """Split text into overlapping chunks."""
        text = self._clean_text(text)
        if not text:
            return []

        char_size    = _char_budget(self.chunk_tokens, language)
        char_overlap = _char_budget(self.overlap_tokens, language)
        char_min     = _char_budget(self.min_tokens, language)

        # Split into paragraphs first, then sentences
        paragraphs = self._split_paragraphs(text)
        chunks     = []
        current    = ""
        idx        = 0

        for para in paragraphs:
            if len(current) + len(para) + 2 <= char_size:
                current += ("\n\n" if current else "") + para
            else:
                if current and len(current.strip()) >= char_min:
                    chunks.append(TextChunk(
                        content=current.strip(),
                        source_id=source_id,
                        chunk_index=idx,
                        project_name=project_name,
                        category=category,
                        language=language,
                        is_verified_fact=is_verified_fact,
                        metadata=metadata,
                    ))
                    idx += 1
                    # Overlap: carry last N chars of current into next chunk
                    overlap_text = current[-char_overlap:] if len(current) > char_overlap else current
                    current = overlap_text + "\n\n" + para if overlap_text else para
                else:
                    current = para

        # Flush remaining
        if current and len(current.strip()) >= char_min:
            chunks.append(TextChunk(
                content=current.strip(),
                source_id=source_id,
                chunk_index=idx,
                project_name=project_name,
                category=category,
                language=language,
                is_verified_fact=is_verified_fact,
                metadata=metadata,
            ))

        return chunks

    def chunk_structured_data(
        self,
        data: dict,
        source_id: str,
        project_name: Optional[str] = None,
    ) -> List[TextChunk]:
        """
        Convert structured project JSON data into text chunks.
        Each field becomes a targeted chunk for precise retrieval.
        """
        chunks = []
        base_meta = {"project": project_name, "source_type": "structured_data"}

        def make_chunk(content: str, category: str, is_verified: bool = False) -> TextChunk:
            return TextChunk(
                content=content,
                source_id=source_id,
                chunk_index=len(chunks),
                project_name=project_name,
                category=category,
                language="en",
                is_verified_fact=is_verified,
                metadata={**base_meta, "category": category},
            )

        name = data.get("project_name", "")

        # Overview chunk
        overview_parts = []
        if data.get("description"):
            overview_parts.append(data["description"])
        if data.get("tagline"):
            overview_parts.append(data["tagline"])
        if data.get("project_type"):
            overview_parts.append(f"Type: {data['project_type']}")
        if data.get("project_status"):
            overview_parts.append(f"Status: {data['project_status']}")
        if overview_parts:
            chunks.append(make_chunk(
                f"{name} — Overview\n" + "\n".join(overview_parts),
                "project_overview",
                is_verified=data.get("approval_status") == "APPROVED",
            ))

        # Location chunk
        loc_parts = []
        for field in ["location", "address", "city", "state", "pincode"]:
            if data.get(field):
                loc_parts.append(f"{field.title()}: {data[field]}")
        if data.get("connectivity"):
            loc_parts.append("Connectivity: " + str(data["connectivity"]))
        if data.get("nearby_facilities"):
            loc_parts.append("Nearby: " + str(data["nearby_facilities"]))
        if loc_parts:
            chunks.append(make_chunk(
                f"{name} — Location & Connectivity\n" + "\n".join(loc_parts),
                "project_location",
            ))

        # Configuration chunk
        if data.get("configurations"):
            config_text = f"{name} — Configurations\n"
            for cfg in data["configurations"]:
                config_text += f"  • {cfg.get('type', '')}: "
                if cfg.get("carpet_area_sqft"):
                    config_text += f"{cfg['carpet_area_sqft']} sq.ft carpet area"
                if cfg.get("price_min") and not data.get("price_verified"):
                    config_text += " (pricing — contact sales for current rates)"
                config_text += "\n"
            chunks.append(make_chunk(config_text, "project_configuration"))

        # Pricing chunk — only if verified
        if data.get("price_verified") and (data.get("price_min") or data.get("price_max")):
            price_text = f"{name} — Pricing\n"
            if data.get("price_min"):
                price_text += f"Starting from: ₹{data['price_min']:,.0f}\n"
            if data.get("price_max"):
                price_text += f"Up to: ₹{data['price_max']:,.0f}\n"
            if data.get("price_per_sqft_min"):
                price_text += f"Rate: ₹{data['price_per_sqft_min']:,.0f}/sq.ft onwards\n"
            chunks.append(make_chunk(price_text, "project_pricing", is_verified=True))
        elif data.get("price_min") or data.get("price_max"):
            # Unverified pricing — add note
            chunks.append(make_chunk(
                f"{name} — Pricing\nIndicative pricing available — contact sales team for verified current rates.\nPhone: +91 9309505388",
                "project_pricing",
                is_verified=False,
            ))

        # Amenities chunk
        if data.get("amenities"):
            amenity_text = f"{name} — Amenities\n" + str(data["amenities"])
            chunks.append(make_chunk(amenity_text, "project_amenities"))

        # RERA chunk
        if data.get("rera_number"):
            verified = data.get("rera_verified", False)
            rera_text = f"{name} — RERA Registration\nRERA Number: {data['rera_number']}\n"
            if not verified:
                rera_text += "Note: Please verify this number at the official MahaRERA portal."
            chunks.append(make_chunk(rera_text, "project_rera", is_verified=verified))

        # Possession chunk
        if data.get("possession_date"):
            poss_text = f"{name} — Possession\nExpected possession: {data['possession_date']}\n"
            if not data.get("possession_verified"):
                poss_text += "Note: Possession date subject to change — verify with sales team."
            chunks.append(make_chunk(poss_text, "project_possession",
                                     is_verified=data.get("possession_verified", False)))

        return chunks

    # ── Private helpers ────────────────────────────────────

    def _clean_text(self, text: str) -> str:
        """Remove noise: excessive whitespace, HTML artifacts, URLs."""
        text = re.sub(r'<[^>]+>', ' ', text)         # Strip HTML tags
        text = re.sub(r'https?://\S+', '[link]', text) # Mask URLs
        text = re.sub(r'\s{3,}', '\n\n', text)        # Collapse whitespace
        text = re.sub(r'\n{4,}', '\n\n\n', text)      # Max 3 blank lines
        return text.strip()

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs, trying to keep sentences intact."""
        paragraphs = re.split(r'\n{2,}', text)
        char_max = _char_budget(self.chunk_tokens, "en")
        result = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # If paragraph fits in one chunk, keep it whole
            if len(para) <= char_max:
                result.append(para)
                continue
            # Paragraph is too long — split at sentence boundaries
            sentences = re.split(r'(?<=[.!?।])\s+', para)
            sub = ""
            for sent in sentences:
                if not sub:
                    sub = sent
                elif len(sub) + 1 + len(sent) <= char_max:
                    sub += " " + sent
                else:
                    result.append(sub)
                    sub = sent
            if sub:
                result.append(sub)
        return result
