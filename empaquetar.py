"""Crea un ZIP de fuentes sin base poblada, secretos, entorno ni uploads."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent


def empaquetar():
    output = ROOT.parent / 'output' / 'DevArcade_Flask.zip'
    output.parent.mkdir(exist_ok=True)
    sources = [p for p in ROOT.iterdir() if p.is_file() and
               (p.suffix in ('.py', '.md', '.bat') or p.name in
                ('requirements.txt', '.env.example', '.gitignore'))]
    sources += [ROOT / 'db/schema.sql', ROOT / 'uploads/.gitkeep']
    sources += [p for p in (ROOT / 'prototipo').rglob('*') if p.is_file()]
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(sources):
            archive.write(path, Path('devarcade') / path.relative_to(ROOT))
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        assert all(not n.endswith(('.db', '.db-wal', '.db-shm', '.secret_key', '/.env')) for n in archive.namelist())
        print(f'ZIP verificado: {output} ({len(archive.namelist())} archivos)')


if __name__ == '__main__':
    empaquetar()
