import json

import pytest

from aletheia import config


def _base(**extra):
    return {
        "lexico": "lexico.json",
        "fontes": [{"tipo": "rss", "id": "rss:x", "url": "https://x/feed", "estrato": "imprensa"}],
        **extra,
    }


def test_config_sa():
    assert config.validar(_base()) == []


def test_estrato_obrigatorio_e_conhecido():
    dados = _base()
    del dados["fontes"][0]["estrato"]
    assert any("sem estrato" in p for p in config.validar(dados))
    dados["fontes"][0]["estrato"] = "jornais"
    assert any("estrato desconhecido" in p for p in config.validar(dados))


def test_prefixo_do_id_e_o_tipo():
    dados = _base()
    dados["fontes"][0]["id"] = "jornal:x"
    assert any("prefixo do id" in p for p in config.validar(dados))


def test_niveis_coerentes():
    dados = _base(catalogo={"nivel_minimo": 2}, vistas={"nivel_minimo": 3})
    assert any("vistas.nivel_minimo" in p for p in config.validar(dados))
    dados = _base(catalogo={"nivel_minimo": 7})
    assert any("inteiro de 0 a 3" in p for p in config.validar(dados))


def test_desde_e_ids_repetidos():
    dados = _base(desde="05/10/2026")
    assert any("AAAA-MM-DD" in p for p in config.validar(dados))
    dados = _base()
    dados["fontes"].append(dict(dados["fontes"][0]))
    assert any("ids repetidos" in p for p in config.validar(dados))


def test_carregar_e_propriedades(tmp_path):
    caminho = tmp_path / "config.json"
    caminho.write_text(json.dumps(_base(
        diretorio=".", catalogo={"arquivo": "catalogo.csv"}, vistas={}, arquivo={"resolver": True}
    )))  # fmt: skip
    c = config.carregar(caminho)
    assert c.catalogo_csv == tmp_path.resolve() / "catalogo.csv" and c.catalogo_nivel == 3
    assert c.vistas_csv == tmp_path.resolve() / "vistas.csv" and c.vistas_nivel == 2
    assert c.resolver_arquivo is True
    assert c.estrato_de("rss:x") == "imprensa" and c.estrato_de("nada") == "geral"
    with pytest.raises(ValueError, match="nenhuma fonte"):
        caminho.write_text(json.dumps({"lexico": "l", "fontes": []}))
        config.carregar(caminho)


def test_config_real_do_repositorio_e_valida():
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    dados = json.loads((raiz / "config.json").read_text(encoding="utf-8"))
    assert config.validar(dados) == []
