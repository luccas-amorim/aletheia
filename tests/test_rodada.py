"""Rodada de ponta a ponta, sem rede: feed, páginas, sentinela, triagem, estado e saídas."""

import json
from datetime import date

import pytest

from aletheia import cli, config, estado, lexico, rodada, saidas
from aletheia.captura import Corpus
from aletheia.contrato import Referencia
from aletheia.fontes.rss import documento_html
from aletheia.http import Resposta
from tests.apoio import BASE, FEED, _rodar


def test_rodada_completa(cfg, rede_jornal):
    c, r = _rodar(cfg, rede_jornal)
    por_id = {linha.ref.id_na_fonte: linha for linha in r.linhas}

    assert set(por_id) == {"jornal-1001", "jornal-1002", "jornal-1003"}  # 0900 é anterior
    assert por_id["jornal-1001"].nivel == 3
    assert por_id["jornal-1001"].resultado.onde == "manchete"
    assert por_id["jornal-1002"].resultado.motivo == "sem_termo"
    assert por_id["jornal-1003"].situacao == rodada.SENTINELA
    assert r.codigo_saida == rodada.PEDE_LEITURA
    assert r.pede_leitura
    assert r.desde == {"rss:jornal": "2026-09-01"}

    # Corpus: só o íntegro tem nome canônico; o reprovado fica como .part.
    pasta = c.corpus / "rss_jornal"
    assert len(list(pasta.glob("*.json"))) == 2
    assert len(list(pasta.glob("*.json.part"))) == 1

    # Estado: o reprovado não é marcado como visto, para ser tentado de novo.
    memoria = estado.ler(c.estado, "rss:jornal")
    assert memoria.ultima_rodada == date(2026, 10, 4)
    assert set(memoria.vistos) == {"jornal-1001", "jornal-1002"}
    assert memoria.progresso == {}


def test_saidas(cfg, rede_jornal):
    c, r = _rodar(cfg, rede_jornal)
    pasta = saidas.escrever(r, c.saidas)
    aceitos = [json.loads(x) for x in (pasta / "aceitos.jsonl").read_text().splitlines()]
    assert len(aceitos) == 1
    item = aceitos[0]
    assert item["url"] == f"{BASE}/carandiru-34-anos"
    assert item["lexico"] == {"id": "carandiru-amostra", "versao": "2026-10-04"}
    assert item["chaves"][0] == "massacre-do-carandiru"
    assert "evento" in item["categorias"]
    assert item["hash_texto"] and item["capturado_em"]
    assert item["snapshot"] is None
    assert item["corpus"] == f"corpus/rss_jornal/{item['hash_texto']}.json"
    assert (c.diretorio / item["corpus"]).exists()
    assert (pasta / "pede-juizo.jsonl").read_text() == ""
    assert len((pasta / "itens.jsonl").read_text().splitlines()) == 3

    completo = (pasta / "relatorio-completo.md").read_text()
    resumo = (pasta / "relatorio-resumo.md").read_text()
    assert completo.startswith("# Alétheia: rodada")
    assert "Descartados no nível 0" in completo and "drenagem" in completo
    assert "drenagem" not in resumo
    assert "Falhas de captura ou de integridade (1)" in resumo
    meta = json.loads((pasta / "rodada.json").read_text())
    assert meta["contagens"]["situacao"] == {"reprovado_sentinela": 1, "triado": 2}
    assert meta["codigo_saida"] == 3 and meta["pede_leitura"] is True
    assert meta["incompletas"] == {}


def test_segunda_rodada_nao_rebaixa_o_que_ja_viu(cfg, rede_jornal):
    _rodar(cfg, rede_jornal)
    rede_jornal.pedidos.clear()
    _, r = _rodar(cfg, rede_jornal)
    baixadas = [u for u in rede_jornal.urls() if u.startswith(BASE)]
    # A janela agora começa em 02/10 e o item reprovado é de 01/10: só volta por ser pendente.
    assert r.desde == {"rss:jornal": "2026-10-02"}  # última rodada menos a margem
    assert baixadas == [f"{BASE}/sumiu"]


