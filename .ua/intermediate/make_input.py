import json, os
p = r"C:\Users\Ivermectin\Desktop\NLP\NLP\.ua\intermediate\batches.json"
data = json.load(open(p))
batch = None
for b in data["batches"]:
    if b["batchIndex"] == 19:
        batch = b
        break
inp = {
  "projectRoot": r"C:\Users\Ivermectin\Desktop\NLP\NLP",
  "batchFiles": batch["files"],
  "batchImportData": batch["batchImportData"]
}
out = r"C:\Users\Ivermectin\Desktop\NLP\NLP\.ua\intermediate\batch19-input.json"
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(inp, open(out,"w"), indent=2)
print("files:", len(batch["files"]))