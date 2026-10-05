"""Captura: monta o Documento com proveniência e grava o texto integral no corpus.

O arquivo é escrito primeiro como `.part` e só é promovido ao nome final quando a
sentinela da fonte aprova. Arquivo no caminho canônico significa "íntegro", por
construção: quem varre o corpus não precisa ler metadado para saber se pode confiar.
O `.part` reprovado fica no diretório para diagnóstico e não casa com `*.json`.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from aletheia.contrato import Documento, Fonte, Referencia
from aletheia.texto import normalizar, sha256


def montar_documento(
    ref: Referencia,
    texto: str,
    *,
    bruto: bytes | None = None,
    cabecalhos: dict[str, str] | None = None,
    destaques: dict[str, str] | None = None,
    agora: datetime | None = None,
) -> Documento:
    """O único lugar que calcula hash e data de captura. Adaptadores chamam este."""
    texto = normalizar(texto)
    return Documento(
        ref=ref,
        texto=texto,
        capturado_em=(agora or datetime.now(UTC)).replace(microsecond=0),
        hash_texto=sha256(texto),
        bruto=bruto,
        cabecalhos=dict(cabecalhos or {}),
        destaques={k: normalizar(v) for k, v in (destaques or {}).items() if v and v.strip()},
    )


def nome_seguro(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", texto).strip("_") or "_"


def documento_para_dict(doc: Documento) -> dict:
    ref = asdict(doc.ref)
    ref.pop("dados", None)
    if isinstance(doc.ref.publicado_em, date):
        ref["publicado_em"] = doc.ref.publicado_em.isoformat()
    return {
        "ref": ref,
        "texto": doc.texto,
        "capturado_em": doc.capturado_em.isoformat(),
        "hash_texto": doc.hash_texto,
        "cabecalhos": doc.cabecalhos,
        "destaques": doc.destaques,
    }


def documento_de_dict(dados: dict) -> Documento:
    ref = dict(dados["ref"])
    if ref.get("publicado_em"):
        ref["publicado_em"] = date.fromisoformat(ref["publicado_em"])
    return Documento(
        ref=Referencia(**ref),
        texto=dados["texto"],
        capturado_em=datetime.fromisoformat(dados["capturado_em"]),
        hash_texto=dados["hash_texto"],
        cabecalhos=dados.get("cabecalhos", {}),
        destaques=dados.get("destaques", {}),
    )


class Corpus:
    """`<raiz>/<fonte>/<hash>.json`: um arquivo por texto distinto dentro da fonte.

    O mesmo texto chegando por outro id da mesma fonte (republicação) cai no mesmo
    arquivo, e a referência gravada passa a ser a da captura mais recente. O relatório e
    o JSONL da rodada guardam as duas.

    Com `guardar=False` nada é gravado: a sentinela confere o documento em memória, a
    triagem lê o texto e ele é descartado. É a escolha de quem quer só o catálogo (URL e
    identificadores), ao preço de não poder retriar sem baixar de novo.
    """

    def __init__(self, raiz: Path, guardar: bool = True) -> None:
        self.raiz = Path(raiz)
        self.guardar = guardar

    def relativo(self, caminho: Path | None) -> str | None:
        """Caminho como vai para a saída: relativo ao diretório de dados, portável."""
        if caminho is None:
            return None
        return Path(caminho).relative_to(self.raiz.parent).as_posix()

    def caminho(self, doc: Documento) -> Path:
        return self.raiz / nome_seguro(doc.ref.fonte) / f"{doc.hash_texto}.json"

    def gravar(self, doc: Documento, fonte: Fonte) -> tuple[bool, Path | None]:
        """(íntegro, caminho). Grava `.part`, pergunta à sentinela, promove se passar."""
        if not self.guardar:
            return fonte.sentinela(doc), None
        final = self.caminho(doc)
        final.parent.mkdir(parents=True, exist_ok=True)
        parcial = final.with_suffix(".json.part")
        parcial.write_text(
            json.dumps(documento_para_dict(doc), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        if not fonte.sentinela(doc):
            return False, parcial
        os.replace(parcial, final)
        return True, final

    def documentos(self, fonte: str | None = None) -> Iterator[tuple[Documento, Path]]:
        pastas = [self.raiz / nome_seguro(fonte)] if fonte else sorted(self.raiz.glob("*"))
        for pasta in pastas:
            for arquivo in sorted(pasta.glob("*.json")):
                yield documento_de_dict(json.loads(arquivo.read_text(encoding="utf-8"))), arquivo
