import json
data = {
  "projectRoot": r"C:\Users\Ivermectin\Desktop\NLP\NLP",
  "batchFiles": [
    {"path": "docker/Dockerfile", "language": "dockerfile", "sizeLines": 24, "fileCategory": "infra"},
    {"path": "docker/docker-compose.yml", "language": "yaml", "sizeLines": 112, "fileCategory": "infra"}
  ],
  "batchImportData": {
    "docker/Dockerfile": [],
    "docker/docker-compose.yml": []
  }
}
with open(r"C:\Users\Ivermectin\Desktop\NLP\NLP\.ua\tmp\ua-file-analyzer-input-7.json","w") as f:
    json.dump(data, f, indent=2)
print("ok")
