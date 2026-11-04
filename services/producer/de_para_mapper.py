"""Mapeamento De-Para da API pública (Users, Albums, Photos) para o domínio de Acordos Jurídicos."""

from typing import Any, Dict, List, Optional


def format_address(address: Optional[Dict[str, Any]]) -> str:
    """Formata o endereço seguindo o padrão: '{street}, {suite} - {city} CEP {zipcode}'."""
    if not address or not isinstance(address, dict):
        return "Endereço não informado"
    street = str(address.get("street", "")).strip()
    suite = str(address.get("suite", "")).strip()
    city = str(address.get("city", "")).strip()
    zipcode = str(address.get("zipcode", "")).strip()
    return f"{street}, {suite} - {city} CEP {zipcode}"


def map_photo_to_documento(photo: Dict[str, Any]) -> Dict[str, Any]:
    """Realiza o De-Para de um registro de foto (/photos) para documento jurídico."""
    return {
        "id": int(photo["id"]),
        "titulo": str(photo.get("title", "")).strip(),
        "url": str(photo.get("url", "")).strip(),
        "thumbnailUrl": str(photo.get("thumbnailUrl", "")).strip(),
    }


def map_album_to_acordo(album: Dict[str, Any], photos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Realiza o De-Para de um álbum (/albums) e suas fotos para acordo jurídico e documentos."""
    return {
        "id": int(album["id"]),
        "titulo": str(album.get("title", "")).strip(),
        "documentos": [map_photo_to_documento(p) for p in photos],
    }


def map_user_to_autor_payload(
    user: Dict[str, Any],
    albums_with_photos: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Realiza o De-Para completo do usuário (/users) para o contrato canônico de Autor e Acordos."""
    company = user.get("company") if isinstance(user.get("company"), dict) else {}
    return {
        "autor": {
            "id": int(user["id"]),
            "nome": str(user.get("name", "")).strip(),
            "email": str(user.get("email", "")).strip(),
            "telefone": str(user.get("phone", "")).strip(),
            "endereco": format_address(user.get("address")),
            "empresa": {
                "nome": str(company.get("name", "")).strip(),
                "segmento": str(company.get("bs", "")).strip(),
            },
        },
        "acordos": albums_with_photos,
    }
