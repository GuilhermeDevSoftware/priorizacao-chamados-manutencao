"""Prepara docs/ para GitHub Pages sem depender de caminhos absolutos."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def preparar():
    destino = ROOT / "docs"
    destino.mkdir(exist_ok=True)
    for nome in ("index.html", "styles.css", "app.js", "engine.js", "config.json"):
        origem = ROOT / "frontend" / nome
        if not origem.is_file():
            raise FileNotFoundError(f"Arquivo obrigatório ausente: {origem}")
        shutil.copy2(origem, destino / nome)
    (destino / "modelo").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "modelo" / "arvore.json", destino / "modelo" / "arvore.json")
    (destino / ".nojekyll").touch()
    print("Demonstração preparada em docs/. Publicação: main /docs no GitHub Pages.")


if __name__ == "__main__":
    preparar()
