"""Cliente HTTP educado: identifica o projeto, obedece o limite da fonte e o robots.txt.

O limite é o que o adaptador declara (`limite_por_minuto`), não um número que o motor
negocia. O transporte é injetável: os testes trocam a rede por fixtures gravadas.

Duas regras de segurança que este módulo impõe sozinho:

- **Nenhuma mensagem de erro ou linha de log carrega segredo.** Toda URL passa por
  `redigir()` antes de virar texto: `api_key=`, `token=` e afins saem como `<redigido>`.
  O relatório da rodada é comitado num repositório público; uma falha do OpenAlex depois
  das tentativas levaria a chave inteira para o histórico do git.
- **Falha transitória é retentada, inclusive a resposta truncada.** `IncompleteRead`,
  `RemoteDisconnected` e `BadStatusLine` herdam de `http.client.HTTPException`, não de
  `OSError`; sem este `except`, uma conexão encerrada pelo servidor virava "falha de fonte"
  sem nova tentativa (foi o que derrubou a primeira rodada do observatório).
"""

from __future__ import annotations

import http.client
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable
from dataclasses import dataclass, field

from aletheia import __version__

log = logging.getLogger(__name__)

USER_AGENT = (
    f"Aletheia/{__version__} (pesquisa acadêmica; +https://github.com/luccas-amorim/aletheia)"
)
RETENTAVEIS = {408, 425, 429, 500, 502, 503, 504}

_SEGREDOS = re.compile(
    r"((?:api[_-]?key|apikey|key|token|access[_-]?token|secret|password|senha|mailto)=)([^&#\s]+)",
    re.I,
)


def redigir(texto: str) -> str:
    """Troca o valor de parâmetros sensíveis por `<redigido>`. Idempotente."""
    return _SEGREDOS.sub(r"\1<redigido>", texto)


@dataclass(frozen=True)
class Requisicao:
    metodo: str
    url: str
    corpo: bytes | None = None
    cabecalhos: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Resposta:
    status: int
    url: str
    corpo: bytes
    cabecalhos: dict[str, str] = field(default_factory=dict)

    def json(self):
        return json.loads(self.corpo.decode("utf-8"))


Transporte = Callable[[Requisicao, float], Resposta]


class ErroColeta(RuntimeError):
    """Falha de rede ou de HTTP depois de esgotadas as tentativas."""


class BloqueadoPorRobots(ErroColeta):
    """O robots.txt da origem não autoriza o caminho. Não é falha: é política."""


class BloqueadoPorPais(ErroColeta):
    """A origem recusa conexões de fora do Brasil (medido no DJEN, via CloudFront).

    Não adianta tentar de novo nem trocar de cabeçalho: a rodada precisa sair de um IP
    brasileiro (runner próprio no Brasil, máquina local, nuvem em região de São Paulo).
    """


# Assinaturas de bloqueio geográfico no corpo de um 403.
_MARCAS_DE_PAIS = (
    b"block access from your country",
    b"not available in your country",
    b"geo-restricted",
)

# Exceções de transporte que merecem nova tentativa: rede, DNS, timeout e resposta
# truncada ou encerrada pelo servidor (estas últimas não são OSError).
TRANSITORIAS = (OSError, urllib.error.URLError, http.client.HTTPException)


def transporte_urllib(req: Requisicao, tempo_limite: float) -> Resposta:
    pedido = urllib.request.Request(
        req.url, data=req.corpo, headers=req.cabecalhos, method=req.metodo
    )
    try:
        with urllib.request.urlopen(pedido, timeout=tempo_limite) as r:
            return Resposta(
                r.status, r.geturl(), r.read(), {k.lower(): v for k, v in r.headers.items()}
            )
    except urllib.error.HTTPError as erro:
        cabecalhos = {k.lower(): v for k, v in (erro.headers or {}).items()}
        return Resposta(erro.code, req.url, erro.read() or b"", cabecalhos)


