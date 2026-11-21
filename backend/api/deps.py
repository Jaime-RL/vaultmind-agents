from fastapi import Request

from app.services import Services


def get_services(request: Request) -> Services:
    """Los servicios viven en app.state; los endpoints los piden con Depends(get_services)."""
    return request.app.state.services
