"""Catálogo CSV v2 (um documento por linha), vistas e migração do formato antigo."""

import csv
import json
from datetime import date

from aletheia import cli, config, fontes, rodada
from aletheia.contrato import Referencia
from aletheia.saidas import catalogo, vistas
from aletheia.triagem import Resultado
from aletheia.url import identidade
from tests.apoio import _rodar


def _linhas(caminho):
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def test_catalogo_v2_so_com_o_que_passou(cfg, rede_jornal, tmp_path):
    c, r = _rodar(cfg, rede_jornal)
    caminho = tmp_path / "catalogo.csv"
    assert catalogo.atualizar(r, caminho, estrato_de=lambda f: "imprensa") == 1
    (linha,) = _linhas(caminho)
    assert tuple(linha) == catalogo.COLUNAS
    assert linha["url"] == "https://jornal.exemplo.br/2026/10/carandiru-34-anos"
    assert linha["id"] == identidade(linha["url"]) == catalogo.id_da_url(linha["url"])
    assert linha["dominio"] == "jornal.exemplo.br"
    assert linha["estrato"] == "imprensa"
    assert linha["titulo"].startswith("Massacre do Carandiru: 34 anos depois")
    assert linha["publicado_em"] == "2026-10-02"
    assert linha["nivel"] == "3"
    assert linha["identificadores"].split(";")[0] == "massacre-do-carandiru"
    assert "evento" in linha["categorias"].split(";")
    assert linha["primeira_rodada"] == r.id
    assert linha["lexico_versao"] == "2026-10-04"
    assert linha["snapshot"] == "" and linha["capturado_em"] == ""


def test_catalogo_e_cumulativo_e_guarda_o_registro_inicial(cfg, rede_jornal, tmp_path):
    _, r = _rodar(cfg, rede_jornal)
    caminho = tmp_path / "catalogo.csv"
    catalogo.atualizar(r, caminho)
    antes = caminho.read_text(encoding="utf-8")
    r.linhas[0].resultado.chaves = ["outra-chave"]
    assert catalogo.atualizar(r, caminho) == 0
    assert caminho.read_text(encoding="utf-8") == antes


def test_mesma_materia_arquivada_e_viva_e_uma_linha(tmp_path):
    r = rodada.Rodada("20261005T000000Z", "lex", "v1", "rodar", "x")
    viva = Referencia(
        "gdelt:c", "a", "https://www.jornal.br/2016/carandiru.shtml?utm_source=t", "Título"
    )
    arquivada = Referencia(
        "wayback:j", "http://jornal.br/2016/carandiru.shtml",
        "https://web.archive.org/web/20160927090000id_/http://jornal.br/2016/carandiru.shtml",
        dados={"snapshot": "https://web.archive.org/web/20160927090000id_/http://jornal.br/2016/carandiru.shtml"},
    )  # fmt: skip
    for ref in (viva, arquivada):
        r.linhas.append(rodada.Linha(ref, rodada.TRIADO, Resultado(3, "aceito", ["k"], ["evento"]),
                                     hash_texto="h", snapshot=rodada._snapshot(ref)))  # fmt: skip
    caminho = tmp_path / "catalogo.csv"
    assert catalogo.atualizar(r, caminho) == 1
    (linha,) = _linhas(caminho)
    assert linha["url"] == "https://www.jornal.br/2016/carandiru.shtml?utm_source=t"  # a primeira
    assert linha["snapshot"] == ""  # a viva não trouxe; completar_snapshots resolve depois

    n = catalogo.completar_snapshots(
        caminho,
        lambda url: ("20160927090000", f"https://web.archive.org/web/20160927090000id_/{url}"),
    )
    assert n == 1
    (linha,) = _linhas(caminho)
    assert linha["capturado_em"] == "20160927090000" and "id_/" in linha["snapshot"]
    assert catalogo.completar_snapshots(caminho, lambda url: None) == 0


def test_snapshot_do_wayback_vai_para_o_catalogo(tmp_path):
    r = rodada.Rodada("20261005T000000Z", "lex", "v1", "rodar", "x")
    snap = "https://web.archive.org/web/19990301120000id_/http://www1.j.br/fsp/carandiru.htm"
    ref = Referencia(
        "wayback:j", "http://www1.j.br/fsp/carandiru.htm", snap, dados={"snapshot": snap}
    )
    r.linhas.append(rodada.Linha(ref, rodada.TRIADO, Resultado(3, "aceito"), snapshot=snap))
    catalogo.atualizar(r, tmp_path / "c.csv")
    (linha,) = _linhas(tmp_path / "c.csv")
    assert linha["url"] == "http://www1.j.br/fsp/carandiru.htm"
    assert linha["snapshot"] == snap and linha["capturado_em"] == "19990301120000"


def test_migra_o_formato_antigo_de_tres_colunas(tmp_path):
    caminho = tmp_path / "catalogo.csv"
    caminho.write_text(
        "id,url,identificadores\n"
        "abcd,https://web.archive.org/web/2016id_/http://www.j.br/x,massacre-do-carandiru\n",
        encoding="utf-8",
    )
    r = rodada.Rodada("20261005T000000Z", "lex", "v1", "rodar", "x")
    assert catalogo.atualizar(r, caminho) == 0
    (linha,) = _linhas(caminho)
    assert tuple(linha) == catalogo.COLUNAS
    assert linha["url"] == "http://www.j.br/x" and linha["id"] == identidade("http://www.j.br/x")
    assert linha["dominio"] == "j.br" and linha["identificadores"] == "massacre-do-carandiru"


