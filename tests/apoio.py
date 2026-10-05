"""Constantes e atalhos compartilhados pelos testes de rodada."""

from datetime import date

from aletheia import config, fontes, lexico, rodada

FEED = "https://jornal.exemplo.br/feed"
BASE = "https://jornal.exemplo.br/2026/10"


def _rodar(caminho, rede, **kw):
    c = config.carregar(caminho)
    casador = lexico.Casador(lexico.carregar(c.lexico))
    instancias = [fontes.construir(f, rede) for f in c.fontes]
    return c, rodada.rodar(c, instancias, casador, hoje=date(2026, 10, 4), **kw)
