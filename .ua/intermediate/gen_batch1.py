import json, os
root='C:/Users/Ivermectin/Desktop/NLP/NLP'
struct=json.load(open(root+'/.ua/intermediate/batch-1-structure.json'))
inp=json.load(open(root+'/.ua/intermediate/batch-1-input.json'))
bid=inp['batchImportData']

nodes=[]
edges=[]
node_ids=set()

def add_node(n):
    if n['id'] not in node_ids:
        nodes.append(n); node_ids.add(n['id'])

for r in struct['results']:
    path=r['path']
    lang=r['language']
    fid='file:'+path
    lines=r.get('totalLines',0)
    complexity='simple' if lines<100 else ('moderate' if lines<300 else 'complex')
    add_node({
      'id':fid,
      'type':'file',
      'name':os.path.basename(path),
      'filePath':path,
      'summary':f'{path} ({lines} lines) - {lang} source file in bharatcontract-ai.',
      'tags':[lang, r.get('fileCategory','code')],
      'complexity':complexity
    })
    for fn in r.get('functions',[]) or []:
        nid='function:'+path+':'+fn['name']
        add_node({
          'id':nid,
          'type':'function',
          'name':fn['name'],
          'filePath':path,
          'summary':f"Function {fn['name']} defined in {path} (lines {fn['startLine']}-{fn['endLine']}).",
          'tags':['function',lang],
          'complexity':'moderate'
        })
        edges.append({'source':fid,'target':nid,'type':'contains','direction':'forward','weight':1.0})
    for cls in r.get('classes',[]) or []:
        nid='class:'+path+':'+cls['name']
        add_node({
          'id':nid,
          'type':'class',
          'name':cls['name'],
          'filePath':path,
          'summary':f"Class {cls['name']} defined in {path} (lines {cls['startLine']}-{cls['endLine']}).",
          'tags':['class',lang],
          'complexity':'moderate',
          'methods':cls.get('methods',[]),
          'properties':cls.get('properties',[])
        })
        edges.append({'source':fid,'target':nid,'type':'contains','direction':'forward','weight':1.0})
    for tgt in bid.get(path,[]) or []:
        edges.append({'source':fid,'target':'file:'+tgt,'type':'imports','direction':'forward','weight':0.7})
    fn_names={fn['name']:'function:'+path+':'+fn['name'] for fn in (r.get('functions') or [])}
    for cg in r.get('callGraph',[]) or []:
        caller=cg['caller']; callee=cg['callee']
        if caller in fn_names and callee in fn_names:
            edges.append({'source':fn_names[caller],'target':fn_names[callee],'type':'calls','direction':'forward','weight':0.8})

seen={}
for e in edges:
    key=(e['source'],e['target'],e['type'],e.get('direction','forward'))
    if key not in seen or e.get('weight',0)>seen[key].get('weight',0):
        seen[key]=e
edges=list(seen.values())

out={'nodes':nodes,'edges':edges}
json.dump(out, open(root+'/.ua/intermediate/batch-1.json','w'), indent=2)
print('nodes',len(nodes),'edges',len(edges))