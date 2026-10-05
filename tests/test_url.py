import pytest

from aletheia.url import dominio, identidade, normalizar, original_do_wayback


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://www.Jornal.br/a/b/", "jornal.br/a/b"),
        ("http://jornal.br/a/b?utm_source=x&id=3", "jornal.br/a/b?id=3"),
        ("https://web.archive.org/web/20021002080000id_/http://www.jornal.br/a/b", "jornal.br/a/b"),
        ("https://web.archive.org/web/2002/https://jornal.br/a/b", "jornal.br/a/b"),
        (
            "http://www1.folha.uol.com.br:80/cotidiano/x.shtml",
            "www1.folha.uol.com.br/cotidiano/x.shtml",
        ),
        ("jornal.br", "jornal.br/"),
    ],
)
def test_normalizar(url, esperado):
    assert normalizar(url) == esperado


def test_mesma_materia_viva_e_arquivada_tem_o_mesmo_id():
    viva = "https://www.jornal.br/2016/carandiru.shtml?fbclid=abc"
    arquivada = (
        "https://web.archive.org/web/20160927090000id_/http://jornal.br/2016/carandiru.shtml"
    )
    assert identidade(viva) == identidade(arquivada)
    assert len(identidade(viva)) == 16
    assert dominio(arquivada) == "jornal.br"
    assert original_do_wayback(arquivada) == "http://jornal.br/2016/carandiru.shtml"
    assert original_do_wayback(viva) == viva
