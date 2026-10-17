"""Validación compartida de las entradas de la API."""
import re
from datetime import datetime
from PIL import Image, UnidentifiedImageError


class ValidationError(ValueError):
    pass


def v_str(valor, field="campo", min_len=1, max_len=500, allow_empty=False):
    if valor is None and allow_empty:
        return ""
    if not isinstance(valor, str):
        raise ValidationError(f"{field}: debe ser texto")
    s = valor.strip()
    if allow_empty and not s:
        return ""
    if not min_len <= len(s) <= max_len:
        raise ValidationError(f"{field}: debe tener entre {min_len} y {max_len} caracteres")
    return s


def v_nombre_jugador(valor):
    s = v_str(valor, "nombre", 3, 20)
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,20}", s):
        raise ValidationError("nombre: usá letras, números, puntos o guiones (3 a 20)")
    return s


def v_email(valor):
    s = v_str(valor, "email", 5, 254).lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", s) or any(c in s for c in "\r\n"):
        raise ValidationError("email: formato inválido")
    return s


def v_slug(valor, field="slug"):
    s = re.sub(r"\s+", "-", v_str(valor, field, 2, 80).lower())
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", s):
        raise ValidationError(f"{field}: usá minúsculas, números y guiones")
    return s


def v_int(valor, field="campo", min_val=0, max_val=99999999):
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise ValidationError(f"{field}: debe ser un entero")
    if isinstance(valor, str) and not re.fullmatch(r"-?\d+", valor.strip()):
        raise ValidationError(f"{field}: debe ser un entero")
    try:
        n = int(valor)
    except (ValueError, TypeError):
        raise ValidationError(f"{field}: debe ser un entero")
    if not min_val <= n <= max_val:
        raise ValidationError(f"{field}: debe estar entre {min_val} y {max_val}")
    return n


def v_bool_int(valor, default=0):
    if valor is None:
        return default
    if isinstance(valor, (int, bool)) and valor in (0, 1):
        return int(valor)
    if isinstance(valor, str):
        if valor.lower() in ("1", "true", "on", "si", "sí"):
            return 1
        if valor.lower() in ("0", "false", "off", "no"):
            return 0
    raise ValidationError("estado: debe ser verdadero o falso")


def v_one_of(valor, permitidos, field="campo"):
    if valor not in permitidos:
        raise ValidationError(f"{field}: valor inválido")
    return valor


def v_date(valor, field="fecha", allow_none=True):
    if not valor and allow_none:
        return None
    if not isinstance(valor, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        raise ValidationError(f"{field}: usá YYYY-MM-DD")
    try:
        datetime.strptime(valor, "%Y-%m-%d")
    except ValueError:
        raise ValidationError(f"{field}: fecha inexistente")
    return valor


def v_imagen_archivo(file_storage, max_bytes=2 * 1024 * 1024):
    if not file_storage or not file_storage.filename:
        raise ValidationError("imagen: seleccioná un archivo")
    ext = "." + file_storage.filename.rsplit(".", 1)[-1].lower()
    formatos = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP", ".gif": "GIF"}
    if ext not in formatos:
        raise ValidationError("imagen: usar PNG, JPG, WEBP o GIF")
    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if not 0 < size <= max_bytes:
        raise ValidationError("imagen: máximo 2 MB y archivo no vacío")
    try:
        with Image.open(file_storage.stream) as image:
            if image.format != formatos[ext] or image.width * image.height > 20_000_000:
                raise ValidationError("imagen: formato o dimensiones inválidas")
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, ValueError):
        raise ValidationError("imagen: contenido inválido o archivo dañado")
    finally:
        file_storage.stream.seek(0)
    return ext
