"""Linha de comando.

    aletheia rodar --config config.json
    aletheia rodar --config ... --fonte wayback:ponte --desde 1996-01-01
    aletheia retriar --config ...
    aletheia estimar --config ... [--desde AAAA-MM-DD]
    aletheia validar-lexico lexico.json
    aletheia validar-config config.json
    aletheia sondar --config ... [--fonte wayback:folha]

Saídas: 0 nada a ler; 2 erro de execução ou fonte fora do ar; 3 há itens que pedem juízo.
`rodada.json` traz `pede_leitura` mesmo quando o código é 2: um não esconde o outro.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from aletheia import __version__, arquivo, config, estimativa, fontes, lexico, rodada, saidas
from aletheia.saidas import catalogo, vistas


def _instancias(cfg: config.Config, caminho_config: str, escolhidas: list[str] | None):
    selecionadas = [f for f in cfg.fontes if not escolhidas or f["id"] in escolhidas]
    if escolhidas and len(selecionadas) != len(set(escolhidas)):
        raise ValueError(f"fonte desconhecida entre {escolhidas}")
    base = str(Path(caminho_config).resolve().parent)
    return [fontes.construir({"_diretorio_config": base, **f}) for f in selecionadas]


def _rodar(args: argparse.Namespace) -> int:
    cfg = config.carregar(args.config)
    casador = lexico.Casador(lexico.carregar(cfg.lexico))
    try:
        instancias = _instancias(cfg, args.config, args.fonte)
    except ValueError as erro:
        print(erro, file=sys.stderr)
        return rodada.ERRO
    desde = date.fromisoformat(args.desde) if args.desde else None
    resultado = rodada.rodar(cfg, instancias, casador, desde=desde, usar_estado=not args.sem_estado)
    pasta = saidas.escrever(resultado, cfg.saidas)
    print(f"{len(resultado.linhas)} itens; saídas em {pasta}")
    _catalogar(cfg, resultado)
    if resultado.falhas_de_fonte and resultado.pede_leitura:
        print("há itens que pedem leitura, além de fonte(s) com falha", file=sys.stderr)
    return resultado.codigo_saida


def _catalogar(cfg: config.Config, resultado: rodada.Rodada) -> None:
    if cfg.catalogo_csv is not None:
        novas = catalogo.atualizar(resultado, cfg.catalogo_csv, cfg.catalogo_nivel, cfg.estrato_de)
        print(f"catálogo: {novas} documentos novos em {cfg.catalogo_csv}")
    if cfg.vistas_csv is not None:
        n = vistas.acrescentar(resultado, cfg.vistas_csv, cfg.vistas_nivel)
        print(f"vistas: {n} observações em {cfg.vistas_csv}")
    if cfg.catalogo_csv is not None and cfg.resolver_arquivo:
        limite = int((cfg.arquivo or {}).get("limite_por_minuto", 15))
        n = catalogo.completar_snapshots(
            cfg.catalogo_csv, arquivo.Arquivo(limite_por_minuto=limite).resolver
        )
        print(f"arquivo: {n} cópias de referência resolvidas no Wayback")


def _retriar(args: argparse.Namespace) -> int:
    cfg = config.carregar(args.config)
    casador = lexico.Casador(lexico.carregar(cfg.lexico))
    resultado = rodada.retriar(cfg, casador, args.fonte)
    pasta = saidas.escrever(resultado, cfg.saidas)
    print(f"{len(resultado.linhas)} itens retriados; saídas em {pasta}")
    _catalogar(cfg, resultado)
    return resultado.codigo_saida


def _estimar(args: argparse.Namespace) -> int:
    cfg = config.carregar(args.config)
    if cfg.vistas_csv is None:
        print('configure "vistas" no config.json para estimar', file=sys.stderr)
        return rodada.ERRO
    desde = date.fromisoformat(args.desde) if args.desde else None
    por_estrato = estimativa.calcular(cfg.vistas_csv, args.nivel_minimo, cfg.estrato_de, desde)
    texto = estimativa.relatorio(por_estrato, desde)
    destino = cfg.diretorio / (args.saida or "estimativa.md")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    for nome, est in sorted(por_estrato.items()):
        piso = f"{est.chao:,.0f}" if est.chao is not None else "sem estimativa (um canal só)"
        print(f"{nome}: {len(est.observadas)} documentos observados; piso estimado: {piso}")
    print(f"relatório em {destino}")
    return rodada.SEM_NADA


def _validar_lexico(args: argparse.Namespace) -> int:
    try:
        lex = lexico.carregar(args.arquivo)
    except lexico.ErroLexico as erro:
        print(erro, file=sys.stderr)
        return rodada.ERRO
    formas = sum(len(t.formas) for t in lex.termos)
    print(f"{lex.id} {lex.versao}: válido, {len(lex.termos)} termos, {formas} formas")
    return rodada.SEM_NADA


def _validar_config(args: argparse.Namespace) -> int:
    dados = json.loads(Path(args.arquivo).read_text(encoding="utf-8"))
    problemas = config.validar(dados)
    for f in dados.get("fontes") or []:
        try:
            fontes.construir({"_diretorio_config": str(Path(args.arquivo).parent), **f})
        except (ValueError, KeyError) as erro:
            problemas.append(f"fontes[{f.get('id') or '?'}]: {erro}")
    if problemas:
        print("configuração inválida:\n  - " + "\n  - ".join(problemas), file=sys.stderr)
        return rodada.ERRO
    print(f"{args.arquivo}: válido, {len(dados.get('fontes', []))} fontes")
    return rodada.SEM_NADA


def _sondar(args: argparse.Namespace) -> int:
    """Quantos blocos de índice cada prefixo do Wayback exige: calibra as fatias."""
    cfg = config.carregar(args.config)
    instancias = _instancias(cfg, args.config, args.fonte)
    for fonte in instancias:
        if not hasattr(fonte, "blocos"):
            continue
        for prefixo in fonte.prefixos:
            try:
                blocos = fonte.blocos(prefixo)
            except Exception as erro:  # noqa: BLE001
                print(f"{fonte.id}  {prefixo}: erro: {erro}")
                continue
            aviso = "  (largo demais: prefira seções)" if blocos and blocos > 600 else ""
            print(f"{fonte.id}  {prefixo}: {blocos} blocos{aviso}")
    return rodada.SEM_NADA


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aletheia", description=__doc__.split("\n")[0])
    parser.add_argument("--version", action="version", version=f"aletheia {__version__}")
    parser.add_argument("-v", "--verboso", action="store_true")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("rodar", help="uma rodada: listar, baixar, triar, gravar")
    p.add_argument("--config", required=True)
    p.add_argument("--desde", help="AAAA-MM-DD; ignora a data guardada no estado")
    p.add_argument("--sem-estado", action="store_true", help="relê tudo e não grava estado")
    p.add_argument("--fonte", action="append", help="só esta fonte (repetível)")
    p.set_defaults(func=_rodar)

    p = sub.add_parser("retriar", help="aplica o léxico atual ao corpus guardado, sem rede")
    p.add_argument("--config", required=True)
    p.add_argument("--fonte")
    p.set_defaults(func=_retriar)

    p = sub.add_parser("estimar", help="quanto falta: captura e recaptura entre os canais")
    p.add_argument("--config", required=True)
    p.add_argument("--nivel-minimo", type=int, default=2)
    p.add_argument("--desde", help="AAAA-MM-DD: só itens a partir desta data")
    p.add_argument("--saida", help="nome do relatório dentro do diretório (padrão estimativa.md)")
    p.set_defaults(func=_estimar)

    p = sub.add_parser("validar-lexico", help="confere o formato de um léxico")
    p.add_argument("arquivo")
    p.set_defaults(func=_validar_lexico)

    p = sub.add_parser("validar-config", help="confere a configuração: fontes, estratos, níveis")
    p.add_argument("arquivo")
    p.set_defaults(func=_validar_config)

    p = sub.add_parser("sondar", help="mede o tamanho de cada prefixo do Wayback (rede)")
    p.add_argument("--config", required=True)
    p.add_argument("--fonte", action="append")
    p.set_defaults(func=_sondar)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verboso else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.func(args)
    except (OSError, ValueError) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return rodada.ERRO
