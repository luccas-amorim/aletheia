"""O que já foi visto, por fonte. É a única memória entre rodadas.

`<raiz>/<fonte>.json` guarda a data da última rodada concluída, o hash do texto de cada
id já capturado, os **pendentes** (referências cuja captura falhou ou que a sentinela
reprovou) e o **progresso** da listagem: o que o adaptador já percorreu de uma varredura
longa (no Wayback, as fatias `prefixo|ano` concluídas).

Pendente é tentado de novo em toda rodada, mesmo fora da janela de datas; sem isso, um
item que falhou uma vez sairia da janela e nunca mais seria lido, em silêncio. O
progresso é o que faz uma listagem interrompida continuar de onde parou, em vez de
recomeçar de 1996 toda segunda-feira. Apagar o arquivo equivale a reler tudo.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from aletheia.captura import nome_seguro
from aletheia.contrato import Referencia

# `dados` de uma referência pendente acima disto não é guardado: pode conter o texto do
# item (nomes de pessoas), e o adaptador precisa saber baixar de novo só pela URL.
LIMITE_DADOS_PENDENTE = 4000


@dataclass
class Estado:
    fonte: str
    ultima_rodada: date | None = None
    vistos: dict[str, str] = field(default_factory=dict)  # id_na_fonte -> hash_texto
    pendentes: dict[str, dict] = field(default_factory=dict)  # id_na_fonte -> referência
    progresso: dict = field(default_factory=dict)  # do adaptador; opaco para o motor

    def visto(self, id_na_fonte: str) -> bool:
        return id_na_fonte in self.vistos

    def pendurar(self, ref: Referencia, motivo: str) -> None:
        anterior = self.pendentes.get(ref.id_na_fonte, {})
        dados = asdict(ref)
        dados["publicado_em"] = ref.publicado_em.isoformat() if ref.publicado_em else None
        extras = dict(ref.dados) if ref.dados is not None else None
        if extras is not None:
            tamanho = len(json.dumps(extras, ensure_ascii=False))
            if tamanho > LIMITE_DADOS_PENDENTE:
                extras = None
        dados["dados"] = extras
        self.pendentes[ref.id_na_fonte] = {
            "ref": dados,
            "motivo": motivo,
            "tentativas": anterior.get("tentativas", 0) + 1,
        }

    def resolver(self, id_na_fonte: str, hash_texto: str) -> None:
        self.pendentes.pop(id_na_fonte, None)
        self.vistos[id_na_fonte] = hash_texto

    def referencias_pendentes(self) -> list[Referencia]:
        refs = []
        for item in self.pendentes.values():
            dados = dict(item["ref"])
            if dados.get("publicado_em"):
                dados["publicado_em"] = date.fromisoformat(dados["publicado_em"])
            refs.append(Referencia(**dados))
        return refs


def caminho(raiz: Path, fonte: str) -> Path:
    return Path(raiz) / f"{nome_seguro(fonte)}.json"


def ler(raiz: Path, fonte: str) -> Estado:
    arquivo = caminho(raiz, fonte)
    if not arquivo.exists():
        return Estado(fonte)
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    ultima = dados.get("ultima_rodada")
    return Estado(
        fonte,
        date.fromisoformat(ultima) if ultima else None,
        dados.get("vistos", {}),
        dados.get("pendentes", {}),
        dados.get("progresso", {}),
    )


def gravar(raiz: Path, estado: Estado) -> None:
    arquivo = caminho(raiz, estado.fonte)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".json.part")
    dados = {
        "fonte": estado.fonte,
        "ultima_rodada": estado.ultima_rodada.isoformat() if estado.ultima_rodada else None,
        "vistos": dict(sorted(estado.vistos.items())),
        "pendentes": dict(sorted(estado.pendentes.items())),
        "progresso": estado.progresso,
    }
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporario, arquivo)
