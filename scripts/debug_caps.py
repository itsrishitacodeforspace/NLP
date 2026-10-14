def main() -> int:
    line = 'RESIDENT ACCOMMODATION SERVICE AGREEMENT ("Agreement")'
    stripped = line.strip()
    print(f"stripped: {stripped!r}")
    print(f"upper:    {stripped.upper()!r}")
    print(f"equal:    {stripped == stripped.upper()}")
    for i, (a, b) in enumerate(zip(stripped, stripped.upper())):
        if a != b:
            print(f"  diff @ {i}: {a!r} vs {b!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())