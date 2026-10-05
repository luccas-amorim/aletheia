from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from aletheia.http import Requisicao, Resposta
from tests.apoio import BASE, FEED

FIXTURES = Path(__file__).parent / "fixtures"


class Rede:
    """Transporte falso: responde por URL exata (sem query) a partir de fixtures."""

    def __init__(self) -> None:
        self.rotas: dict[str, list[Resposta]] = {}
        self.pedidos: list[Requisicao] = []

    def responder(
        self,
        url: str,
        corpo: bytes | str | Path,
        status: int = 200,
        cabecalhos: dict[str, str] | None = None,
    ) -> None:
        if isinstance(corpo, Path):
            corpo = corpo.read_bytes()
        elif isinstance(corpo, str):
            corpo = corpo.encode("utf-8")
        self.rotas.setdefault(url, []).append(Resposta(status, url, corpo, cabecalhos or {}))

    def __call__(self, req: Requisicao, tempo_limite: float) -> Resposta:
        self.pedidos.append(req)
        url = req.url.split("?")[0]
        if url not in self.rotas:
            return Resposta(404, req.url, b"nao encontrado", {})
        fila = self.rotas[url]
        return fila.pop(0) if len(fila) > 1 else fila[0]

    def urls(self) -> list[str]:
        return [p.url for p in self.pedidos]


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    """O limite por minuto é testado em test_http com relógio falso; aqui, nada dorme."""
    monkeypatch.setattr("aletheia.http.time.sleep", lambda segundos: None)


@pytest.fixture
def rede() -> Rede:
    return Rede()


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def cfg(tmp_path, fixtures):
    """Configuração mínima: um feed RSS e o léxico de amostra do Carandiru."""
    shutil.copy(fixtures / "lexico-carandiru.json", tmp_path / "lexico.json")
    dados = {
        "lexico": "lexico.json",
        "diretorio": "dados",
        "desde": "2026-09-01",
        "fontes": [{"tipo": "rss", "id": "rss:jornal", "url": FEED, "minimo_caracteres": 200}],
    }
    caminho = tmp_path / "config.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


@pytest.fixture
def rede_jornal(rede, fixtures):
    rede.responder(FEED, fixtures / "rss" / "feed.xml")
    rede.responder(f"{BASE}/carandiru-34-anos", fixtures / "rss" / "materia-carandiru.html")
    rede.responder(f"{BASE}/drenagem", fixtures / "rss" / "materia-outra.html")
    rede.responder(f"{BASE}/sumiu", fixtures / "rss" / "erro-200.html")
    return rede
