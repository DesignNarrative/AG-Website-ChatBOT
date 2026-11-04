import json
with open('data/website-extraction/projects.json', encoding='utf-8') as f:
    projects = json.load(f)
for p in projects:
    print(f"Project: {p['project_name']}")
    print(f"  Sources: {len(p['source_urls'])}")
    print(f"  Images:  {len(p['images'])}")
    print(f"  RERA:    {p['rera_numbers']}")
    print(f"  Phones:  {p['phone_numbers'][:5]}")
    print(f"  Snippets: {len(p['text_snippets'])}")
    if p['text_snippets']:
        print(f"  Preview: {p['text_snippets'][0][:200]}")
    print()
