"""Lista curada: URLs que uma pessoa reuniu à mão, num CSV versionado.

Serve ao que nenhum robô alcança por política ou por falta de API: a Hemeroteca Digital,
acervos pagos cuja página pública existe, documentos do processo achados em consulta
manual. O CSV tem cabeçalho `url,titulo,publicado_em` (os dois últimos opcionais). A
listagem devolve tudo; o estado da fonte impede a releitura do que já foi visto.

Configuração:
    {"tipo": "lista", "id": "lista:hemeroteca", "arquivo": "listas/hemeroteca.csv",
     "limite_por_minuto": 10, "estrato": "imprensa-historica"}

`arquivo` é relativo ao `config.json`.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from aletheia.contrato import Documento, Referencia
from aletheia.fontes.rss import documento_html, pagina_integra
from aletheia.http import Cliente, Transporte, transporte_urllib
from aletheia.url import normalizar


class Lista:
    respeita_robots = True

    def __init__(
        self,
        id: str,
        arquivo: Path,
        cliente: Cliente,
        limite_por_minuto: int = 10,
        minimo_caracteres: int = 400,
    ) -> None:
        self.id = id
        self.arquivo = Path(arquivo)
        self.cliente = cliente
        self.limite_por_minuto = limite_por_minuto
        self.minimo_caracteres = minimo_caracteres

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> Lista:
        limite = int(cfg.get("limite_por_minuto", 10))
        base = Path(cfg.get("_diretorio_config", "."))
        cliente = Cliente(limite, respeita_robots=True, transporte=transporte)
        return cls(
            cfg["id"],
            base / cfg["arquivo"],
            cliente,
            limite,
            int(cfg.get("minimo_caracteres", 400)),
        )

    def listar(self, desde: date) -> Iterator[Referencia]:
        with self.arquivo.open(encoding="utf-8", newline="") as f:
            for linha in csv.DictReader(f):
                url = (linha.get("url") or "").strip()
                if not url:
                    continue
                publicado = (linha.get("publicado_em") or "").strip()
                try:
                    data = date.fromisoformat(publicado) if publicado else None
                except ValueError:
                    data = None
                yield Referencia(
                    fonte=self.id,
                    id_na_fonte=normalizar(url),
                    url=url,
                    titulo=(linha.get("titulo") or "").strip() or None,
                    publicado_em=data,
                    dados={"via": self.arquivo.name},
                )

    def baixar(self, ref: Referencia) -> Documento:
        return documento_html(ref, self.cliente.requisitar(ref.url), ref.titulo)

    def sentinela(self, doc: Documento) -> bool:
        return pagina_integra(doc, self.minimo_caracteres)
