import csv
import json
from datetime import date

import pytest

from aletheia import cli, estimativa
from aletheia.estimativa import Par, normalizar_url
from aletheia.url import identidade


def test_normalizar_url_reexportada():
    assert normalizar_url("https://www.Jornal.br/a/b/") == "jornal.br/a/b"


def test_chapman_com_numeros_conhecidos():
    # n1 = 100, n2 = 80, em comum 40: Lincoln-Petersen daria 200; Chapman, 199,4.
    par = Par("a", "b", 100, 80, 40)
    assert par.chapman == pytest.approx(101 * 81 / 41 - 1)
    baixo, alto = par.intervalo
    assert 140 <= baixo < par.chapman < alto


def _vistas(caminho, observacoes):
    """observacoes: (fonte, url, nivel, rodada[, publicado_em[, hash]])."""
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=estimativa_colunas())
        escritor.writeheader()
        for obs in observacoes:
            fonte, url, nivel, rodada = obs[:4]
            publicado = obs[4] if len(obs) > 4 else ""
            hash_texto = obs[5] if len(obs) > 5 else ""
            escritor.writerow({
                "id": identidade(url), "canal": estimativa.canal(fonte), "fonte": fonte,
                "rodada": rodada, "nivel": nivel, "publicado_em": publicado,
                "hash_texto": hash_texto, "url": url,
            })  # fmt: skip


def estimativa_colunas():
    from aletheia.saidas.vistas import COLUNAS

    return COLUNAS


def test_calcular_canais_chao_curva_e_dedupe_por_hash(tmp_path):
    vistas = tmp_path / "vistas.csv"
    r1, r2 = "20261001T000000Z", "20261008T000000Z"
    _vistas(vistas, [
        ("wayback:j", "http://j.br/1", 3, r1),
        ("wayback:k", "http://k.br/2", 2, r1),
        ("wayback:j", "http://j.br/ruido", 1, r1),            # nível 1 fica de fora
        ("topico:c", "https://www.j.br/1", 3, r2),             # mesma URL normalizada
        ("topico:c", "https://k.br/9", 2, r2, "", "HASH-A"),
        ("rss:jornal", "https://k.br/9-amp", 3, r2, "", "HASH-A"),  # outra URL, mesmo texto
        ("openalex:c", "https://doi.org/10.1/x", 3, r2),
        ("crossref:c", "https://doi.org/10.1/x", 3, r2),
    ])  # fmt: skip

    estrato = {"openalex:c": "academico", "crossref:c": "academico"}
    por_estrato = estimativa.calcular(vistas, estrato_de=lambda f: estrato.get(f, "imprensa"))
    imprensa, academico = por_estrato["imprensa"], por_estrato["academico"]

    # Dois domínios do Wayback são um canal só; k.br/9 e k.br/9-amp são um documento.
    assert set(imprensa.por_canal) == {"wayback", "topico", "rss"}
    assert len(imprensa.observadas) == 3
    assert imprensa.frequencias == {2: 2, 1: 1}
    assert imprensa.chao == 3 + 1 * 1 / (2 * 2)
    assert imprensa.curva == [(r1, 2, 2), (r2, 1, 3)]
    assert academico.chao == 1  # dois canais, tudo em comum: piso igual ao observado

    texto = estimativa.relatorio(por_estrato)
    assert "## Estrato `imprensa`" in texto and "## Estrato `academico`" in texto
    assert "`topico` × `wayback` | 2 | 2 | 1 |" in texto


def test_gdelt_so_entra_no_piso_com_desde(tmp_path):
    vistas = tmp_path / "vistas.csv"
    r = "20261001T000000Z"
    _vistas(vistas, [
        ("wayback:j", "http://j.br/velha", 3, r, "2002-10-02"),
        ("wayback:j", "http://j.br/nova", 3, r, "2026-09-30"),
        ("gdelt:c", "http://j.br/nova", 3, r, "2026-09-30"),
    ])  # fmt: skip
    (sem,) = estimativa.calcular(vistas).values()
    assert sem.chao is None  # wayback + gdelt sem alinhar: um canal comparável só
    assert "não comparável" in estimativa.relatorio({"geral": sem})

    (com,) = estimativa.calcular(vistas, desde=date(2026, 7, 1)).values()
    assert com.observadas == {identidade("http://j.br/nova")}
    assert com.alinhado and com.chao == 1


def test_um_canal_so_nao_estima(tmp_path):
    vistas = tmp_path / "vistas.csv"
    _vistas(vistas, [("rss:a", "https://x.br/1", 3, "20261001T000000Z")])
    por_estrato = estimativa.calcular(vistas)
    assert por_estrato["geral"].chao is None
    assert "ao menos dois" in estimativa.relatorio(por_estrato)


def test_sem_vistas_relatorio_vazio(tmp_path):
    assert estimativa.calcular(tmp_path / "nao-existe.csv") == {}
    assert "Nenhuma rodada" in estimativa.relatorio({})


def test_cli_estimar_exige_vistas_e_grava_relatorio(cfg, capsys):
    assert cli.main(["estimar", "--config", str(cfg)]) == 2
    dados = json.loads(cfg.read_text())
    dados["vistas"] = {"arquivo": "vistas.csv"}
    cfg.write_text(json.dumps(dados))
    assert cli.main(["estimar", "--config", str(cfg)]) == 0
    assert "relatório em" in capsys.readouterr().out
    assert (cfg.parent / "dados" / "estimativa.md").exists()
