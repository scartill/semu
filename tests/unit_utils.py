from pathlib import Path


def load_sasm(filename: str) -> str:
    return (Path(__file__).parent / filename).read_text()
