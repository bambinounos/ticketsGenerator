from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent.parent / 'VERSION'

def get_version():
    try:
        return VERSION_FILE.read_text().strip()
    except FileNotFoundError:
        return '0.0.0'

__version__ = get_version()
