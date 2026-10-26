import json
root = r"C:\Users\Ivermectin\Desktop\NLP\NLP"
scan = json.load(open(r"C:\Users\Ivermectin\Desktop\NLP\NLP\.ua\tmp\ua-scan-files.json", encoding="utf-8-sig"))
imp = json.load(open(r"C:\Users\Ivermectin\Desktop\NLP\NLP\.ua\tmp\ua-import-map-output.json", encoding="utf-8-sig"))

name = "bharatcontract-ai"
raw_description = "Legal Contract Intelligence — Indian-context risk-aware clause extraction & obligation tracker"
readme_head = ""  # not needed for description basis since raw_description non-empty
description = raw_description
if scan["totalFiles"] > 100:
    description = description + " Note: this project has over 100 source files; consider scoping analysis to a subdirectory for faster results."

languages = sorted(scan["stats"]["byLanguage"].keys())

frameworks = ["Alembic", "Celery", "Docker", "Docker Compose", "FastAPI", "Pydantic", "Pytest", "SQLAlchemy", "Streamlit", "Uvicorn"]

result = {
    "name": name,
    "description": description,
    "languages": languages,
    "frameworks": frameworks,
    "files": scan["files"],
    "totalFiles": scan["totalFiles"],
    "filteredByIgnore": scan["filteredByIgnore"],
    "estimatedComplexity": scan["estimatedComplexity"],
    "importMap": imp["importMap"],
}

out_path = r"C:\Users\Ivermectin\Desktop\NLP\NLP\.ua\intermediate\scan-result.json"
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=2)
print("written", len(result["files"]), result["totalFiles"])
