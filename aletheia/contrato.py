"""O contrato que todo adaptador de fonte cumpre.

Três funções e um bloco de metadados. O motor não sabe o que é um tribunal
nem um jornal: sabe listar, baixar e perguntar se o que baixou está íntegro.
Tudo o que for específico da origem fica dentro do adaptador, com fixture e
teste que rodam sem rede.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class Referencia:
    """O que `listar` devolve: o suficiente para decidir baixar, nada mais."""

    fonte: str  # id do adaptador, p.ex. "wayback:folha"
    id_na_fonte: str  # identificador estável dentro da origem
    url: str
    titulo: str | None = None
    publicado_em: date | None = None
    # O que a listagem já trouxe e o adaptador quer reaproveitar em `baixar`
    # (p.ex. o registro inteiro de uma API). Não entra na igualdade.
    dados: Mapping[str, Any] | None = field(default=None, compare=False, hash=False)


@dataclass
class Documento:
    """O que `baixar` devolve: o item inteiro, com proveniência."""

    ref: Referencia
    texto: str  # normalizado em UTF-8, sem marcação
    capturado_em: datetime
    hash_texto: str  # sha256 do texto normalizado
    bruto: bytes | None = None  # HTML/JSON cru, quando houver
    cabecalhos: dict[str, str] = field(default_factory=dict)
    # Trechos que a própria fonte marca como fortes: ementa, dispositivo,
    # manchete, assuntos. Termo achado aqui é o que leva a triagem ao nível 3.
    # Cada destaque também precisa estar no `texto`: a triagem conta termos no texto.
    destaques: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class Fonte(Protocol):
    """Um adaptador. Instâncias são configuradas pelo consumidor (chaves, consultas)."""

    id: str
    limite_por_minuto: int  # declarado pelo adaptador; o motor obedece
    respeita_robots: bool  # True, salvo fonte que publique API própria
    # Opcional: `margem_dias: int`, quanto voltar antes da última rodada. Fonte que
    # publica com atraso declara a sua; sem ela, vale a margem da configuração.
    # Opcional: `usa_progresso: bool`, ver `listar`.
    # Opcional: `desde_efetivo: date`, a janela que a fonte de fato consultou quando ela
    # é menor que a pedida (o GDELT só guarda ~90 dias); vai para o relatório.

    def listar(self, desde: date) -> Iterable[Referencia]:
        """Enumera o que a fonte publicou a partir de `desde`.

        Pode paginar internamente. Não baixa texto. Deve ser idempotente:
        chamar duas vezes com a mesma data devolve as mesmas referências.

        Adaptador de varredura longa declara `usa_progresso = True` e recebe um segundo
        argumento, `progresso: dict`, que o motor guarda no estado da fonte entre rodadas.
        O adaptador anota ali o que já concluiu (fatias, cursores) e, na rodada seguinte,
        continua de onde parou. Se a listagem for interrompida por erro, o que foi
        anotado antes do erro é preservado.
        """

    def baixar(self, ref: Referencia) -> Documento:
        """Baixa o item inteiro e normaliza codificação aqui, uma vez só.

        Nunca decide pelo resumo: se a origem só dá o resumo na listagem,
        é aqui que se busca o integral.
        """

    def sentinela(self, doc: Documento) -> bool:
        """Diz se o documento está íntegro.

        Página de erro com HTTP 200, texto truncado, "nenhum resultado" e
        captcha são rejeitados aqui, antes da triagem. Falhar é barato;
        aceitar texto ruim contamina a rodada em silêncio.
        """
