"""Canais: wayback fatiado, topico, wikipedia, openalex, crossref, gdelt, ia, lista."""

import json
from datetime import date
from urllib.parse import parse_qs, urlsplit

from aletheia import arquivo, fontes
from aletheia.fontes import crossref, gdelt, ia, openalex, topico, wayback, wikipedia


def _query(url):
    return parse_qs(urlsplit(url).query)


def _cdx(rede):
    return [p for p in rede.pedidos if p.url.startswith(wayback.CDX)]


# --- wayback -----------------------------------------------------------------------


def _wayback(rede, **cfg):
    base = {"tipo": "wayback", "id": "wayback:jornal", "dominio": "jornal.exemplo.br"}
    fonte = fontes.construir({**base, **cfg}, rede)
    fonte.hoje = lambda: date(2026, 10, 4)
    return fonte


def test_wayback_dominio_inteiro_pagina_pelo_resume_key(rede, fixtures):
    rede.responder(wayback.CDX, fixtures / "wayback" / "cdx-p1.json")
    rede.responder(wayback.CDX, fixtures / "wayback" / "cdx-p2.json")
    refs = list(_wayback(rede).listar(date(1996, 1, 1), {}))

    assert len(refs) == 3
    primeira = refs[0]
    assert (
        primeira.id_na_fonte
        == "http://www1.jornal.exemplo.br/fsp/cotidian/carandiru-ff02109912.htm"
    )
    assert primeira.url == f"{wayback.ARQUIVO}/19990301120000id_/{primeira.id_na_fonte}"
    assert primeira.publicado_em == date(1999, 3, 1)  # data da captura
    assert primeira.dados["snapshot"] == primeira.url

    q1, q2 = (_query(p.url) for p in rede.pedidos)
    assert q1["filter"] == ["original:(?i).*carandiru.*", "statuscode:200", "mimetype:text/html"]
    assert q1["matchType"] == ["domain"] and q1["collapse"] == ["urlkey"]
    assert q1["from"] == ["19960101"] and "to" not in q1  # fatia "tudo": uma consulta só
    assert "resumeKey" not in q1
    assert q2["resumeKey"] == ["br,exemplo,jornal)/carandiru-10-anos.shtml 20021002080000"]
    assert "robots.txt" not in " ".join(rede.urls())


def test_wayback_fatiado_por_prefixo_e_ano_grava_progresso(rede, fixtures):
    rede.responder(wayback.CDX, fixtures / "wayback" / "cdx-p2.json")
    fonte = _wayback(rede, dominio=None, prefixos=["www1.jornal.exemplo.br/cotidiano/"])
    progresso = {}
    refs = list(fonte.listar(date(2024, 6, 1), progresso))

    consultas = [_query(p.url) for p in _cdx(rede)]
    assert [(q["from"][0], q.get("to", [None])[0]) for q in consultas] == [
        ("20240601", "20241231"),
        ("20250101", "20251231"),
        ("20260101", None),  # ano corrente: aberto
    ]
    assert all(q["matchType"] == ["prefix"] for q in consultas)
    assert all(q["url"] == ["www1.jornal.exemplo.br/cotidiano/"] for q in consultas)
    assert len(refs) == 3
    # Só os anos fechados são dados por concluídos.
    assert progresso["concluidas"] == [
        "www1.jornal.exemplo.br/cotidiano/|2024",
        "www1.jornal.exemplo.br/cotidiano/|2025",
    ]
    assert fonte.listagem_incompleta is None

    # Rodada seguinte: pula o que já concluiu.
    rede.pedidos.clear()
    list(fonte.listar(date(2024, 6, 1), progresso))
    assert len(_cdx(rede)) == 1
    assert _query(_cdx(rede)[0].url)["from"] == ["20260101"]


def test_wayback_limite_de_fatias_por_rodada_deixa_o_resto_para_a_proxima(rede, fixtures):
    rede.responder(wayback.CDX, fixtures / "wayback" / "cdx-p2.json")
    fonte = _wayback(rede, dominio=None, prefixos=["a.br/x/", "a.br/y/"], fatias_por_rodada=2)
    progresso = {}
    list(fonte.listar(date(2025, 1, 1), progresso))
    assert len(_cdx(rede)) == 2
    assert progresso["concluidas"] == ["a.br/x/|2025"]  # 2026 é aberto; a.br/y/ nem começou
    assert "2 fatia(s)" in fonte.listagem_incompleta


