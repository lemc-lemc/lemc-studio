import shutil
import sys
from importlib.metadata import distribution
from pathlib import Path


def collect(target):
    target.mkdir(parents=True, exist_ok=True)
    for candidate in (Path(sys.base_prefix) / 'LICENSE.txt', Path(sys.base_prefix) / 'LICENSE'):
        if candidate.is_file():
            shutil.copyfile(candidate, target / 'Python-LICENSE.txt')
            break
    for name in ('Pillow', 'PyInstaller'):
        package = distribution(name)
        for file in package.files or ():
            if file.name.lower().startswith(('license', 'copying', 'notice')):
                origin = Path(package.locate_file(file))
                if origin.is_file():
                    copy = target / name / Path(*file.parts[1:])
                    copy.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(origin, copy)


if __name__ == '__main__':
    collect(Path(sys.argv[1]))
