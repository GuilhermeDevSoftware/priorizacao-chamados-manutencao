"""Exporta o commit atual sem dados locais nem pacotes anteriores.

Uso: python scripts/empacotar_entrega.py --saida /caminho/Entrega_IA.zip
O comando inclui somente arquivos já commitados; não lê o banco ou os uploads.
"""
import argparse
from io import BytesIO
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
EXCLUIDOS = {"entrega", "instance", "uploads", "work", "__pycache__", ".pytest_cache", ".git"}


def empacotar(saida):
    origem = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT,
                            capture_output=True, check=True).stdout
    saida = Path(saida).resolve()
    saida.parent.mkdir(parents=True, exist_ok=True)
    quantidade = 0
    with tarfile.open(fileobj=BytesIO(origem)) as pacote, ZipFile(saida, "w", ZIP_DEFLATED) as zipado:
        for membro in pacote.getmembers():
            caminho = PurePosixPath(membro.name)
            if not membro.isfile() or set(caminho.parts) & EXCLUIDOS:
                continue
            if caminho.name == ".env" or caminho.name.startswith(".env.") and caminho.name != ".env.example":
                continue
            if caminho.suffix in (".db", ".sqlite", ".sqlite3"):
                continue
            entrada = ZipInfo("priorizacao-chamados-manutencao/" + membro.name)
            entrada.compress_type = ZIP_DEFLATED
            zipado.writestr(entrada, pacote.extractfile(membro).read())
            quantidade += 1
    with ZipFile(saida) as zipado:
        if zipado.testzip() is not None:
            raise RuntimeError("Falha de integridade no ZIP.")
    print(f"Entrega criada: {saida} ({quantidade} arquivos, somente o commit atual).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", required=True, help="Caminho de destino do arquivo ZIP.")
    empacotar(parser.parse_args().saida)
