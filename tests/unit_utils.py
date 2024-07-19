from pathlib import Path


def find_file(filename: str) -> Path:
    return Path(__file__).parent / filename


def load_file(filename: str) -> str:
    return find_file(filename).read_text()
