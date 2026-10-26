import json, os
base = r"C:\Users\Ivermectin\Desktop\NLP\NLP"
files = [
 "data/datasets/maud/data/contracts/contract_89.txt",
 "data/datasets/maud/data/contracts/contract_9.txt",
 "data/datasets/maud/data/contracts/contract_90.txt",
 "data/datasets/maud/data/contracts/contract_91.txt",
 "data/datasets/maud/data/contracts/contract_92.txt",
 "data/datasets/maud/data/contracts/contract_93.txt",
 "data/datasets/maud/data/contracts/contract_94.txt",
 "data/datasets/maud/data/contracts/contract_95.txt",
 "data/datasets/maud/data/contracts/contract_96.txt",
 "data/datasets/maud/data/contracts/contract_97.txt",
 "data/datasets/maud/data/contracts/contract_98.txt",
 "data/datasets/maud/data/contracts/contract_99.txt",
]
prefix = "MAUD dataset source contract text: "
nodes = []
for f in files:
    path = os.path.join(base, f)
    first = ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if s:
                first = s
                break
    snippet = first[:200]
    summary = prefix + snippet
    name = os.path.basename(f)
    nodes.append({
        "id": "document:" + f,
        "type": "document",
        "name": name,
        "filePath": f,
        "summary": summary,
        "tags": ["documentation","legal-contract","maud-dataset","merger-agreement"],
        "complexity": "complex"
    })
out = {"nodes": nodes, "edges": []}
json.dump(out, open(os.path.join(base, ".ua", "intermediate", "batch-19.json"), "w"), indent=2)
print("nodes", len(nodes))