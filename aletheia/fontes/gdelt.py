"""GDELT DOC 2.0: notícias do mundo inteiro, busca por texto, em dezenas de línguas.

API: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

A janela é **móvel, de cerca de três meses**: o GDELT serve à vigilância (o que saiu
agora), não à varredura do passivo. `desde` anterior a isso é cortado para o limite, e o
relatório diz a janela usada.

Cada consulta devolve no máximo 250 artigos. O adaptador pergunta **um dia por vez**; se um
dia vier cheio, pergunta de novo em quatro faixas de seis horas, para não perder o que
passou do teto. O texto vem da página do veículo, com o `robots.txt` dele respeitado.

Configuração:
    {"tipo": "gdelt", "id": "gdelt:carandiru", "busca": "carandiru",
     "limite_por_minuto": 12, "minimo_caracteres": 400}
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta

from aletheia.contrato import Documento, Referencia
from aletheia.fontes.rss import documento_html, pagina_integra
from aletheia.http import Cliente, Transporte, transporte_urllib

URL = "https://api.gdeltproject.org/api/v2/doc/doc"
TETO = 250
JANELA_DIAS = 90


def _momento(dia: date, hora: int = 0) -> str:
    return datetime(dia.year, dia.month, dia.day, hora).strftime("%Y%m%d%H%M%S")


def _data(visto: str | None) -> date | None:
    try:
        return datetime.strptime((visto or "")[:8], "%Y%m%d").date()
    except ValueError:
        return None


class Gdelt:
    respeita_robots = True  # vale para as páginas dos veículos

    def __init__(
        self,
        id: str,
        busca: str,
        cliente: Cliente,
        limite_por_minuto: int = 12,
        minimo_caracteres: int = 400,
        hoje: Callable[[], date] = date.today,
    ) -> None:
        self.id = id
        self.busca = busca
        self.cliente = cliente
        self.limite_por_minuto = limite_por_minuto
        self.minimo_caracteres = minimo_caracteres
        self.hoje = hoje
        self.desde_efetivo: date | None = None

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> Gdelt:
        limite = int(cfg.get("limite_por_minuto", 12))
        cliente = Cliente(limite, respeita_robots=cls.respeita_robots, transporte=transporte)
        return cls(cfg["id"], cfg["busca"], cliente, limite, int(cfg.get("minimo_caracteres", 400)))

    def _consultar(self, inicio: str, fim: str) -> list[dict]:
        params = {
            "query": self.busca,
            "mode": "artlist",
            "format": "json",
            "maxrecords": TETO,
            "sort": "datedesc",
            "startdatetime": inicio,
            "enddatetime": fim,
        }
        return self.cliente.requisitar(URL, params=params).json().get("articles") or []

    def listar(self, desde: date) -> Iterator[Referencia]:
        hoje = self.hoje()
        dia = max(desde, hoje - timedelta(days=JANELA_DIAS))
        self.desde_efetivo = dia
        while dia <= hoje:
            artigos = self._consultar(_momento(dia), _momento(dia + timedelta(days=1)))
            if len(artigos) >= TETO:
                artigos = []
                for hora in (0, 6, 12, 18):
                    inicio = _momento(dia, hora)
                    proximo = dia + timedelta(days=1)
                    fim = _momento(proximo) if hora == 18 else _momento(dia, hora + 6)
                    artigos += self._consultar(inicio, fim)
            for artigo in artigos:
                if artigo.get("url"):
                    yield Referencia(
                        fonte=self.id,
                        id_na_fonte=artigo["url"],
                        url=artigo["url"],
                        titulo=artigo.get("title"),
                        publicado_em=_data(artigo.get("seendate")),
                        dados={k: artigo.get(k) for k in ("domain", "language", "sourcecountry")},
                    )
            dia += timedelta(days=1)

    def baixar(self, ref: Referencia) -> Documento:
        return documento_html(ref, self.cliente.requisitar(ref.url), ref.titulo)

    def sentinela(self, doc: Documento) -> bool:
        return pagina_integra(doc, self.minimo_caracteres)
