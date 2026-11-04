"""Quick debug test."""
import sys
sys.path.insert(0, '.')
from app.rag.chunker import KnowledgeChunker, _char_budget

c = KnowledgeChunker()
text = 'Samsara is a luxury 3 BHK residential project by Abhinav Group located at Mukund Nagar, Pune. ' * 20
print(f'text length: {len(text)}')
print(f'chunk char budget (en): {_char_budget(400, "en")}')

paras = c._split_paragraphs(text)
print(f'paragraphs: {len(paras)}')
for i, p in enumerate(paras[:3]):
    print(f'  para[{i}]: {len(p)} chars')

chunks = c.chunk_text(text, source_id='s', project_name='Samsara', category='project_overview')
print(f'chunks: {len(chunks)}')
for i, ch in enumerate(chunks):
    print(f'  chunk[{i}]: {len(ch.content)} chars')