class Cliente:
    def __init__(
        self,
        limite_por_minuto: int,
        *,
        respeita_robots: bool = True,
        transporte: Transporte = transporte_urllib,
        cabecalhos: dict[str, str] | None = None,
        tentativas: int = 4,
        tempo_limite: float = 60.0,
        dormir: Callable[[float], None] | None = None,
        relogio: Callable[[], float] | None = None,
    ) -> None:
        if limite_por_minuto <= 0:
            raise ValueError("limite_por_minuto precisa ser positivo")
        self.intervalo = 60.0 / limite_por_minuto
        self.respeita_robots = respeita_robots
        self.transporte = transporte
        self.cabecalhos = {"User-Agent": USER_AGENT, **(cabecalhos or {})}
        self.tentativas = tentativas
        self.tempo_limite = tempo_limite
        # Resolvidos na chamada, e não na definição, para que os testes troquem o relógio.
        self._dormir = dormir or (lambda segundos: time.sleep(segundos))
        self._relogio = relogio or (lambda: time.monotonic())
        self._ultima: float | None = None
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _aguardar(self) -> None:
        if self._ultima is not None:
            espera = self.intervalo - (self._relogio() - self._ultima)
            if espera > 0:
                self._dormir(espera)
        self._ultima = self._relogio()

    def _permitido(self, url: str) -> bool:
        partes = urllib.parse.urlsplit(url)
        origem = f"{partes.scheme}://{partes.netloc}"
        if origem not in self._robots:
            # Falha de rede aqui sobe como ErroColeta e não fica em cache: a próxima
            # requisição à mesma origem tenta ler o robots.txt de novo.
            self._robots[origem] = self._ler_robots(origem)
        regras = self._robots[origem]
        return regras is None or regras.can_fetch(self.cabecalhos["User-Agent"], url)

    def _ler_robots(self, origem: str) -> urllib.robotparser.RobotFileParser | None:
        """None quando não há robots.txt (404 e afins): a convenção é tudo permitido.

        401 e 403 são lidos como "proíbe tudo". É mais conservador que a RFC 9309 (que
        trata 4xx como ausência de restrição) e é escolha deliberada: origem que esconde
        o robots.txt não ganha o benefício da dúvida.
        """
        resposta = self._enviar(
            Requisicao("GET", f"{origem}/robots.txt", cabecalhos=dict(self.cabecalhos))
        )
        regras = urllib.robotparser.RobotFileParser()
        if resposta.status in (401, 403):
            regras.disallow_all = True
            return regras
        if resposta.status >= 400:
            return None
        regras.parse(resposta.corpo.decode("utf-8", errors="replace").splitlines())
        return regras

    def _enviar(self, req: Requisicao) -> Resposta:
        ultimo: str = ""
        for tentativa in range(self.tentativas):
            self._aguardar()
            try:
                resposta = self.transporte(req, self.tempo_limite)
            except TRANSITORIAS as erro:
                ultimo = f"{type(erro).__name__}: {redigir(str(erro))}"
            else:
                if resposta.status not in RETENTAVEIS:
                    return resposta
                ultimo = f"HTTP {resposta.status}"
            if tentativa + 1 < self.tentativas:
                pausa = min(60.0, 2.0 ** (tentativa + 1))
                log.warning(
                    "%s %s falhou (%s); nova tentativa em %ss",
                    req.metodo, redigir(req.url), ultimo, pausa,
                )  # fmt: skip
                self._dormir(pausa)
        raise ErroColeta(
            f"{req.metodo} {redigir(req.url)} falhou após {self.tentativas} tentativas: {ultimo}"
        )

    def requisitar(
        self,
        url: str,
        *,
        metodo: str = "GET",
        params: dict | list[tuple[str, str]] | None = None,
        json_corpo: dict | None = None,
        cabecalhos: dict[str, str] | None = None,
    ) -> Resposta:
        """Faz a requisição e devolve a resposta 2xx. Qualquer outro status é ErroColeta."""
        if params:
            url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
        if self.respeita_robots and not self._permitido(url):
            raise BloqueadoPorRobots(f"robots.txt não autoriza {redigir(url)}")
        todos = {**self.cabecalhos, **(cabecalhos or {})}
        corpo = None
        if json_corpo is not None:
            corpo = json.dumps(json_corpo, ensure_ascii=False).encode("utf-8")
            todos.setdefault("Content-Type", "application/json")
        resposta = self._enviar(Requisicao(metodo, url, corpo, todos))
        if resposta.status == 403 and any(m in resposta.corpo for m in _MARCAS_DE_PAIS):
            raise BloqueadoPorPais(
                f"{metodo} {redigir(url)}: a origem bloqueia acesso de fora do Brasil; "
                "rode a partir de um IP brasileiro"
            )
        if not 200 <= resposta.status < 300:
            trecho = resposta.corpo[:300].decode("utf-8", errors="replace")
            raise ErroColeta(f"{metodo} {redigir(url)} -> HTTP {resposta.status}: {trecho}")
        return resposta
