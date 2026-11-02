from app.services.segmenter import _looks_like_heading_line, detect_section_number


def main() -> int:
    line = 'RESIDENT ACCOMMODATION SERVICE AGREEMENT ("Agreement")'
    print(f"line: {line!r}")
    print(f"length: {len(line)}")
    print(f"detect_section: {detect_section_number(line)}")
    print(f"looks like heading: {_looks_like_heading_line(line)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