def test_nivel_minimo(cfg, rede_jornal, tmp_path):
    _, r = _rodar(cfg, rede_jornal)
    assert catalogo.atualizar(r, tmp_path / "a.csv", nivel_minimo=0) == 2
    assert catalogo.atualizar(r, tmp_path / "b.csv", nivel_minimo=3) == 1


def test_vistas_uma_linha_por_observacao(cfg, rede_jornal, tmp_path):
    _, r = _rodar(cfg, rede_jornal)
    caminho = tmp_path / "vistas.csv"
    assert vistas.acrescentar(r, caminho) == 1  # só nível >= 2
    assert vistas.acrescentar(r, caminho) == 1  # acrescenta de novo: é observação, não documento
    linhas = _linhas(caminho)
    assert len(linhas) == 2 and tuple(linhas[0]) == vistas.COLUNAS
    assert linhas[0]["canal"] == "rss" and linhas[0]["fonte"] == "rss:jornal"
    assert linhas[0]["id"] == identidade(linhas[0]["url"])
    assert linhas[0]["rodada"] == r.id and linhas[0]["nivel"] == "3"
    assert linhas[0]["publicado_em"] == "2026-10-02" and len(linhas[0]["hash_texto"]) == 64


def test_sem_guardar_texto_nada_vai_para_o_corpus(cfg, rede_jornal):
    dados = json.loads(cfg.read_text())
    dados["guardar_texto"] = False
    cfg.write_text(json.dumps(dados))
    c, r = _rodar(cfg, rede_jornal)
    assert not c.corpus.exists()
    assert [linha.nivel for linha in r.linhas if linha.nivel is not None] == [3, 0]
    assert all(linha.corpus is None for linha in r.linhas)


def test_cli_atualiza_catalogo_e_vistas(cfg, monkeypatch, rede_jornal, capsys):
    dados = json.loads(cfg.read_text())
    dados["catalogo"] = {"arquivo": "catalogo.csv"}
    dados["vistas"] = {"arquivo": "vistas.csv"}
    dados["fontes"][0]["estrato"] = "imprensa"
    cfg.write_text(json.dumps(dados))
    construir = fontes.construir
    monkeypatch.setattr(fontes, "construir", lambda f: construir(f, rede_jornal))
    assert cli.main(["rodar", "--config", str(cfg)]) == 3
    c = config.carregar(cfg)
    assert len(_linhas(c.catalogo_csv)) == 1
    assert _linhas(c.catalogo_csv)[0]["estrato"] == "imprensa"
    assert len(_linhas(c.vistas_csv)) == 1
    saida = capsys.readouterr().out
    assert "catálogo: 1 documentos novos" in saida and "vistas: 1 observações" in saida
    assert cli.main(["validar-config", str(cfg)]) == 0


def test_date_import_usado():
    assert date(2026, 10, 5).isoformat() == "2026-10-05"


def test_titulo_vem_da_manchete_quando_a_referencia_so_tem_url():
    r = rodada.Rodada("20261005T000000Z", "lex", "v1", "rodar", "x")
    ref = Referencia(
        "wayback:j",
        "http://j.br/x",
        "https://web.archive.org/web/1id_/http://j.br/x",
        "http://j.br/x",
    )
    r.linhas.append(
        rodada.Linha(
            ref, rodada.TRIADO, Resultado(3, "aceito"), manchete="Carandiru, dez anos depois"
        )
    )
    assert r.linhas[0].titulo == "Carandiru, dez anos depois"
    assert r.linhas[0].como_dict()["titulo"] == "Carandiru, dez anos depois"
    ref_feed = Referencia("rss:j", "a", "https://j.br/a", "Manchete do feed")
    com_titulo = rodada.Linha(ref_feed, rodada.TRIADO, Resultado(3, "aceito"), manchete="Outra")
    assert com_titulo.titulo == "Manchete do feed"
    assert rodada.Linha(Referencia("x", "a", "https://j.br/a"), rodada.TRIADO).titulo is None


def test_mesmo_texto_em_duas_urls_e_um_documento(tmp_path):
    r = rodada.Rodada("20261005T000000Z", "lex", "v1", "rodar", "x")
    for url in ("https://j.br/materia/", "https://j.br/materia/embed/"):
        r.linhas.append(rodada.Linha(Referencia("wayback:j", url, url), rodada.TRIADO,
                                     Resultado(3, "aceito"), hash_texto="MESMO"))  # fmt: skip
    assert catalogo.atualizar(r, tmp_path / "c.csv") == 1
    r2 = rodada.Rodada("20261006T000000Z", "lex", "v1", "rodar", "x")
    r2.linhas.append(rodada.Linha(Referencia("gdelt:c", "z", "https://outro.br/z"), rodada.TRIADO,
                                  Resultado(3, "aceito"), hash_texto="MESMO"))  # fmt: skip
    assert catalogo.atualizar(r2, tmp_path / "c.csv") == 0