def test_pendente_e_resolvido_quando_a_pagina_volta(cfg, rede_jornal, fixtures):
    c, _ = _rodar(cfg, rede_jornal)
    memoria = estado.ler(c.estado, "rss:jornal")
    assert memoria.pendentes["jornal-1003"]["motivo"] == rodada.SENTINELA
    assert memoria.pendentes["jornal-1003"]["tentativas"] == 1

    rede_jornal.rotas[f"{BASE}/sumiu"] = []
    rede_jornal.responder(f"{BASE}/sumiu", fixtures / "rss" / "materia-carandiru.html")
    _, r = _rodar(cfg, rede_jornal)
    assert [linha.nivel for linha in r.linhas] == [3]
    memoria = estado.ler(c.estado, "rss:jornal")
    assert memoria.pendentes == {}
    assert "jornal-1003" in memoria.vistos


def test_pendente_nao_guarda_dados_grandes(cfg):
    memoria = estado.Estado("x")
    grande = Referencia("x", "1", "https://a.br/1", dados={"texto": "palavra " * 2000})
    pequena = Referencia(
        "x", "2", "https://a.br/2", dados={"snapshot": "https://web.archive.org/web/1id_/a"}
    )
    memoria.pendurar(grande, rodada.FALHA)
    memoria.pendurar(pequena, rodada.FALHA)
    assert memoria.pendentes["1"]["ref"]["dados"] is None
    assert memoria.pendentes["2"]["ref"]["dados"]["snapshot"].startswith("https://web.archive.org")


def test_sem_estado_rele_tudo_e_nao_grava(cfg, rede_jornal):
    c, _ = _rodar(cfg, rede_jornal, usar_estado=False)
    assert not estado.caminho(c.estado, "rss:jornal").exists()


def test_fonte_fora_do_ar_da_codigo_2_e_nao_avanca_a_data(cfg, rede):
    c, r = _rodar(cfg, rede)  # sem rota para o feed: 404
    assert r.codigo_saida == rodada.ERRO
    assert "rss:jornal" in r.falhas_de_fonte
    # O estado é gravado (vistos, pendentes, progresso), mas a data não avança.
    memoria = estado.ler(c.estado, "rss:jornal")
    assert memoria.ultima_rodada is None


class _FonteQueFalhaNoMeio:
    """Lista uma referência, anota progresso, e aí a rede cai."""

    id = "fake:meio"
    limite_por_minuto = 60
    respeita_robots = False
    usa_progresso = True

    def __init__(self, html: bytes) -> None:
        self.html = html

    def listar(self, desde, progresso):
        progresso["concluidas"] = ["a|2024"]
        snapshot = "https://web.archive.org/web/20261001id_/https://fake.br/um"
        yield Referencia(
            self.id, "um", "https://fake.br/um", "Carandiru: 34 anos", date(2026, 10, 1),
            {"snapshot": snapshot},
        )  # fmt: skip
        raise ConnectionError("caiu com api_key=SEGREDO na URL")

    def baixar(self, ref):
        return documento_html(ref, Resposta(200, ref.url, self.html, {}), ref.titulo)

    def sentinela(self, doc):
        return True


def test_listagem_que_falha_no_meio_aproveita_o_que_listou_e_grava_progresso(cfg, fixtures):
    c = config.carregar(cfg)
    casador = lexico.Casador(lexico.carregar(c.lexico))
    fonte = _FonteQueFalhaNoMeio((fixtures / "rss" / "materia-carandiru.html").read_bytes())
    r = rodada.rodar(c, [fonte], casador, hoje=date(2026, 10, 4))

    assert r.codigo_saida == rodada.ERRO
    assert "SEGREDO" not in r.falhas_de_fonte["fake:meio"]
    assert "api_key=<redigido>" in r.falhas_de_fonte["fake:meio"]
    assert [linha.nivel for linha in r.linhas] == [3]  # a referência listada foi triada
    assert r.linhas[0].snapshot.startswith("https://web.archive.org/web/20261001id_/")
    assert r.pede_leitura

    memoria = estado.ler(c.estado, "fake:meio")
    assert memoria.progresso == {"concluidas": ["a|2024"]}
    assert "um" in memoria.vistos
    assert memoria.ultima_rodada is None  # a janela seguinte volta a cobrir o período


