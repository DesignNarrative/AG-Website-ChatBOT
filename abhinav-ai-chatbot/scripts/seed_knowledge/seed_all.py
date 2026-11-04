"""
Abhinav Group AI Chatbot — Knowledge Base Seeder
Phase 4: Seeds the database and vector store from crawled website data.

What this does:
1. Reads data/website-extraction/extracted_pages.json
2. Reads data/website-extraction/projects.json
3. Creates KnowledgeSource records in DB
4. Chunks text using KnowledgeChunker
5. Embeds chunks using the configured AI provider
6. Saves chunks to DB (knowledge_chunks table)
7. Saves embeddings to FAISS vector store

Usage:
    cd abhinav-ai-chatbot/backend
    python ../scripts/seed_knowledge/seed_all.py

Notes:
- Requires AI_PROVIDER=mock (or real key) to embed chunks
- All chunks are created with is_approved=False — developer must approve via admin dashboard
- Pricing chunks are always is_verified_fact=False until manually confirmed
- Run this script after each website re-crawl to update knowledge base
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Path setup ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = ROOT / "backend"
DATA_DIR = ROOT / "data" / "website-extraction"
sys.path.insert(0, str(BACKEND))

# ── Environment ──────────────────────────────────────────────────────────────
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///./abhinav_chatbot.db")
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("MDOC_ENABLED", "false")
os.environ.setdefault("CELERY_ENABLED", "false")
os.environ.setdefault("APP_SECRET_KEY", "seed_script_key_32chars_minimum_x1")
os.environ.setdefault("JWT_SECRET_KEY", "seed_script_jwt_32chars_minimum_x1")
os.environ.setdefault("DEBUG", "false")


# ── Project metadata (from official website + manual verification) ──────────
# IMPORTANT: All items below marked UNVERIFIED must be confirmed by Abhinav Group
#            before is_verified_fact=True is set.

KNOWN_PROJECTS = {
    "Samsara": {
        "project_name": "Samsara",
        "project_type": "residential",
        "project_status": "ongoing",
        "location": "Mukund Nagar",
        "city": "Pune",
        "state": "Maharashtra",
        "description": "Samsara is a premium luxury residential project by Abhinav Group featuring 3 BHK apartments in Mukund Nagar, Pune. The project offers spacious, modern homes in a well-connected prime location.",
        "configurations": [{"type": "3 BHK", "note": "Contact sales for carpet area details"}],
        "rera_number": "P52100079797",   # Extracted from website — verify at maharerait.maharashtra.gov.in
        "rera_verified": False,           # UNVERIFIED
        "price_verified": False,          # Pricing only on request — do not publish
        "possession_date": "June 2028",  # UNVERIFIED — from third-party sources
        "possession_verified": False,
        "official_url": "https://abhinavgroup.co.in/samsara-project-detail-page/",
        "sales_contact": "+91 9890393838",
        "approval_status": "PENDING",
        "amenities_note": "Details on website — verify before publishing",
    },
    "Pebbles Greenfield": {
        "project_name": "Pebbles Greenfield",
        "project_type": "residential",
        "project_status": "ongoing",
        "location": "Tathawade / Wakad",
        "city": "Pune",
        "state": "Maharashtra",
        "description": "Pebbles Greenfield is a green-certified residential project by Abhinav Group offering 2 & 3 BHK homes in Tathawade, near Wakad, Pune. The project is IGBC certified, emphasising sustainable and eco-friendly living.",
        "configurations": [
            {"type": "2 BHK", "note": "Contact sales for details"},
            {"type": "3 BHK", "note": "Contact sales for details"},
        ],
        "rera_number": "P52100045923",   # Extracted from website — verify at maharerait.maharashtra.gov.in
        "rera_verified": False,
        "price_verified": False,
        "possession_date": "Mid-2027",   # UNVERIFIED
        "possession_verified": False,
        "official_url": "https://abhinavgroup.co.in/pebbles-greenfields/",
        "sales_contact": "+91 9890393838",
        "approval_status": "PENDING",
        "green_certification": "IGBC Certified",
    },
    "The Curve": {
        "project_name": "The Curve",
        "project_type": "residential",
        "project_status": "ongoing",
        "location": "Virar West",
        "city": "Mumbai",
        "state": "Maharashtra",
        "description": "The Curve is a premium residential project by Abhinav Group offering 2 & 3 BHK homes in Virar West, Mumbai Metropolitan Region (MMR). The project offers modern architecture with excellent connectivity.",
        "configurations": [
            {"type": "2 BHK", "note": "Contact sales for details"},
            {"type": "3 BHK", "note": "Contact sales for details"},
        ],
        "rera_number": "PR1240002600667",  # Extracted from website — verify on MahaRERA
        "rera_verified": False,
        "price_verified": False,
        "possession_date": "June 2031",    # From official website
        "possession_verified": False,
        "official_url": "https://abhinavgroup.co.in/the-curve-virar/",
        "microsite_urls": ["https://thecurvevirar.in", "https://abhinavthecurve.in"],
        "sales_contact": "+91 9890393838",
        "approval_status": "PENDING",
    },
    "Aeromall": {
        "project_name": "Aeromall",
        "project_type": "commercial",
        "project_status": "ongoing",
        "location": "Airport Road, Lohegaon",
        "city": "Pune",
        "state": "Maharashtra",
        "description": "Aeromall is Pune's first 24×7 operational commercial mall by Abhinav Group, developed in partnership with Airports Authority of India (AAI) on Airport Road, Lohegaon, Pune. It offers commercial spaces for retail, F&B, and business.",
        "configurations": [{"type": "Commercial Space", "note": "Contact sales for available units"}],
        "rera_number": None,
        "rera_verified": False,
        "price_verified": False,
        "possession_date": None,
        "possession_verified": False,
        "official_url": "https://abhinavgroup.co.in/aeromall-project-detail-page/",
        "sales_contact": "+91 9890393838",
        "approval_status": "PENDING",
        "note": "PPP project with AAI — verify exact ownership and commercial terms before publishing",
    },
}

COMPANY_INFO = {
    "name": "Abhinav Group",
    "full_name": "Abhinav Infrastructure Pvt. Ltd.",
    "tagline": "Building trust, building homes",
    "website": "https://abhinavgroup.co.in",
    "office_address": "Office No. 302, Sanas Memories Building, CTS 927, F.C. Road, Shivajinagar, Pune 411005",
    "sales_phone": "+91 9890393838",
    "office_phone": "02025663051",
    "email": "sales@abhinavinfra.com",
    "sales_hours": "Monday to Saturday, 10 AM to 7 PM",
    "established": "Established real estate developer in Pune",
    "focus": "Quality residential and commercial developments in Pune and MMR",
}

NRI_INFO = """
Abhinav Group welcomes NRI (Non-Resident Indian) property buyers.
Key information for NRIs purchasing property in India:

1. FEMA Compliance: NRIs can purchase residential and commercial property in India under FEMA regulations.
2. Repatriation: NRIs can repatriate sale proceeds subject to RBI guidelines.
3. Home Loans: NRIs are eligible for home loans from Indian banks.
4. Power of Attorney: NRIs can designate a Power of Attorney (PoA) holder in India.
5. TDS on Purchase: Seller deducts TDS at applicable rate for NRI buyers.

For NRI-specific queries, please contact our sales team:
Phone: +91 9890393838
Email: sales@abhinavinfra.com
Hours: Monday to Saturday, 10 AM to 7 PM IST

Note: Tax and legal regulations change frequently. Always consult a qualified CA/lawyer before purchase.
"""

GENERAL_REALESTATE_FAQ = [
    {
        "question": "What is RERA and why is it important?",
        "answer": "RERA (Real Estate Regulatory Authority) is a government body that regulates real estate transactions in India. Under the RERA Act 2016, all projects with more than 8 apartments must be registered. RERA registration ensures transparency, timely delivery, and legal protection for buyers. Always verify a project's RERA number at maharerait.maharashtra.gov.in."
    },
    {
        "question": "What is carpet area vs built-up area?",
        "answer": "Carpet area is the net usable floor area within the walls — the area where you can place your carpet. Built-up area includes the carpet area plus the thickness of walls. Super built-up area (also called saleable area) additionally includes a share of common areas like lobby, lifts, and corridors. Under RERA, pricing must be quoted on carpet area basis."
    },
    {
        "question": "What is the home-buying process in Pune?",
        "answer": "The typical process: 1. Shortlist project and visit site. 2. Book the unit with a booking amount. 3. Sign the Agreement for Sale. 4. Arrange home loan if needed. 5. Register the sale deed at the sub-registrar office. 6. Take possession. 7. Apply for OC (Occupancy Certificate). Allow 2-4 weeks for loan processing."
    },
    {
        "question": "What documents should I check before buying?",
        "answer": "Key documents: RERA registration certificate, Title deed (clear ownership), NA (Non-Agricultural) order, IOD/CC (commencement certificate), approved building plans, Occupation Certificate (for ready properties), encumbrance certificate, and property card."
    },
]


async def seed():
    """Main seeding function."""
    print("\n" + "=" * 60)
    print("  ABHINAV GROUP KNOWLEDGE BASE SEEDER")
    print("  Phase 4 — Database + Vector Store Seeding")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    from app.database.session import init_db, AsyncSessionLocal
    from app.rag.chunker import KnowledgeChunker
    from app.rag.vector_store import FAISSVectorStore
    from app.ai.provider import get_ai_provider

    # Init DB
    print("\n[1] Initializing database ...")
    await init_db()
    print("    OK")

    # Init components
    chunker = KnowledgeChunker()
    vector_store = FAISSVectorStore(dim=768, index_dir=ROOT / "data" / "vector-index")
    ai_provider = get_ai_provider()
    print(f"[2] AI Provider: {ai_provider.provider_name}")
    print(f"[3] Vector store: {vector_store.count()} existing chunks")

    total_chunks = 0
    total_embedded = 0

    async with AsyncSessionLocal() as db:
        from app.models.knowledge import KnowledgeChunk, KnowledgeSource

        # ── Seed project knowledge ──────────────────────────────────────
        print("\n[4] Seeding project knowledge ...")
        for project_name, project_data in KNOWN_PROJECTS.items():
            print(f"\n    Project: {project_name}")

            # Create a KnowledgeSource record
            source = KnowledgeSource(
                source_type="manual_structured",
                source_url=project_data.get("official_url"),
                source_title=f"{project_name} — Structured Data",
                content_hash=None,
                is_active=True,
            )
            db.add(source)
            await db.flush()

            # Chunk the structured data
            chunks = chunker.chunk_structured_data(
                data=project_data,
                source_id=source.id,
                project_name=project_name,
            )
            print(f"    Chunks: {len(chunks)}")

            for chunk in chunks:
                # Embed
                try:
                    embedding = await ai_provider.embed(chunk.content)
                except Exception as e:
                    print(f"    WARNING: Embed failed for chunk: {e}")
                    embedding = None

                # Save to DB
                db_chunk = KnowledgeChunk(
                    source_id=source.id,
                    category=chunk.category,
                    content=chunk.content,
                    content_hash=chunk.content_hash,
                    language=chunk.language,
                    embedding=embedding,
                    embedding_dim=len(embedding) if embedding else None,
                    embedding_model=ai_provider.provider_name,
                    is_approved=False,       # Requires developer approval
                    is_verified_fact=chunk.is_verified_fact,
                    chunk_index=chunk.chunk_index,
                    metadata_={"project": project_name, **chunk.metadata},
                )
                db.add(db_chunk)
                await db.flush()

                # Add to vector store
                if embedding:
                    vector_store.add(
                        chunk_id=db_chunk.id,
                        vector=embedding,
                        metadata={
                            "content": chunk.content[:200],
                            "content_hash": chunk.content_hash,
                            "project": project_name,
                            "category": chunk.category,
                            "is_approved": False,
                            "is_verified_fact": chunk.is_verified_fact,
                        },
                    )
                    total_embedded += 1

                total_chunks += 1

        # ── Seed company info ───────────────────────────────────────────
        print("\n[5] Seeding company information ...")
        company_text = f"""