def test_wayback_recusa_config_sem_prefixo_ou_fatia_invalida(rede):
    import pytest

    with pytest.raises(ValueError, match="prefixos"):
        fontes.construir({"tipo": "wayback", "id": "wayback:x"}, rede)
    with pytest.raises(ValueError, match="fatia"):
        fontes.construir(
            {"tipo": "wayback", "id": "wayback:x", "dominio": "a.br", "fatia": "mes"}, rede
        )


def test_wayback_baixa_a_copia_e_reprova_nao_arquivada(rede, fixtures):
    fonte = _wayback(rede)
    rede.responder(wayback.CDX, fixtures / "wayback" / "cdx-p2.json")
    (ref,) = list(fonte.listar(date(1996, 1, 1), {}))
    rede.responder(ref.url, fixtures / "wayback" / "captura.html")
    doc = fonte.baixar(ref)
    assert doc.destaques["manchete"] == "Carandiru, dez anos depois"
    assert "Pavilhão 9" in doc.texto
    assert fonte.sentinela(doc)

    rede.rotas[ref.url] = []
    rede.responder(ref.url, fixtures / "wayback" / "nao-arquivada.html")
    fonte.minimo_caracteres = 10
    assert not fonte.sentinela(fonte.baixar(ref))


def test_arquivo_resolve_url_exata(rede):
    rede.responder(
        arquivo.CDX,
        json.dumps([["timestamp", "original"], ["20200101000000", "http://x.br/a"]]),
    )
    ts, url = arquivo.Arquivo(transporte=rede).resolver("https://www.x.br/a?utm_source=z")
    assert ts == "20200101000000"
    assert url == f"{arquivo.ARQUIVO}/20200101000000id_/http://x.br/a"
    q = _query(rede.pedidos[-1].url)
    assert q["matchType"] == ["exact"] and q["limit"] == ["-1"]

    rede.rotas[arquivo.CDX] = []
    rede.responder(arquivo.CDX, "[]")
    assert arquivo.Arquivo(transporte=rede).resolver("https://x.br/nunca") is None


# --- topico ------------------------------------------------------------------------


def test_topico_segue_a_paginacao_e_filtra_navegacao(rede, fixtures):
    base = "https://ponte.org/tag/carandiru/"
    rede.responder(base, fixtures / "topico" / "pagina1.html")
    rede.responder(f"{base}page/2/", fixtures / "topico" / "pagina2.html")
    # page/3/ não tem rota: 404 encerra a paginação.
    fonte = fontes.construir({"tipo": "topico", "id": "topico:ponte", "url": base}, rede)
    refs = list(fonte.listar(date(1996, 1, 1)))
    assert [r.url for r in refs] == [
        "https://ponte.org/2021/10/trinta-anos-sem-justica-carandiru/",
        "https://ponte.org/2022/10/familiares-pedem-memorial/",
        "https://www.ponte.org/2023/02/juri-remarcado/",
        "https://ponte.org/2019/10/o-que-mudou-no-sistema-prisional/",
    ]
    assert refs[0].dados["via"] == base
    assert refs[0].id_na_fonte == "ponte.org/2021/10/trinta-anos-sem-justica-carandiru"
    assert rede.urls()[0] == "https://ponte.org/robots.txt"


def test_topico_le_versoes_arquivadas_da_propria_pagina(rede, fixtures):
    base = "https://ponte.org/tag/carandiru/"
    captura = f"{arquivo.ARQUIVO}/20200101000000id_/{base}"
    rede.responder(arquivo.CDX, json.dumps([["timestamp", "original"], ["20200101000000", base]]))
    rede.responder(captura, fixtures / "topico" / "pagina2.html")
    fonte = fontes.construir(
        {"tipo": "topico", "id": "topico:ponte", "url": base, "arquivadas": True, "max_paginas": 0},
        rede,
    )
    refs = list(fonte.listar(date(2019, 1, 1)))
    assert [r.url for r in refs] == [
        "https://ponte.org/2023/02/juri-remarcado/",
        "https://ponte.org/2019/10/o-que-mudou-no-sistema-prisional/",
    ]
    assert refs[0].dados["via"] == captura
    assert _query([p for p in rede.pedidos if p.url.startswith(arquivo.CDX)][0].url)[
        "collapse"
    ] == ["timestamp:4"]


