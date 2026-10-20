from pathlib import Path
import json,re
# Requires the repository's installed @iconify/json dependency.
base=Path(__file__).resolve().parents[3]
data=base/'internal/tailwind-config/node_modules/@iconify/json/json'
groups={}
for root in [base/'apps/web-ele/src',base/'packages']:
 for p in root.rglob('*'):
  if p.suffix not in {'.ts','.vue'} or '.test.' in p.name:continue
  for prefix,name in re.findall(r'''['"`]([a-z][a-z0-9-]*):([a-z0-9][a-z0-9-]*)['"`]''',p.read_text()):
   if (data/(prefix+'.json')).exists():groups.setdefault(prefix,set()).add(name)
sets=[]
for prefix,names in sorted(groups.items()):
 original=json.loads((data/(prefix+'.json')).read_text());icons={};aliases={}
 def include(name):
  if name in original['icons']:icons[name]=original['icons'][name]
  elif name in original.get('aliases',{}):
   aliases[name]=original['aliases'][name];include(aliases[name]['parent'])
 for name in sorted(names):include(name)
 if icons:
  item={k:v for k,v in original.items() if k in {'prefix','width','height','info'}}
  item['icons']=icons
  if aliases:item['aliases']=aliases
  sets.append(item)
p=base/'apps/web-ele/src/offline-icons.json';p.write_text(json.dumps(sets,ensure_ascii=False,indent=2)+'\n')
print('offline collections:',len(sets),'icons:',sum(len(s['icons']) for s in sets),'bytes:',p.stat().st_size)
