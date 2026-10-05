"""O relatório da rodada em dois tamanhos.

O completo tem uma linha por item, inclusive os descartados, com o motivo: três segundos
de leitura por linha, e a decisão do filtro fica auditável. O resumo tem só o que pede
ação, e é o que vira corpo de issue.
"""

from __future__ import annotations

from pathlib import Path

from aletheia.rodada import FALHA, ROBOTS, SENTINELA, TRIADO, Linha, Rodada
from aletheia.saidas.jsonl import contagens


def _celula(texto: str | None) -> str:
    return (texto or "").replace("|", "\\|").replace("\n", " ").strip()


def _titulo(linha: Linha) -> str:
    titulo = _celula(linha.titulo) or linha.ref.id_na_fonte
    return f"[{titulo[:120]}]({linha.ref.url})"


def _cabecalho(rodada: Rodada) -> list[str]:
    c = contagens(rodada)
    partes = [f"{k}: {v}" for k, v in {**c["situacao"], **c["motivo"]}.items()]
    linhas = [
        f"# Alétheia: rodada {rodada.id} ({rodada.modo})",
        "",
        f"Léxico `{rodada.lexico_id}` versão `{rodada.lexico_versao}`. "
        f"Início {rodada.inicio}, fim {rodada.fim}.",
        "",
        f"Contagens: {', '.join(partes) or 'nenhum item'}.",
    ]
    if rodada.desde:
        janelas = ", ".join(f"`{f}` desde {d}" for f, d in rodada.desde.items())
        linhas += ["", f"Janelas: {janelas}."]
    return linhas


def _secao(titulo: str, linhas: list[Linha], com_trecho: bool) -> list[str]:
    if not linhas:
        return []
    saida = ["", f"## {titulo} ({len(linhas)})", ""]
    for linha in linhas:
        r = linha.resultado
        detalhe = ""
        if r is not None:
            chaves = ", ".join(f"`{c}`" for c in r.chaves)
            detalhe = f" nível {r.nivel}, `{r.motivo}`" + (f", {chaves}" if chaves else "")
        elif linha.erro:
            detalhe = f" {_celula(linha.erro)[:200]}"
        arquivo = f" · [cópia]({linha.snapshot})" if linha.snapshot else ""
        saida.append(f"- {_titulo(linha)} ({linha.ref.fonte}){detalhe}{arquivo}")
        if com_trecho and r is not None and r.trecho:
            saida.append(f"  > {_celula(r.trecho)} *({r.onde})*")
    return saida


def _grupos(rodada: Rodada) -> dict[str, list[Linha]]:
    triadas = [linha for linha in rodada.linhas if linha.situacao == TRIADO]
    return {
        "aceitos": [linha for linha in triadas if linha.nivel == 3],
        "juizo": [linha for linha in triadas if linha.nivel == 2],
        "nivel1": [linha for linha in triadas if linha.nivel == 1],
        "nivel0": [linha for linha in triadas if linha.nivel == 0],
        "falhas": [linha for linha in rodada.linhas if linha.situacao in (FALHA, SENTINELA)],
        "robots": [linha for linha in rodada.linhas if linha.situacao == ROBOTS],
    }


def _falhas_de_fonte(rodada: Rodada) -> list[str]:
    saida: list[str] = []
    if rodada.falhas_de_fonte:
        saida += ["", f"## Fontes que falharam ({len(rodada.falhas_de_fonte)})", ""]
        saida += [f"- `{f}`: {_celula(e)[:300]}" for f, e in rodada.falhas_de_fonte.items()]
        if rodada.pede_leitura:
            saida += ["", "Há itens que pedem leitura nesta rodada, além das falhas acima."]
    if rodada.incompletas:
        saida += [
            "",
            f"## Listagens que continuam na próxima rodada ({len(rodada.incompletas)})",
            "",
        ]
        saida += [f"- `{f}`: {_celula(e)[:300]}" for f, e in rodada.incompletas.items()]
    return saida


def resumo(rodada: Rodada) -> str:
    g = _grupos(rodada)
    corpo = _cabecalho(rodada) + _falhas_de_fonte(rodada)
    corpo += _secao("Pede juízo", g["juizo"], com_trecho=True)
    corpo += _secao("Aceitos", g["aceitos"], com_trecho=True)
    corpo += _secao("Falhas de captura ou de integridade", g["falhas"], com_trecho=False)
    if not (g["juizo"] or g["aceitos"] or g["falhas"] or rodada.falhas_de_fonte):
        corpo += ["", "Nada pede leitura nesta rodada."]
    return "\n".join(corpo) + "\n"


def completo(rodada: Rodada) -> str:
    g = _grupos(rodada)
    corpo = _cabecalho(rodada) + _falhas_de_fonte(rodada)
    corpo += _secao("Pede juízo", g["juizo"], com_trecho=True)
    corpo += _secao("Aceitos", g["aceitos"], com_trecho=True)
    corpo += _secao("Falhas de captura ou de integridade", g["falhas"], com_trecho=False)
    corpo += _secao("Bloqueados por robots.txt", g["robots"], com_trecho=False)
    corpo += _secao("Descartados no nível 1", g["nivel1"], com_trecho=True)
    corpo += _secao("Descartados no nível 0", g["nivel0"], com_trecho=False)
    return "\n".join(corpo) + "\n"


def escrever(rodada: Rodada, pasta: Path) -> None:
    (pasta / "relatorio-resumo.md").write_text(resumo(rodada), encoding="utf-8")
    (pasta / "relatorio-completo.md").write_text(completo(rodada), encoding="utf-8")