def test_extrair_links_resolve_relativos_dentro_de_captura(fixtures):
    html = (fixtures / "topico" / "pagina2.html").read_text()
    captura = f"{arquivo.ARQUIVO}/2020id_/https://ponte.org/tag/carandiru/"
    links = topico.extrair_links(html, captura, "ponte.org")
    assert links[0] == "https://ponte.org/2023/02/juri-remarcado/"


def test_topico_paginacao_por_query():
    fonte = topico.Topico(
        "topico:x", "https://agencia.br/tags/carandiru", None, paginacao="?page={n}"
    )
    assert fonte._pagina(1) == "https://agencia.br/tags/carandiru"
    assert fonte._pagina(2) == "https://agencia.br/tags/carandiru?page=2"
    assert fonte.dominio == "agencia.br"
    assert topico.Topico("t", "https://www.ebc.com.br/x", None).dominio == "ebc.com.br"


# --- wikipedia ---------------------------------------------------------------------


def test_wikipedia_lista_links_externos_com_continue(rede, fixtures):
    api = "https://pt.wikipedia.org/w/api.php"
    rede.responder(api, fixtures / "wikipedia" / "extlinks-p1.json")
    rede.responder(api, fixtures / "wikipedia" / "extlinks-p2.json")
    cfg = {
        "tipo": "wikipedia",
        "id": "wikipedia:pt",
        "idioma": "pt",
        "titulos": ["Massacre_do_Carandiru"],
    }
    fonte = fontes.construir(cfg, rede)
    refs = list(fonte.listar(date(1996, 1, 1)))
    urls = [r.url for r in refs]
    assert urls == [
        "https://g1.globo.com/sp/sao-paulo/noticia/2016/09/massacre-do-carandiru.html",
        "https://web.archive.org/web/20101002000000/http://www.jornal.exemplo.br/carandiru-10-anos.shtml",
        "http://dhnet.org.br/dados/relatorios/carandiru.html",
    ]  # ftp fora; o g1 com www. é o mesmo documento e não repete
    assert refs[1].dados["snapshot"] == refs[1].url
    assert refs[0].dados["via"] == "pt.wikipedia.org/wiki/Massacre_do_Carandiru"
    q1, q2 = (_query(p.url) for p in rede.pedidos)
    assert q1["prop"] == ["extlinks"] and "eloffset" not in q1
    assert q2["eloffset"] == ["2"]
    assert isinstance(fonte, wikipedia.Wikipedia)


# --- openalex ----------------------------------------------------------------------


def test_openalex_cursor_resumo_e_chave(rede, fixtures, monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "chave-de-teste")
    rede.responder(openalex.URL, fixtures / "openalex" / "p1.json")
    rede.responder(openalex.URL, fixtures / "openalex" / "p2.json")
    cfg = {"tipo": "openalex", "id": "openalex:carandiru", "busca": "carandiru"}
    fonte = fontes.construir(cfg, rede)
    artigo, dissertacao = list(fonte.listar(date(2026, 1, 1)))

    q1, q2 = (_query(p.url) for p in rede.pedidos)
    assert q1["cursor"] == ["*"] and q2["cursor"] == ["Ij1hYmMi"]
    assert q1["filter"] == ["from_publication_date:2026-01-01"]
    assert q1["api_key"] == ["chave-de-teste"]
    assert not any("mailto" in p.url for p in rede.pedidos)

    assert artigo.url == "https://doi.org/10.0000/exemplo.1"
    assert dissertacao.url == "https://repositorio.exemplo.br/handle/1"  # sem DOI
    doc = fonte.baixar(artigo)
    assert "Este artigo analisa a memória do massacre de 1992." in doc.texto
    assert doc.destaques["titulo"].startswith("Memória e violência de Estado")
    assert fonte.sentinela(doc)


def test_resumo_invertido_vazio():
    assert openalex.resumo(None) == ""
    assert openalex.resumo({"b": [1], "a": [0, 2]}) == "a b a"


# --- crossref ----------------------------------------------------------------------


