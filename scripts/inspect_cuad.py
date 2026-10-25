"""Inspect the CUAD categories."""
import json
import re
from pathlib import Path

DATA = Path("data/datasets/cuad/CUADv1.json")


def main() -> int:
    with DATA.open(encoding="utf-8") as fh:
        data = json.load(fh)

    seen: set[str] = set()
    order: list[str] = []
    for doc in data["data"]:
        for para in doc["paragraphs"]:
            for qa in para["qas"]:
                q = qa["question"]
                if q in seen:
                    continue
                seen.add(q)
                m = re.search(r'related to "([^"]+)"', q)
                if m:
                    order.append(m.group(1))

    print(f"Unique categories: {len(order)}")
    for c in order:
        print(f"  - {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