Abhinav Group — Company Information

Company: {COMPANY_INFO['name']} ({COMPANY_INFO['full_name']})
Website: {COMPANY_INFO['website']}
Tagline: {COMPANY_INFO['tagline']}

Sales Office:
{COMPANY_INFO['office_address']}

Contact:
Sales Phone: {COMPANY_INFO['sales_phone']}
Office Phone: {COMPANY_INFO['office_phone']}
Email: {COMPANY_INFO['email']}
Hours: {COMPANY_INFO['sales_hours']}

About:
{COMPANY_INFO['focus']}

Active Projects:
- Samsara: 3 BHK luxury residences, Mukund Nagar, Pune
- Pebbles Greenfield: 2 & 3 BHK IGBC-certified homes, Tathawade/Wakad, Pune
- The Curve: 2 & 3 BHK homes, Virar West, Mumbai MMR
- Aeromall: Commercial mall, Airport Road, Lohegaon, Pune
        """.strip()

        company_source = KnowledgeSource(
            source_type="manual_entry",
            source_url="https://abhinavgroup.co.in/about-us/",
            source_title="Abhinav Group Company Information",
        )
        db.add(company_source)
        await db.flush()

        company_chunks = chunker.chunk_text(
            company_text,
            source_id=company_source.id,
            category="company_info",
            is_verified_fact=False,  # Must be verified by Abhinav Group
        )
        for chunk in company_chunks:
            embedding = await ai_provider.embed(chunk.content)
            db_chunk = KnowledgeChunk(
                source_id=company_source.id,
                category=chunk.category,
                content=chunk.content,
                content_hash=chunk.content_hash,
                language="en",
                embedding=embedding,
                embedding_dim=len(embedding) if embedding else None,
                embedding_model=ai_provider.provider_name,
                is_approved=False,
                is_verified_fact=False,
                chunk_index=chunk.chunk_index,
                metadata_={"category": "company_info"},
            )
            db.add(db_chunk)
            await db.flush()
            if embedding:
                vector_store.add(db_chunk.id, embedding, {
                    "content": chunk.content[:200],
                    "content_hash": chunk.content_hash,
                    "project": None,
                    "category": "company_info",
                    "is_approved": False,
                    "is_verified_fact": False,
                })
                total_embedded += 1
            total_chunks += 1

        # ── Seed NRI info ───────────────────────────────────────────────
        print("[6] Seeding NRI information ...")
        nri_source = KnowledgeSource(
            source_type="website_page",
            source_url="https://abhinavgroup.co.in/nri-corner/",
            source_title="NRI Corner — Property Purchase Guidelines",
        )
        db.add(nri_source)
        await db.flush()

        nri_chunks = chunker.chunk_text(
            NRI_INFO,
            source_id=nri_source.id,
            category="nri_info",
            is_verified_fact=False,
        )
        for chunk in nri_chunks:
            embedding = await ai_provider.embed(chunk.content)
            db_chunk = KnowledgeChunk(
                source_id=nri_source.id,
                category=chunk.category,
                content=chunk.content,
                content_hash=chunk.content_hash,
                language="en",
                embedding=embedding,
                embedding_dim=len(embedding),
                embedding_model=ai_provider.provider_name,
                is_approved=False,
                is_verified_fact=False,
                chunk_index=chunk.chunk_index,
                metadata_={"category": "nri_info"},
            )
            db.add(db_chunk)
            await db.flush()
            if embedding:
                vector_store.add(db_chunk.id, embedding, {
                    "content": chunk.content[:200],
                    "content_hash": chunk.content_hash,
                    "project": None,
                    "category": "nri_info",
                    "is_approved": False,
                    "is_verified_fact": False,
                })
                total_embedded += 1
            total_chunks += 1

        # ── Seed general real estate FAQ ────────────────────────────────
        print("[7] Seeding general real estate FAQ ...")
        faq_source = KnowledgeSource(
            source_type="manual_entry",
            source_title="General Real Estate FAQ",
        )
        db.add(faq_source)
        await db.flush()

        for faq in GENERAL_REALESTATE_FAQ:
            faq_text = f"Q: {faq['question']}\nA: {faq['answer']}"
            faq_chunks = chunker.chunk_text(
                faq_text,
                source_id=faq_source.id,
                category="general_realestate",
                is_verified_fact=True,  # General knowledge — not project-specific
            )
            for chunk in faq_chunks:
                embedding = await ai_provider.embed(chunk.content)
                db_chunk = KnowledgeChunk(
                    source_id=faq_source.id,
                    category=chunk.category,
                    content=chunk.content,
                    content_hash=chunk.content_hash,
                    language="en",
                    embedding=embedding,
                    embedding_dim=len(embedding),
                    embedding_model=ai_provider.provider_name,
                    is_approved=False,
                    is_verified_fact=True,
                    chunk_index=chunk.chunk_index,
                    metadata_={"category": "general_realestate"},
                )
                db.add(db_chunk)
                await db.flush()
                if embedding:
                    vector_store.add(db_chunk.id, embedding, {
                        "content": chunk.content[:200],
                        "content_hash": chunk.content_hash,
                        "project": None,
                        "category": "general_realestate",
                        "is_approved": False,
                        "is_verified_fact": True,
                    })
                    total_embedded += 1
                total_chunks += 1

        await db.commit()

    # Save vector store to disk
    print("\n[8] Saving vector store ...")
    vector_store.save()

    print("\n" + "=" * 60)
    print("  SEEDING COMPLETE")
    print("=" * 60)
    print(f"  Total chunks created  : {total_chunks}")
    print(f"  Chunks embedded       : {total_embedded}")
    print(f"  Vector store total    : {vector_store.count()}")
    print()
    print("  NEXT STEPS:")
    print("  1. Open admin dashboard")
    print("  2. Review all chunks in the Knowledge section")
    print("  3. Approve verified chunks (they are all PENDING now)")
    print("  4. Mark pricing and RERA data as verified after manual check")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
