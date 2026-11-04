"""Quick test for RAG components — chunker and vector store."""
import sys, pathlib, tempfile
sys.path.insert(0, '.')

# ── Chunker ──
from app.rag.chunker import KnowledgeChunker
c = KnowledgeChunker()
chunks = c.chunk_text(
    'Samsara is a luxury 3 BHK residential project by Abhinav Group located at Mukund Nagar, Pune. ' * 20,
    source_id='test-src',
    project_name='Samsara',
    category='project_overview',
)
assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"
assert len(chunks[0].content) > 100, "Chunk too small"
print(f"PASS  chunker: {len(chunks)} chunks, first={len(chunks[0].content)}ch")

# Overlap check
if len(chunks) > 1:
    overlap_tail = chunks[0].content[-30:]
    has_overlap = overlap_tail in chunks[1].content
    print(f"PASS  overlap: {has_overlap}")

# Structured data chunker
struct_chunks = c.chunk_structured_data({
    'project_name': 'Samsara',
    'description': 'Luxury 3BHK residences in Mukund Nagar, Pune',
    'location': 'Mukund Nagar', 'city': 'Pune', 'state': 'Maharashtra',
    'configurations': [{'type': '3 BHK', 'carpet_area_sqft': 1200}],
    'rera_number': 'P52100079797',
    'approval_status': 'PENDING',
    'price_verified': False,
}, source_id='s1', project_name='Samsara')
assert len(struct_chunks) >= 3, f"Expected >=3 struct chunks, got {len(struct_chunks)}"
print(f"PASS  struct_chunks: {len(struct_chunks)}")
for ch in struct_chunks:
    print(f"      [{ch.category}] {len(ch.content)}ch verified={ch.is_verified_fact}")

# Content hash
assert chunks[0].content_hash, "No content hash"
print(f"PASS  content_hash: {chunks[0].content_hash[:16]}...")

# ── Vector Store ──
import numpy as np
from app.rag.vector_store import FAISSVectorStore
tmp = pathlib.Path(tempfile.mkdtemp())
store = FAISSVectorStore(dim=4, index_dir=tmp)

store.add('c1', [0.9, 0.1, 0.1, 0.1], {'project':'Samsara','category':'overview','is_approved':True,'content':'Samsara 3BHK','content_hash':'h1','is_verified_fact':True})
store.add('c2', [0.1, 0.9, 0.1, 0.1], {'project':'Pebbles Greenfield','category':'overview','is_approved':True,'content':'Pebbles 2BHK','content_hash':'h2','is_verified_fact':False})
store.add('c3', [0.8, 0.2, 0.1, 0.1], {'project':'Samsara','category':'pricing','is_approved':True,'content':'Samsara pricing','content_hash':'h3','is_verified_fact':False})
assert store.count() == 3, f"Expected 3, got {store.count()}"
print(f"PASS  vector_store count: {store.count()}")

results = store.search([0.9, 0.1, 0.1, 0.1], top_k=3, min_score=0.0)
assert len(results) > 0, "No results"
assert results[0].chunk_id == 'c1', f"Top result should be c1, got {results[0].chunk_id}"
print(f"PASS  search top result: {results[0].chunk_id} score={results[0].score:.3f}")

# Project filter
filtered = store.search([0.9, 0.1, 0.1, 0.1], top_k=3, project_filter='Samsara', min_score=0.0)
assert all(r.metadata['project'] == 'Samsara' for r in filtered), "Filter failed"
print(f"PASS  project_filter: {len(filtered)} Samsara results")

# Remove
removed = store.remove('c2')
assert removed, "Remove failed"
assert store.count() == 2, f"Expected 2 after remove, got {store.count()}"
print(f"PASS  remove: count now {store.count()}")

# Save and reload
store.save()
store2 = FAISSVectorStore(dim=4, index_dir=tmp)
assert store2.count() == 2, f"Expected 2 after reload, got {store2.count()}"
print(f"PASS  persist+reload: {store2.count()} chunks")

print()
print("=" * 40)
print("ALL RAG COMPONENT TESTS PASSED")
print("=" * 40)