def test_crossref_cursor_doi_e_resumo_jats(rede, fixtures, monkeypatch):
    monkeypatch.delenv("CROSSREF_MAILTO", raising=False)
    rede.responder(crossref.URL, fixtures / "crossref" / "p1.json")
    rede.responder(crossref.URL, fixtures / "crossref" / "p2.json")
    cfg = {"tipo": "crossref", "id": "crossref:carandiru", "busca": "carandiru"}
    fonte = fontes.construir(cfg, rede)
    (obra,) = list(fonte.listar(date(2019, 1, 1)))  # a sem DOI é ignorada

    q1, q2 = (_query(p.url) for p in rede.pedidos)
    assert q1["cursor"] == ["*"] and q2["cursor"] == ["cursor-2"]
    assert q1["filter"] == ["from-pub-date:2019-01-01"]
    assert "mailto" not in q1
    assert obra.url == "https://doi.org/10.1000/Exemplo.1"
    assert obra.id_na_fonte == "10.1000/exemplo.1"
    assert obra.publicado_em == date(2020, 5, 1)
    doc = fonte.baixar(obra)
    assert "Resumo" not in doc.texto or "<jats" not in doc.texto
    assert "Este artigo analisa a memória do massacre de 1992." in doc.texto
    assert doc.destaques["titulo"].startswith("Memória e violência")
    assert fonte.sentinela(doc)


def test_crossref_data_e_resumo():
    assert crossref._data({"date-parts": [[2021]]}) == date(2021, 1, 1)
    assert crossref._data({"date-parts": [[None]]}) is None
    assert crossref._data(None) is None
    assert crossref.limpar_resumo("<jats:p>a  b</jats:p>") == "a b"


# --- internet archive --------------------------------------------------------------


def test_ia_busca_paginada_e_item_sem_rede(rede, fixtures):
    rede.responder(ia.URL, fixtures / "ia" / "p1.json")
    fonte = fontes.construir({"tipo": "ia", "id": "ia:carandiru", "busca": "carandiru"}, rede)
    (ref,) = list(fonte.listar(date(2010, 1, 1)))
    q = _query(rede.pedidos[0].url)
    assert q["q"] == ["(carandiru) AND publicdate:[2010-01-01 TO null]"]
    assert q["rows"] == ["100"] and q["page"] == ["1"]
    assert ref.url == "https://archive.org/details/carandiru-relatorio-1993"
    assert ref.publicado_em == date(2015, 3, 1)
    doc = fonte.baixar(ref)
    assert "111 presos" in doc.texto and "Tipo: texts" in doc.texto
    assert fonte.sentinela(doc)
    assert len(rede.pedidos) == 1  # menos de uma página cheia: sem segunda consulta


# --- gdelt -------------------------------------------------------------------------


def test_gdelt_um_dia_por_vez_dentro_da_janela(rede, fixtures):
    rede.responder(gdelt.URL, fixtures / "gdelt" / "dia.json")
    cfg = {"tipo": "gdelt", "id": "gdelt:carandiru", "busca": "carandiru"}
    fonte = fontes.construir(cfg, rede)
    fonte.hoje = lambda: date(2026, 10, 4)
    refs = list(fonte.listar(date(2020, 1, 1)))  # anterior à janela: cortado

    consultas = [_query(p.url) for p in rede.pedidos if p.url.startswith(gdelt.URL)]
    assert len(consultas) == 91  # 90 dias de janela, mais hoje
    assert consultas[0]["startdatetime"] == ["20260706000000"]
    assert consultas[0]["enddatetime"] == ["20260707000000"]
    assert fonte.desde_efetivo == date(2026, 7, 6)  # vai para o relatório da rodada
    assert {r.id_na_fonte for r in refs} == {
        "https://noticias.exemplo.com/2026/10/02/carandiru-34-anos",
        "https://news.example.org/brazil-prison-massacre",
    }
    assert refs[0].publicado_em == date(2026, 10, 2)


def test_gdelt_dia_cheio_e_repartido_em_seis_horas(rede):
    cheio = {
        "articles": [
            {"url": f"https://x.br/{i}", "seendate": "20261002T000000Z"} for i in range(250)
        ]
    }
    rede.responder(gdelt.URL, json.dumps(cheio))
    rede.responder(gdelt.URL, json.dumps({"articles": []}))
    cfg = {"tipo": "gdelt", "id": "gdelt:x", "busca": "x"}
    fonte = fontes.construir(cfg, rede)
    fonte.hoje = lambda: date(2026, 10, 2)
    list(fonte.listar(date(2026, 10, 2)))
    api = [p for p in rede.pedidos if p.url.startswith(gdelt.URL)]
    faixas = [_query(p.url)["startdatetime"][0] for p in api][1:]
    assert faixas == ["20261002000000", "20261002060000", "20261002120000", "20261002180000"]


# --- lista -------------------------------------------------------------------------


