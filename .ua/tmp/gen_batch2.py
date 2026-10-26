import json, os, math

root = r"C:\Users\Ivermectin\Desktop\NLP\NLP"
ua = os.path.join(root, ".ua")
extract = json.load(open(os.path.join(ua, "tmp", "ua-file-extract-results-2.json")))
batches = json.load(open(os.path.join(ua, "intermediate", "batches.json")))
batch = [bb for bb in batches["batches"] if bb["batchIndex"]==2][0]
bid = batch["batchImportData"]

file_meta = {
 "nlp/clause_classification/classifier.py": ("Clause classifier — rule-based keyword matcher enriched by CUAD keyword bank, with TF-IDF ML fallback; exposes classify_clause and classify_clauses.", ["classification","nlp","clause-typing","rule-based","tfidf"], "complex"),
 "nlp/clause_classification/classifier_ml.py": ("Lazy DeBERTa-v3 clause classifier wrapper; classify_with_deberta returns ClassificationResult or None.", ["classification","ml","deberta","optional-deps"], "moderate"),
 "nlp/clause_classification/tfidf_model.py": ("Runtime loader for bundled TF-IDF clause classifier (7z extraction + joblib) with TrainedClassifier.predict_one/top1.", ["tfidf","model-loading","classification"], "moderate"),
 "nlp/datasets/__init__.py": ("Package barrel re-exporting CUAD and MAUD dataset loaders.", ["barrel","package","dataset"], "simple"),
 "nlp/datasets/cuad.py": ("CUAD dataset loader: iter_examples, build_corpus, category_counts, collect_keyword_bank.", ["dataset","cuad","corpus","provenance"], "moderate"),
 "nlp/datasets/manifest.py": ("Manifest generation and verification for dataset provenance.", ["provenance","manifest","dataset"], "moderate"),
 "nlp/datasets/maud.py": ("MAUD dataset loader: iter_examples, build_corpus.", ["dataset","maud","corpus"], "moderate"),
 "nlp/datasets/splits.py": ("Source resolution, split assignment and provenance validation (ProvenanceError, SourceSpec).", ["splits","provenance","validation","dataset"], "moderate"),
 "nlp/datasets/unified.py": ("Unified TrainingExample schema and JSONL read/write helpers.", ["dataset","schema","io"], "simple"),
 "nlp/provenance.py": ("Provenance registry: sha256 caching, artifact status, warnings, record_loaded_model.", ["provenance","registry","caching"], "moderate"),
 "nlp/taxonomy.py": ("CUAD/MAUD label mapping to internal taxonomy (map_cuad_label, map_maud_label).", ["taxonomy","labels","mapping"], "moderate"),
 "scripts/build_training_data.py": ("Builds unified training corpus from CUAD/MAUD and writes clause classifier CSV.", ["training-data","build","dataset","cli"], "moderate"),
 "scripts/eval_classifier.py": ("Evaluates classifier precision/recall/F1 on held-out CSV.", ["evaluation","classifier","metrics"], "moderate"),
 "scripts/train_tfidf_classifier.py": ("Trains TF-IDF classifier from corpus and saves model.", ["training","tfidf","cli"], "moderate"),
 "scripts/verify_provenance.py": ("Verifies artifact lineage and manifests (check_csv/jsonl/row_lineage).", ["provenance","verification","cli"], "moderate"),
 "tests/test_classifier_accuracy.py": ("Tests classifier accuracy on CUAD gold data (top-1/top-3).", ["test","classifier","accuracy"], "moderate"),
 "tests/test_no_leakage.py": ("Provenance/no-leakage tests for training corpus and manifests.", ["test","provenance","no-leakage"], "complex"),
}

def file_type(cat, path):
    return "file"

nodes = []
edges = []

by_path = {r["path"]: r for r in extract["results"]}

for f in batch["files"]:
    p = f["path"]
    cat = f["fileCategory"]
    ntype = file_type(cat, p)
    summary, tags, comp = file_meta.get(p, (f"Source file {p}.", ["code"], "simple"))
    node = {
        "id": f"{ntype}:{p}",
        "type": ntype,
        "name": os.path.basename(p),
        "filePath": p,
        "summary": summary,
        "tags": tags,
        "complexity": comp,
    }
    nodes.append(node)

