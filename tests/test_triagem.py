from datetime import UTC, datetime

import pytest

from aletheia import lexico
from aletheia.captura import montar_documento
from aletheia.contrato import Referencia
from aletheia.triagem import recortar, triar

REF = Referencia(fonte="teste", id_na_fonte="1", url="https://exemplo.br/1")


@pytest.fixture
def casador(fixtures):
    return lexico.Casador(lexico.carregar(fixtures / "lexico-carandiru.json"))


def _doc(texto, **destaques):
    return montar_documento(
        REF, texto, destaques=destaques, agora=datetime(2026, 10, 4, tzinfo=UTC)
    )


def test_nivel_0_sem_termo(casador):
    r = triar(_doc("A prefeitura anunciou obras de drenagem."), casador)
    assert (r.nivel, r.motivo, r.trecho) == (0, "sem_termo", None)


def test_nivel_0_so_exclusao_sai_com_trecho(casador):
    r = triar(_doc("Sessão de cinema: Carandiru, o filme, com debate."), casador)
    assert (r.nivel, r.motivo) == (0, "so_exclusao")
    assert "o filme" in r.trecho


def test_nivel_1_termo_sem_contexto(casador):
    r = triar(_doc("O bairro do Carandiru ganhou uma feira de artesanato."), casador)
    assert (r.nivel, r.motivo, r.chaves) == (1, "sem_contexto", ["massacre-do-carandiru"])
    assert "Carandiru" in r.trecho


def test_nivel_2_termo_e_contexto_fora_do_destaque(casador):
    doc = _doc(
        "Seminário discute segurança pública. "
        "Entre os casos, o Carandiru, onde presos foram mortos.",
        manchete="Seminário discute segurança pública",
    )
    r = triar(doc, casador)
    assert (r.nivel, r.motivo, r.onde) == (2, "pede_juizo", "texto")


def test_nivel_3_termo_no_destaque(casador):
    doc = _doc(
        "Em 1992 a Polícia Militar invadiu o Pavilhão 9 da Casa de Detenção. Houve indulto.",
        manchete="Massacre do Carandiru: 34 anos",
    )
    r = triar(doc, casador)
    assert (r.nivel, r.motivo, r.onde) == (3, "aceito", "manchete")
    assert r.chaves == ["casa-de-detencao", "indulto"]
    assert r.categorias == ["lugar", "desdobramento-juridico"]
    assert r.pontuacao == 1.5
    assert r.trecho == "Massacre do Carandiru: 34 anos"


def test_recorte_marca_o_que_cortou():
    texto = "a" * 500 + "ALVO" + "b" * 500
    trecho = recortar(texto, 500, 504, raio=10)
    assert trecho == "…" + "a" * 10 + "ALVO" + "b" * 10 + "…"


def test_triagem_e_deterministica(casador):
    doc = _doc("Carandiru, 1992: presos mortos.", manchete="Carandiru")
    assert triar(doc, casador) == triar(doc, casador)
