from datetime import date

import pytest

from aletheia import fontes
from aletheia.contrato import Fonte, Referencia
from aletheia.fontes.rss import Rss, ler_feed

FEED = "https://jornal.exemplo.br/feed"


def _rss(rede, **cfg):
    return fontes.construir({"tipo": "rss", "id": "rss:jornal", "url": FEED, **cfg}, rede)


def test_adaptadores_cumprem_o_contrato():
    for classe in fontes.TIPOS.values():
        for nome in ("listar", "baixar", "sentinela", "de_config"):
            assert callable(getattr(classe, nome))
        assert isinstance(classe.respeita_robots, bool)
    assert isinstance(Rss("x", FEED, cliente=None), Fonte)
    assert set(fontes.TIPOS) == {
        "rss", "wayback", "openalex", "gdelt", "crossref", "ia", "topico", "wikipedia", "lista"
    }  # fmt: skip


def test_tipo_desconhecido_e_recusado():
    with pytest.raises(ValueError, match="desconhecido"):
        fontes.construir({"tipo": "gopher", "id": "x"})


def test_rss_e_atom(fixtures):
    refs = list(ler_feed((fixtures / "rss" / "feed.xml").read_bytes(), "rss:j"))
    assert [r.id_na_fonte for r in refs] == [
        "jornal-1001",
        "jornal-1002",
        "jornal-1003",
        "jornal-0900",
    ]
    assert refs[0].publicado_em == date(2026, 10, 2)
    atom = list(ler_feed((fixtures / "rss" / "atom.xml").read_bytes(), "rss:r"))
    assert len(atom) == 1  # a entrada sem link é ignorada
    assert atom[0].url == "https://repositorio.exemplo.br/handle/123/456"
    assert atom[0].publicado_em == date(2026, 9, 30)


def test_rss_lista_desde_a_data(rede, fixtures):
    rede.responder(FEED, fixtures / "rss" / "feed.xml")
    refs = list(_rss(rede).listar(date(2026, 9, 1)))
    assert "jornal-0900" not in [r.id_na_fonte for r in refs]
    assert len(refs) == 3


def test_rss_baixa_a_pagina_e_nao_o_resumo(rede, fixtures):
    url = "https://jornal.exemplo.br/2026/10/carandiru-34-anos"
    rede.responder(url, fixtures / "rss" / "materia-carandiru.html")
    fonte = _rss(rede)
    ref = Referencia("rss:jornal", "jornal-1001", url, "Massacre do Carandiru: 34 anos depois")
    doc = fonte.baixar(ref)
    assert "Pavilhão 9" in doc.texto
    assert "Resumo curto" not in doc.texto
    assert doc.destaques["manchete"] == ref.titulo
    assert doc.destaques["linha_fina"].startswith("Familiares")
    assert len(doc.hash_texto) == 64
    assert fonte.sentinela(doc)


def test_rss_sentinela_reprova_pagina_de_erro_com_200(rede, fixtures):
    url = "https://jornal.exemplo.br/2026/10/sumiu"
    rede.responder(url, fixtures / "rss" / "erro-200.html")
    fonte = _rss(rede, minimo_caracteres=50)
    doc = fonte.baixar(Referencia("rss:jornal", "jornal-1003", url))
    assert not fonte.sentinela(doc)


def test_rss_sentinela_reprova_texto_curto(rede, fixtures):
    url = "https://jornal.exemplo.br/2026/10/sumiu"
    rede.responder(url, "<p>Carandiru</p>")
    fonte = _rss(rede)
    assert not fonte.sentinela(fonte.baixar(Referencia("rss:jornal", "x", url)))