class _FonteIncompleta(_FonteQueFalhaNoMeio):
    id = "fake:incompleta"
    listagem_incompleta = "3 fatia(s) ficaram para a próxima rodada"

    def listar(self, desde, progresso):
        yield Referencia(
            self.id, "um", "https://fake.br/um", "Carandiru: 34 anos", date(2026, 10, 1)
        )


def test_listagem_incompleta_nao_e_falha_mas_nao_avanca_a_data(cfg, fixtures):
    c = config.carregar(cfg)
    casador = lexico.Casador(lexico.carregar(c.lexico))
    fonte = _FonteIncompleta((fixtures / "rss" / "materia-carandiru.html").read_bytes())
    r = rodada.rodar(c, [fonte], casador, hoje=date(2026, 10, 4))
    assert r.falhas_de_fonte == {}
    assert r.incompletas == {"fake:incompleta": "3 fatia(s) ficaram para a próxima rodada"}
    assert r.codigo_saida == rodada.PEDE_LEITURA
    assert estado.ler(c.estado, "fake:incompleta").ultima_rodada is None
    pasta = saidas.escrever(r, c.saidas)
    assert "continuam na próxima rodada (1)" in (pasta / "relatorio-resumo.md").read_text()


def test_retriar_aplica_lexico_novo_sem_rede(cfg, rede_jornal, tmp_path):
    c, _ = _rodar(cfg, rede_jornal)
    novo = json.loads((tmp_path / "lexico.json").read_text())
    novo["versao"] = "2026-10-05"
    novo["termos"].append({"chave": "drenagem", "formas": ["drenagem"]})
    novo["contexto"]["exige_qualquer"].append("prefeitura")
    (tmp_path / "lexico.json").write_text(json.dumps(novo))

    r = rodada.retriar(c, lexico.Casador(lexico.carregar(c.lexico)))
    assert r.lexico_versao == "2026-10-05"
    niveis = sorted(linha.nivel for linha in r.linhas)
    assert niveis == [3, 3]


def test_cli_validar_e_rodar_sem_fonte(cfg, capsys, fixtures):
    assert cli.main(["validar-lexico", str(fixtures / "lexico-carandiru.json")]) == 0
    assert "válido" in capsys.readouterr().out
    assert cli.main(["rodar", "--config", str(cfg), "--fonte", "rss:outra"]) == rodada.ERRO


def test_feed_malformado_derruba_so_a_fonte(cfg, rede):
    rede.responder(FEED, "<rss><channel><item>sem fechar")
    _, r = _rodar(cfg, rede)
    assert r.codigo_saida == rodada.ERRO
    assert r.falhas_de_fonte["rss:jornal"].startswith("listagem: ParseError")


def test_corpus_relativo():
    corpus = Corpus("/dados/corpus", guardar=False)
    assert corpus.relativo(None) is None


@pytest.mark.parametrize(
    "dados", [{}, {"catalogo": {"nivel_minimo": 1}, "vistas": {"nivel_minimo": 2}}]
)
def test_cli_validar_config_recusa(tmp_path, dados, capsys):
    base = {
        "lexico": "lexico.json",
        "fontes": [{"tipo": "rss", "id": "rss:x", "url": "https://x/feed"}],
    }
    caminho = tmp_path / "config.json"
    caminho.write_text(json.dumps({**base, **dados}))
    assert cli.main(["validar-config", str(caminho)]) == rodada.ERRO
    assert "estrato" in capsys.readouterr().err
