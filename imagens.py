"""Validação e normalização de uma foto, sem confiar no nome enviado."""
from io import BytesIO
from pathlib import Path
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_FOTO_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 25_000_000
FORMATOS = {"JPEG": {".jpg", ".jpeg"}, "PNG": {".png"}, "WEBP": {".webp"}}


class FotoInvalida(ValueError):
    pass


class FotoGrande(FotoInvalida):
    pass


def normalizar_foto(arquivo):
    """Devolve JPEG em memória ou None. Nada é gravado nesta etapa."""
    if arquivo is None:
        return None
    if not arquivo.filename:
        if not arquivo.read(1):
            return None
        raise FotoInvalida("Selecione uma foto JPEG, PNG ou WebP com nome válido.")
    conteudo = arquivo.read(MAX_FOTO_BYTES + 1)
    if len(conteudo) > MAX_FOTO_BYTES:
        raise FotoGrande("A foto deve ter no máximo 5 MiB.")
    if not conteudo:
        raise FotoInvalida("O arquivo de foto está vazio.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(conteudo)) as imagem:
                if imagem.format not in FORMATOS or Path(arquivo.filename).suffix.lower() not in FORMATOS[imagem.format]:
                    raise FotoInvalida("Use JPEG, PNG ou WebP com extensão correspondente ao conteúdo.")
                if imagem.width * imagem.height > MAX_PIXELS:
                    raise FotoGrande("A foto deve ter no máximo 25 megapixels.")
                imagem.verify()
            with Image.open(BytesIO(conteudo)) as original:
                foto = ImageOps.exif_transpose(original)
                foto.thumbnail((2048, 2048))
                if foto.mode in ("RGBA", "LA") or "transparency" in foto.info:
                    rgba = foto.convert("RGBA")
                    limpa = Image.new("RGB", rgba.size, "white")
                    limpa.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    limpa = foto.convert("RGB")
                # Uma imagem nova remove EXIF, localização, ICC e demais metadados.
                pixels = Image.new("RGB", limpa.size)
                pixels.paste(limpa)
                saida = BytesIO()
                pixels.save(saida, format="JPEG", quality=85, optimize=True)
                return saida.getvalue()
    except FotoInvalida:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise FotoGrande("A foto deve ter no máximo 25 megapixels.") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise FotoInvalida("O arquivo não contém uma imagem válida e suportada.") from exc