for r in extract["results"]:
    p = r["path"]
    exported_names = {e["name"] for e in r.get("exports", [])}
    for c in r.get("classes", []):
        name = c["name"]
        methods = c.get("methods", [])
        lines = c.get("endLine",0)-c.get("startLine",0)+1
        if not (len(methods) >= 2 or lines >= 20 or name in exported_names):
            continue
        node = {
            "id": f"class:{p}:{name}",
            "type": "class",
            "name": name,
            "filePath": p,
            "lineRange": [c["startLine"], c["endLine"]],
            "summary": f"Class {name} in {os.path.basename(p)}.",
            "tags": ["class", "type-definition"],
            "complexity": "moderate" if lines > 50 else "simple",
        }
        nodes.append(node)
        edges.append({"source": f"file:{p}", "target": node["id"], "type": "contains", "direction": "forward", "weight": 1.0})
        if name in exported_names:
            edges.append({"source": f"file:{p}", "target": node["id"], "type": "exports", "direction": "forward", "weight": 0.8})
    for fn in r.get("functions", []):
        name = fn["name"]
        start = fn["startLine"]; end = fn["endLine"]
        lines = end - start + 1
        exported = name in exported_names
        if not (lines >= 10 or exported):
            continue
        node = {
            "id": f"function:{p}:{name}",
            "type": "function",
            "name": name,
            "filePath": p,
            "lineRange": [start, end],
            "summary": f"Function {name} in {os.path.basename(p)}.",
            "tags": ["function"],
            "complexity": "moderate" if lines > 30 else "simple",
        }
        nodes.append(node)
        edges.append({"source": f"file:{p}", "target": node["id"], "type": "contains", "direction": "forward", "weight": 1.0})
        if exported:
            edges.append({"source": f"file:{p}", "target": node["id"], "type": "exports", "direction": "forward", "weight": 0.8})

for p, targets in bid.items():
    for t in targets:
        edges.append({"source": f"file:{p}", "target": f"file:{t}", "type": "imports", "direction": "forward", "weight": 0.7})

for p, targets in bid.items():
    if p.startswith("tests/"):
        for t in targets:
            edges.append({"source": f"file:{t}", "target": f"file:{p}", "type": "tested_by", "direction": "forward", "weight": 0.5})

seen = set()
uniq_nodes = []
for n in nodes:
    if n["id"] in seen:
        continue
    seen.add(n["id"])
    uniq_nodes.append(n)

seen_e = set()
uniq_edges = []
for e in edges:
    key = (e["source"], e["target"], e["type"])
    if key in seen_e:
        continue
    seen_e.add(key)
    if e["source"] == e["target"]:
        continue
    uniq_edges.append(e)

out_dir = os.path.join(ua, "intermediate")

if len(uniq_nodes) <= 60 and len(uniq_edges) <= 120:
    out_path = os.path.join(out_dir, "batch-2.json")
    json.dump({"nodes": uniq_nodes, "edges": uniq_edges}, open(out_path, "w"), indent=2)
    print("wrote single", out_path, len(uniq_nodes), len(uniq_edges))
else:
    files_sorted = sorted({n["filePath"] for n in uniq_nodes if "filePath" in n})
    parts = 4
    chunk_size = math.ceil(len(files_sorted)/parts)
    file_part = {}
    for i, fp in enumerate(files_sorted):
        file_part[fp] = min(i // chunk_size + 1, parts)
    for k in range(1, parts+1):
        part_files = {fp for fp,pp in file_part.items() if pp==k}
        part_nodes = [n for n in uniq_nodes if n.get("filePath") in part_files]
        part_node_ids = {n["id"] for n in part_nodes}
        part_edges = [e for e in uniq_edges if e["source"] in part_node_ids]
        out_path = os.path.join(out_dir, f"batch-2-part-{k}.json")
        json.dump({"nodes": part_nodes, "edges": part_edges}, open(out_path, "w"), indent=2)
        print(f"wrote part {k}", out_path, len(part_nodes), len(part_edges))

print("TOTAL nodes", len(uniq_nodes), "edges", len(uniq_edges))
