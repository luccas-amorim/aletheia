"""Triagem em níveis. Determinística: as mesmas entradas dão sempre o mesmo resultado.

| Nível | Significa                                               | Motivo          |
|-------|---------------------------------------------------------|-----------------|
| 0     | nenhuma forma do léxico no texto                        | sem_termo       |
| 0     | só há ocorrências anuladas por exclusão                 | so_exclusao     |
| 1     | termo presente, sem contexto exigido                    | sem_contexto    |
| 2     | termo e contexto, mas o termo não está em destaque      | pede_juizo      |
| 3     | termo e contexto, e o termo está num destaque da fonte  | aceito          |

O corte não apaga: todo nível sai no relatório completo, com o motivo e o trecho que
decidiu. Falso positivo é aceitável; falso negativo não.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aletheia.contrato import Documento
from aletheia.lexico import Casador
from aletheia.texto import dobrar

RAIO_TRECHO = 160


@dataclass
class Resultado:
    nivel: int
    motivo: str
    chaves: list[str] = field(default_factory=list)
    categorias: list[str] = field(default_factory=list)
    pontuacao: float = 0.0
    trecho: str | None = None
    onde: str | None = None  # "texto" ou o nome do destaque em que o trecho foi achado

    def como_dict(self) -> dict:
        return {
            "nivel": self.nivel,
            "motivo": self.motivo,
            "chaves": self.chaves,
            "categorias": self.categorias,
            "pontuacao": self.pontuacao,
            "trecho": self.trecho,
            "onde": self.onde,
        }


def recortar(texto: str, inicio: int, fim: int, raio: int = RAIO_TRECHO) -> str:
    a, b = max(0, inicio - raio), min(len(texto), fim + raio)
    trecho = " ".join(texto[a:b].split())
    return f"{'…' if a > 0 else ''}{trecho}{'…' if b < len(texto) else ''}"


def triar(doc: Documento, casador: Casador) -> Resultado:
    texto = doc.texto
    dobrado = dobrar(texto)
    validas, anuladas = casador.ocorrencias(dobrado)

    if not validas:
        if anuladas:
            oc = anuladas[0]
            return Resultado(
                0, "so_exclusao", trecho=recortar(texto, oc.inicio, oc.fim), onde="texto"
            )
        return Resultado(0, "sem_termo")

    chaves = list(dict.fromkeys(o.chave for o in validas))
    termos = [casador.termo(c) for c in chaves]
    categorias = list(dict.fromkeys(c for t in termos for c in t.categorias))
    pontuacao = round(sum(t.peso for t in termos), 4)
    primeira = validas[0]
    base = Resultado(1, "", chaves, categorias, pontuacao)

    marcador = casador.contexto(dobrado)
    if not marcador:
        base.motivo = "sem_contexto"
        base.trecho, base.onde = recortar(texto, primeira.inicio, primeira.fim), "texto"
        return base

    for nome, destaque in doc.destaques.items():
        no_destaque, _ = casador.ocorrencias(dobrar(destaque))
        if no_destaque:
            oc = no_destaque[0]
            base.nivel, base.motivo = 3, "aceito"
            base.trecho, base.onde = recortar(destaque, oc.inicio, oc.fim), nome
            return base

    base.nivel, base.motivo = 2, "pede_juizo"
    base.trecho, base.onde = recortar(texto, primeira.inicio, primeira.fim), "texto"
    return base
