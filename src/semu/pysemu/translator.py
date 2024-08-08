from pathlib import Path

import click


@click.command()
@click.option('--input', help='Input file', required=True, type=Path)
@click.option('--output', help='Output file', required=True, type=Path)
def translate(input: Path, output: Path):
    print(f'Translating {input} to {output}')
    pass


if __name__ == '__main__':
    translate()
