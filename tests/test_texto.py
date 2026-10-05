from aletheia.texto import Pagina, decodificar, dobrar, normalizar


def test_cp1252_declarado_como_latin1(fixtures):
    texto, codificacao = decodificar((fixtures / "rss" / "materia-carandiru.html").read_bytes())
    assert codificacao == "cp1252"
    assert "Detenção de\nSão Paulo" in texto


def test_cabecalho_http_vence_o_meta():
    bruto = '<meta charset="cp1252"><p>ação</p>'.encode()
    texto, codificacao = decodificar(bruto, "text/html; charset=utf-8")
    assert codificacao == "utf-8"
    assert "ação" in texto


def test_utf16_com_bom_e_byte_solto():
    bruto = "﻿Lei penal".encode("utf-16-le") + b" "
    bruto = b"\xff\xfe" + bruto[2:]
    texto, codificacao = decodificar(bruto)
    assert codificacao == "utf-16"
    assert texto.strip("﻿") == "Lei penal"


def test_sem_declaracao_tenta_utf8_e_cai_em_cp1252():
    assert decodificar("ação".encode())[1] == "utf-8"
    assert decodificar("ação".encode("cp1252"))[1] == "cp1252"


def test_pagina_ignora_script_nav_e_rodape(fixtures):
    html, _ = decodificar((fixtures / "rss" / "materia-carandiru.html").read_bytes())
    pagina = Pagina(html)
    assert "Pavilhão 9" in pagina.texto
    assert "publicidade" not in pagina.texto
    assert "Especial Carandiru" not in pagina.texto
    assert "o filme" not in pagina.texto
    assert pagina.manchete.startswith("Massacre do Carandiru")
    assert pagina.meta["description"].startswith("Familiares")


def test_dobrar_preserva_comprimento():
    original = "AÇÃO Penal — São Paulo, ÍNDIO, ﬁm, İstanbul"
    dobrado = dobrar(original)
    assert len(dobrado) == len(original)
    assert dobrado.startswith("acao penal — sao paulo, indio")


def test_normalizar_colapsa_espacos_e_linhas():
    assert normalizar("a\xa0 b\r\n\n\n\n c  ") == "a b\n\nc"