def test_lista_le_csv_relativo_ao_config(rede, tmp_path, fixtures):
    (tmp_path / "listas").mkdir()
    (tmp_path / "listas" / "hemeroteca.csv").write_text(
        "url,titulo,publicado_em\n"
        "https://memoria.bn.br/doc/1,Jornal do Brasil 3/10/1992,1992-10-03\n"
        "https://memoria.bn.br/doc/2,,data-ruim\n"
        ",sem url,\n",
        encoding="utf-8",
    )
    cfg = {"tipo": "lista", "id": "lista:hemeroteca", "arquivo": "listas/hemeroteca.csv",
           "_diretorio_config": str(tmp_path)}  # fmt: skip
    fonte = fontes.construir(cfg, rede)
    refs = list(fonte.listar(date(1990, 1, 1)))
    assert [r.url for r in refs] == ["https://memoria.bn.br/doc/1", "https://memoria.bn.br/doc/2"]
    assert refs[0].publicado_em == date(1992, 10, 3) and refs[1].publicado_em is None
    assert refs[0].titulo == "Jornal do Brasil 3/10/1992"
    rede.responder("https://memoria.bn.br/doc/1", fixtures / "wayback" / "captura.html")
    assert fonte.sentinela(fonte.baixar(refs[0]))


# --- ajustes da primeira varredura real (ponte.org, 05/10/2026) --------------------


def test_wayback_exclui_ruido_de_endereco(rede):
    corpo = json.dumps([
        ["timestamp", "original", "statuscode", "mimetype", "digest"],
        ["20210101000000", "https://ponte.org/materia-carandiru/", "200", "text/html", "A"],
        ["20210101000000", "https://ponte.org/materia-carandiru/embed/", "200", "text/html", "B"],
        ["20210101000000", "https://ponte.org/materia-carandiru/feed/", "200", "text/html", "C"],
        ["20210101000000", "https://ponte.org/?s=Massacre+do+Carandiru", "200", "text/html", "D"],
        ["20210101000000", "https://ponte.org/tag/massacre-do-carandiru/page/2/", "200",
         "text/html", "E"],
        ["20210101000000", "https://ponte.org/outra-carandiru/?utm_source=x", "200",
         "text/html", "F"],
        ["20210101000000", "https://ponte.org/foto-carandiru.jpg", "200", "text/html", "G"],
    ])  # fmt: skip
    rede.responder(wayback.CDX, corpo)
    refs = list(_wayback(rede).listar(date(2021, 1, 1), {}))
    assert [r.id_na_fonte for r in refs] == [
        "https://ponte.org/materia-carandiru/",
        "https://ponte.org/outra-carandiru/?utm_source=x",
    ]
    sem_filtro = _wayback(rede, excluir="")
    assert len(list(sem_filtro.listar(date(2021, 1, 1), {}))) == 7


def test_topico_bloqueado_por_robots_falha_nomeado_ou_le_so_o_arquivo(rede, fixtures):
    import pytest

    from aletheia.http import BloqueadoPorRobots

    base = "https://ponte.org/tag/carandiru/"
    rede.responder("https://ponte.org/robots.txt", "User-agent: *\nDisallow: /tag/\n")
    fonte = fontes.construir({"tipo": "topico", "id": "topico:ponte", "url": base}, rede)
    with pytest.raises(BloqueadoPorRobots):
        list(fonte.listar(date(2020, 1, 1)))

    captura = f"{arquivo.ARQUIVO}/20200101000000id_/{base}"
    rede.responder(arquivo.CDX, json.dumps([["timestamp", "original"], ["20200101000000", base]]))
    rede.responder(captura, fixtures / "topico" / "pagina2.html")
    fonte = fontes.construir(
        {"tipo": "topico", "id": "topico:ponte", "url": base, "arquivadas": True}, rede
    )
    refs = list(fonte.listar(date(2020, 1, 1)))
    assert len(refs) == 2 and all(r.dados["via"] == captura for r in refs)


def test_wayback_corta_a_janela_para_o_inicio_do_arquivo(rede, fixtures):
    rede.responder(wayback.CDX, fixtures / "wayback" / "cdx-p2.json")
    fonte = _wayback(rede, dominio=None, prefixos=["a.br/"])
    fonte.hoje = lambda: date(1997, 6, 1)
    list(fonte.listar(date(1992, 10, 2), {}))
    consultas = [_query(p.url) for p in _cdx(rede)]
    assert [q["from"][0] for q in consultas] == ["19960101", "19970101"]  # nada de 1992-1995
    assert fonte.desde_efetivo == wayback.INICIO_DO_ARQUIVO
