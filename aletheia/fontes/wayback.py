"""Wayback Machine (Internet Archive): o que um domínio publicou e o arquivo guardou.

Não há busca por texto no Wayback, só por endereço. Este adaptador pergunta ao servidor
CDX por toda URL arquivada cujo endereço case uma expressão (`carandiru` no caminho) e
baixa a cópia arquivada. É o canal que recupera o que já saiu do ar, e cada texto vem com
a data da captura.

**Por que fatiar.** Medido em 05/10/2026: a consulta pelo domínio inteiro da Folha desde
1996, com filtro por regex, estoura em 504 depois de 60 s (o CDX precisa varrer 4.886
blocos de índice antes de devolver a primeira linha); a mesma consulta restrita ao
prefixo `www1.folha.uol.com.br/cotidiano/` e a um ano responde em 4,6 s. Por isso o
adaptador trabalha em **fatias `prefixo × ano`**, cada uma paginada por `resumeKey`, e
anota no `progresso` (guardado no estado da fonte) cada fatia concluída. Uma varredura
interrompida continua da fatia seguinte na próxima rodada, em vez de recomeçar de 1996.
O ano corrente nunca é dado por concluído: ainda recebe capturas.

API: https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server

- `matchType=prefix` com `url=<prefixo>`; `matchType=domain` quando a configuração traz
  `dominio` em vez de `prefixos` (serve a sites pequenos; evite em veículos grandes).
- `filter=original:<regex>` filtra pelo endereço; `(?i)` ignora caixa.
- `collapse=urlkey` devolve uma captura por URL dentro da fatia.
- `showResumeKey=true` pagina: a última linha da resposta é a chave da próxima página.
- O texto vem do modo `id_` (`/web/<timestamp>id_/<url>`), sem a barra do Wayback.

`publicado_em` é a **data da captura**, não da publicação. O arquivo começa em 1996:
`desde` anterior é cortado e o relatório diz a janela efetiva. O CDX e o modo `id_` são a
interface pública e documentada do arquivo; o adaptador declara API própria (não lê
`robots.txt`) e se limita a 15 requisições por minuto.

Configuração:
    {"tipo": "wayback", "id": "wayback:folha",
     "prefixos": ["www1.folha.uol.com.br/cotidiano/", "www1.folha.uol.com.br/poder/"],
     "filtro": "(?i).*carandiru.*", "fatia": "ano", "por_pagina": 500,
     "limite_por_minuto": 15, "fatias_por_rodada": 60, "estrato": "imprensa",
     "excluir": "<regex opcional; o padrão tira feed, embed, amp, busca, listagens e mídia>"}
    {"tipo": "wayback", "id": "wayback:ponte", "dominio": "ponte.org", "fatia": "tudo"}
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from datetime import date, datetime
from urllib.parse import urlencode

from aletheia.arquivo import ARQUIVO, CDX, snapshot
from aletheia.contrato import Documento, Referencia
from aletheia.fontes.rss import MARCAS_DE_ERRO, documento_html, pagina_integra
from aletheia.http import Cliente, Transporte, transporte_urllib

__all__ = ["ARQUIVO", "CDX", "Wayback", "MARCAS_DO_WAYBACK"]

CAMPOS = "timestamp,original,statuscode,mimetype,digest"
FILTRO_PADRAO = "(?i).*carandiru.*"
# O Internet Archive começou a capturar a web em 1996. `desde` anterior é cortado para cá
# (e o relatório da rodada diz a janela efetiva): o massacre é de 1992, mas o que a web
# guarda dele começa aqui. Antes disso, só a Hemeroteca Digital, por `lista`.
INICIO_DO_ARQUIVO = date(1996, 1, 1)
# Endereços que casam o filtro mas não são documento: feed, embed e AMP (cópias), páginas
# de busca e de listagem (tag, categoria, autor, paginação), anexos de mídia. Medido na
# primeira varredura real de ponte.org: 134 URLs listadas, 64 documentos distintos.
EXCLUIR_PADRAO = (
    r"(?i)(/feed/?$|/embed/?$|/amp/?$|/page/\d+/?$|/(tag|tags|categoria|category|autor|author|"
    r"tema|assunto|busca|search)/|[?&](s|q|busca|p|page|paged|replytocom|share|print)=|"
    r"\.(jpe?g|png|gif|svg|webp|pdf|mp3|mp4|css|js)(\?|$))"
)

MARCAS_DO_WAYBACK = (
    *MARCAS_DE_ERRO,
    "wayback machine doesn't have that page archived",
    "hrm. the wayback machine has not archived",
    "this url has been excluded from the wayback machine",
)


def _data(timestamp: str) -> date | None:
    try:
        return datetime.strptime(timestamp[:8], "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


class Wayback:
    respeita_robots = False  # API documentada do arquivo; ver docstring
    usa_progresso = True

    def __init__(
        self,
        id: str,
        prefixos: list[str],
        cliente: Cliente,
        *,
        match_type: str = "prefix",
        filtro: str = FILTRO_PADRAO,
        fatia: str = "ano",
        limite_por_minuto: int = 15,
        minimo_caracteres: int = 400,
        por_pagina: int = 500,
        fatias_por_rodada: int | None = None,
        excluir: str | None = EXCLUIR_PADRAO,
        hoje: Callable[[], date] = date.today,
    ) -> None:
        if fatia not in ("ano", "tudo"):
            raise ValueError(f"{id}: fatia precisa ser 'ano' ou 'tudo', não {fatia!r}")
        self.id = id
        self.prefixos = [p.strip() for p in prefixos if p.strip()]
        if not self.prefixos:
            raise ValueError(f"{id}: nenhum prefixo ou domínio")
        self.cliente = cliente
        self.match_type = match_type
        self.filtro = filtro
        self.fatia = fatia
        self.limite_por_minuto = limite_por_minuto
        self.minimo_caracteres = minimo_caracteres
        self.por_pagina = por_pagina
        self.fatias_por_rodada = fatias_por_rodada
        self.excluir = re.compile(excluir) if excluir else None
        self.hoje = hoje
        self.listagem_incompleta: str | None = None
        self.desde_efetivo: date | None = None

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> Wayback:
        limite = int(cfg.get("limite_por_minuto", 15))
        cliente = Cliente(
            limite,
            respeita_robots=cls.respeita_robots,
            transporte=transporte,
            tempo_limite=float(cfg.get("tempo_limite", 120)),
        )
        if cfg.get("prefixos"):
            prefixos, match_type, fatia = list(cfg["prefixos"]), "prefix", "ano"
        elif cfg.get("dominio"):
            # Domínio inteiro só serve a sites pequenos; neles, uma consulta basta.
            prefixos, match_type, fatia = [cfg["dominio"]], "domain", "tudo"
        else:
            raise ValueError(f"{cfg.get('id')}: informe 'prefixos' (lista) ou 'dominio'")
        return cls(
            cfg["id"],
            prefixos,
            cliente,
            match_type=match_type,
            filtro=cfg.get("filtro", FILTRO_PADRAO),
            fatia=cfg.get("fatia", fatia),
            limite_por_minuto=limite,
            minimo_caracteres=int(cfg.get("minimo_caracteres", 400)),
            por_pagina=int(cfg.get("por_pagina", 500)),
            fatias_por_rodada=(
                int(cfg["fatias_por_rodada"]) if cfg.get("fatias_por_rodada") else None
            ),
            excluir=cfg.get("excluir", EXCLUIR_PADRAO) or None,
        )

    # --- fatias -------------------------------------------------------------------

    def fatias(self, desde: date) -> list[tuple[str, int | None, date, date | None]]:
        """(prefixo, ano ou None, início, fim) na ordem em que serão percorridas."""
        hoje = self.hoje()
        desde = max(desde, INICIO_DO_ARQUIVO)
        saida = []
        for prefixo in self.prefixos:
            if self.fatia == "tudo":
                saida.append((prefixo, None, desde, None))
                continue
            for ano in range(desde.year, hoje.year + 1):
                inicio = desde if ano == desde.year else date(ano, 1, 1)
                fim = date(ano, 12, 31) if ano < hoje.year else None
                saida.append((prefixo, ano, inicio, fim))
        return saida

    @staticmethod
    def chave(prefixo: str, ano: int | None) -> str:
        return f"{prefixo}|{ano if ano is not None else 'tudo'}"

    def _parametros(
        self, prefixo: str, inicio: date, fim: date | None, retomar: str | None
    ) -> list[tuple[str, str]]:
        # Lista de pares: `filter` se repete, e um dicionário perderia as repetições.
        params = [
            ("url", prefixo),
            ("matchType", self.match_type),
            ("filter", f"original:{self.filtro}"),
            ("filter", "statuscode:200"),
            ("filter", "mimetype:text/html"),
            ("collapse", "urlkey"),
            ("output", "json"),
            ("fl", CAMPOS),
            ("from", inicio.strftime("%Y%m%d")),
        ]
        if fim is not None:
            params.append(("to", fim.strftime("%Y%m%d")))
        params += [("limit", str(self.por_pagina)), ("showResumeKey", "true")]
        if retomar:
            params.append(("resumeKey", retomar))
        return params

    def _listar_fatia(self, prefixo: str, inicio: date, fim: date | None) -> Iterator[Referencia]:
        retomar: str | None = None
        while True:
            url = f"{CDX}?{urlencode(self._parametros(prefixo, inicio, fim, retomar))}"
            linhas = self.cliente.requisitar(url).json() or []
            if not linhas:
                return
            cabecalho, corpo = linhas[0], linhas[1:]
            retomar = None
            # Com showResumeKey, o fim é: [..., [], ["<chave>"]].
            if len(corpo) >= 2 and corpo[-2] == [] and len(corpo[-1]) == 1:
                retomar = corpo[-1][0]
                corpo = corpo[:-2]
            for valores in corpo:
                if not valores:
                    continue
                registro = dict(zip(cabecalho, valores, strict=False))
                original, momento = registro.get("original"), registro.get("timestamp", "")
                if not original or (self.excluir and self.excluir.search(original)):
                    continue
                yield Referencia(
                    fonte=self.id,
                    id_na_fonte=original,
                    url=snapshot(momento, original),
                    titulo=original,
                    publicado_em=_data(momento),
                    dados={
                        "original": original,
                        "timestamp": momento,
                        "snapshot": snapshot(momento, original),
                        "prefixo": prefixo,
                    },
                )
            if not retomar:
                return

    # --- contrato -----------------------------------------------------------------

    def listar(self, desde: date, progresso: dict | None = None) -> Iterator[Referencia]:
        progresso = progresso if progresso is not None else {}
        concluidas: list[str] = list(progresso.get("concluidas", []))
        self.listagem_incompleta = None
        self.desde_efetivo = max(desde, INICIO_DO_ARQUIVO)
        feitas = 0
        pendentes = [f for f in self.fatias(desde) if self.chave(f[0], f[1]) not in concluidas]
        for indice, (prefixo, ano, inicio, fim) in enumerate(pendentes):
            if self.fatias_por_rodada is not None and feitas >= self.fatias_por_rodada:
                restantes = len(pendentes) - indice
                self.listagem_incompleta = (
                    f"{restantes} fatia(s) ficaram para a próxima rodada "
                    f"(limite de {self.fatias_por_rodada} por rodada)"
                )
                return
            yield from self._listar_fatia(prefixo, inicio, fim)
            feitas += 1
            if fim is not None:  # ano fechado: não volta a ser consultado
                concluidas.append(self.chave(prefixo, ano))
                progresso["concluidas"] = concluidas

    def baixar(self, ref: Referencia) -> Documento:
        # A manchete vem da página: o "título" da referência é só a URL.
        return documento_html(ref, self.cliente.requisitar(ref.url))

    def sentinela(self, doc: Documento) -> bool:
        return pagina_integra(doc, self.minimo_caracteres, MARCAS_DO_WAYBACK)

    # --- sondagem (CLI `sondar`) -----------------------------------------------------

    def blocos(self, prefixo: str) -> int | None:
        """Quantos blocos de índice o CDX precisa varrer para este prefixo (showNumPages)."""
        params = [("url", prefixo), ("matchType", self.match_type), ("showNumPages", "true")]
        corpo = self.cliente.requisitar(f"{CDX}?{urlencode(params)}").corpo.decode().strip()
        return int(corpo) if corpo.isdigit() else None
