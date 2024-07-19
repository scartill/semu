from pathlib import Path


def find_source(filename: str) -> Path:
    return Path(__file__).parent / filename


def load_sasm(filename: str) -> str:
    return find_source(filename).read_text()
