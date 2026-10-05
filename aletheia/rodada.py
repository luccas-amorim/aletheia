"""Uma rodada: para cada fonte, listar, baixar o que é novo, conferir, triar, gravar.

Falha de uma fonte não derruba as outras, mas não passa calada: a rodada termina com
código 2 e a fonte aparece no resumo. Item que falhou na captura ou na sentinela não é
marcado como visto: fica pendente no estado e é tentado de novo em toda rodada seguinte,
mesmo depois de sair da janela de datas.

Listagem que falha no meio **não perde o que já listou**: as referências lidas até o erro
são baixadas e triadas, o progresso anotado pelo adaptador é gravado, e só a data da
última rodada deixa de avançar. É o que impede uma varredura longa de recomeçar do zero.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from aletheia import estado
from aletheia.captura import Corpus
from aletheia.config import Config
from aletheia.contrato import Documento, Fonte, Referencia
from aletheia.http import BloqueadoPorRobots, redigir
from aletheia.lexico import Casador
from aletheia.triagem import Resultado, triar

log = logging.getLogger(__name__)

# Situação de cada linha do relatório.
TRIADO = "triado"
SENTINELA = "reprovado_sentinela"
FALHA = "falha_captura"
ROBOTS = "bloqueado_robots"

SEM_NADA, ERRO, PEDE_LEITURA = 0, 2, 3


@dataclass
class Linha:
    ref: Referencia
    situacao: str
    resultado: Resultado | None = None
    hash_texto: str | None = None
    capturado_em: str | None = None
    corpus: str | None = None
    erro: str | None = None
    # Cópia de referência no Wayback (`.../web/<ts>id_/<url>`), quando conhecida.
    snapshot: str | None = None
    # Manchete lida da página, quando a listagem só trazia a URL (Wayback, tópico).
    manchete: str | None = None

    @property
    def titulo(self) -> str | None:
        """O melhor título que se tem: o da fonte, se não for só a URL; senão, a manchete."""
        ref = self.ref.titulo
        if ref and ref.strip() and ref.strip() != self.ref.url and not _parece_url(ref):
            return ref.strip()
        return (self.manchete or ref or "").strip() or None

    @property
    def nivel(self) -> int | None:
        return self.resultado.nivel if self.resultado else None

    def como_dict(self) -> dict:
        ref = self.ref
        return {
            "fonte": ref.fonte,
            "id_na_fonte": ref.id_na_fonte,
            "url": ref.url,
            "titulo": self.titulo,
            "publicado_em": ref.publicado_em.isoformat() if ref.publicado_em else None,
            "capturado_em": self.capturado_em,
            "hash_texto": self.hash_texto,
            "situacao": self.situacao,
            **(self.resultado.como_dict() if self.resultado else {"nivel": None}),
            "corpus": self.corpus,
            "snapshot": self.snapshot,
            "erro": self.erro,
        }


@dataclass
class Rodada:
    id: str
    lexico_id: str
    lexico_versao: str
    modo: str  # "rodar" ou "retriar"
    inicio: str
    fim: str | None = None
    linhas: list[Linha] = field(default_factory=list)
    falhas_de_fonte: dict[str, str] = field(default_factory=dict)
    # Fontes cuja listagem parou de propósito (limite de fatias por rodada) e continua
    # na próxima. Não é falha: a data da última rodada é que não avança.
    incompletas: dict[str, str] = field(default_factory=dict)
    desde: dict[str, str] = field(default_factory=dict)

    @property
    def pede_leitura(self) -> bool:
        return any((linha.nivel or 0) >= 2 for linha in self.linhas)

    @property
    def codigo_saida(self) -> int:
        """2 se alguma fonte falhou (o relatório diz também se há leitura pendente)."""
        if self.falhas_de_fonte:
            return ERRO
        if self.pede_leitura:
            return PEDE_LEITURA
        return SEM_NADA


def nova_rodada(casador: Casador, modo: str, agora: datetime | None = None) -> Rodada:
    agora = (agora or datetime.now(UTC)).replace(microsecond=0)
    lex = casador.lexico
    return Rodada(
        id=agora.strftime("%Y%m%dT%H%M%SZ"),
        lexico_id=lex.id,
        lexico_versao=lex.versao,
        modo=modo,
        inicio=agora.isoformat(),
    )


def _snapshot(ref: Referencia) -> str | None:
    return (ref.dados or {}).get("snapshot") if ref.dados else None


def _parece_url(texto: str) -> bool:
    return bool(re.match(r"^(https?://|www\.)\S+$", texto.strip()))


def linha_triada(doc: Documento, casador: Casador, caminho: str | None) -> Linha:
    return Linha(
        ref=doc.ref,
        situacao=TRIADO,
        resultado=triar(doc, casador),
        hash_texto=doc.hash_texto,
        capturado_em=doc.capturado_em.isoformat(),
        corpus=caminho,
        snapshot=_snapshot(doc.ref),
        manchete=doc.destaques.get("manchete") or doc.destaques.get("titulo"),
    )


def _listar(fonte: Fonte, desde: date, memoria: estado.Estado) -> Iterable[Referencia]:
    if getattr(fonte, "usa_progresso", False):
        return fonte.listar(desde, memoria.progresso)  # type: ignore[call-arg]
    return fonte.listar(desde)


def processar_fonte(
    fonte: Fonte,
    casador: Casador,
    corpus: Corpus,
    memoria: estado.Estado,
    desde: date,
    rodada: Rodada,
) -> None:
    rodada.desde[fonte.id] = desde.isoformat()
    referencias: list[Referencia] = []
    try:
        for ref in _listar(fonte, desde, memoria):
            referencias.append(ref)
    # Fronteira com o adaptador: qualquer erro dele (feed malformado é SyntaxError) é
    # falha desta fonte, nunca da rodada inteira. O que foi listado antes segue adiante.
    except Exception as erro:  # noqa: BLE001
        mensagem = redigir(f"{type(erro).__name__}: {erro}")
        log.error("%s: listagem falhou: %s", fonte.id, mensagem)
        rodada.falhas_de_fonte[fonte.id] = f"listagem: {mensagem}"
    if motivo := getattr(fonte, "listagem_incompleta", None):
        rodada.incompletas[fonte.id] = str(motivo)
    efetivo = getattr(fonte, "desde_efetivo", None)
    if isinstance(efetivo, date) and efetivo != desde:
        rodada.desde[fonte.id] = f"{desde.isoformat()} (efetivo {efetivo.isoformat()})"

    unicas: dict[str, Referencia] = {}
    for ref in [*referencias, *memoria.referencias_pendentes()]:
        unicas.setdefault(ref.id_na_fonte, ref)  # a listada agora vence a guardada
    novas = [r for r in unicas.values() if not memoria.visto(r.id_na_fonte)]
    log.info(
        "%s: %d listadas, %d pendentes, %d a baixar desde %s",
        fonte.id, len(referencias), len(memoria.pendentes), len(novas), desde,
    )  # fmt: skip
    for ref in novas:
        try:
            doc = fonte.baixar(ref)
        except BloqueadoPorRobots as erro:
            rodada.linhas.append(Linha(ref, ROBOTS, erro=redigir(str(erro))))
            # Política, não falha: marcar como visto evita bater na mesma porta toda rodada.
            memoria.resolver(ref.id_na_fonte, "")
            continue
        except Exception as erro:  # noqa: BLE001 (mesma fronteira)
            rodada.linhas.append(Linha(ref, FALHA, erro=redigir(f"{type(erro).__name__}: {erro}")))
            memoria.pendurar(ref, FALHA)
            continue
        try:
            integro, caminho = corpus.gravar(doc, fonte)
        except Exception as erro:  # noqa: BLE001 (sentinela é código do adaptador)
            rodada.linhas.append(Linha(ref, FALHA, erro=redigir(f"sentinela: {erro}")))
            memoria.pendurar(ref, FALHA)
            continue
        if not integro:
            rodada.linhas.append(
                Linha(
                    ref,
                    SENTINELA,
                    hash_texto=doc.hash_texto,
                    corpus=corpus.relativo(caminho),
                    snapshot=_snapshot(ref),
                )
            )
            memoria.pendurar(ref, SENTINELA)
            continue
        rodada.linhas.append(linha_triada(doc, casador, corpus.relativo(caminho)))
        memoria.resolver(ref.id_na_fonte, doc.hash_texto)


def rodar(
    config: Config,
    fontes: Iterable[Fonte],
    casador: Casador,
    *,
    desde: date | None = None,
    usar_estado: bool = True,
    hoje: date | None = None,
    agora: datetime | None = None,
) -> Rodada:
    hoje = hoje or (agora.date() if agora else date.today())
    rodada = nova_rodada(casador, "rodar", agora)
    corpus = Corpus(config.corpus, guardar=config.guardar_texto)
    for fonte in fontes:
        memoria = estado.ler(config.estado, fonte.id) if usar_estado else estado.Estado(fonte.id)
        inicio = desde
        if inicio is None and memoria.ultima_rodada:
            # A fonte pode declarar margem própria (quem publica com atraso).
            margem = getattr(fonte, "margem_dias", config.margem_dias)
            inicio = memoria.ultima_rodada - timedelta(days=margem)
        if inicio is None:
            inicio = config.desde or hoje - timedelta(days=7)
        processar_fonte(fonte, casador, corpus, memoria, inicio, rodada)
        if usar_estado:
            # Vistos, pendentes e progresso são gravados sempre; a data só avança quando a
            # listagem terminou inteira, para que a janela seguinte cubra o que faltou.
            if fonte.id not in rodada.falhas_de_fonte and fonte.id not in rodada.incompletas:
                memoria.ultima_rodada = hoje
            estado.gravar(config.estado, memoria)
    rodada.fim = (agora or datetime.now(UTC)).replace(microsecond=0).isoformat()
    return rodada


def retriar(config: Config, casador: Casador, fonte: str | None = None) -> Rodada:
    """Aplica o léxico atual ao corpus guardado, sem rede. É para quando o léxico muda."""
    rodada = nova_rodada(casador, "retriar")
    corpus = Corpus(config.corpus)
    for doc, caminho in corpus.documentos(fonte):
        rodada.linhas.append(linha_triada(doc, casador, corpus.relativo(caminho)))
    rodada.fim = datetime.now(UTC).replace(microsecond=0).isoformat()
    return rodada
