"""Testes reais no Chromium: celular, API Flask e caminhos do GitHub Pages.

Uso: python scripts/testar_navegador.py
     python scripts/testar_navegador.py --url https://usuario.github.io/repositorio/
São usados apenas chamados fictícios e nenhuma API generativa real.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RELATORIOS = ROOT / "relatorios"
CAMPOS = ["risco_seguranca", "servico_essencial_interrompido", "pessoas_afetadas", "dias_aguardando", "recorrente"]


@contextmanager
def servidores_locais():
    """Sobe processos apenas pelo tempo do teste e usa o artefato Pages final."""
    subprocess.run([sys.executable, str(ROOT / "scripts/preparar_pages.py")], cwd=ROOT, check=True)
    ambiente = dict(os.environ)
    ambiente["OPENAI_API_KEY"] = ""
    dados_temporarios = tempfile.TemporaryDirectory(prefix="chamados-browser-db-")
    ambiente["CHAMADOS_TEST_DATABASE"] = str(Path(dados_temporarios.name) / "testes.sqlite3")
    ambiente["CHAMADOS_TEST_UPLOADS"] = str(Path(dados_temporarios.name) / "uploads")
    flask = subprocess.Popen(
        [sys.executable, "-c", "import os; from app import create_app; create_app({'OPENAI_API_KEY': '', 'DATABASE_PATH': os.environ['CHAMADOS_TEST_DATABASE'], 'UPLOAD_FOLDER': os.environ['CHAMADOS_TEST_UPLOADS']}).run(host='127.0.0.1', port=5055, use_reloader=False)"],
        cwd=ROOT, env=ambiente, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    servidor = None
    try:
        for _ in range(100):
            try:
                with urlopen("http://127.0.0.1:5055/config.json", timeout=1) as resposta:
                    if resposta.status == 200:
                        break
            except OSError:
                if flask.poll() is not None:
                    raise RuntimeError("O Flask terminou antes de ficar pronto.")
                time.sleep(0.1)
        else:
            raise RuntimeError("O Flask não ficou pronto em 10 segundos.")
        with tempfile.TemporaryDirectory(prefix="chamados-pages-") as pasta:
            # Subdiretório reproduz a URL /nome-do-repositorio/ do Pages.
            (Path(pasta) / "priorizacao-chamados-manutencao").symlink_to(ROOT / "docs", target_is_directory=True)
            class SemLog(SimpleHTTPRequestHandler):
                def log_message(self, *_args):
                    pass
            servidor = ThreadingHTTPServer(("127.0.0.1", 8765), partial(SemLog, directory=pasta))
            threading.Thread(target=servidor.serve_forever, daemon=True).start()
            yield [("flask", "http://127.0.0.1:5055/", "api"),
                   ("pages_local", "http://127.0.0.1:8765/priorizacao-chamados-manutencao/", "demonstracao")]
    finally:
        if servidor:
            servidor.shutdown()
            servidor.server_close()
        flask.terminate()
        try:
            flask.wait(timeout=5)
        except subprocess.TimeoutExpired:
            flask.kill()
            flask.wait()
        dados_temporarios.cleanup()


def preencher(page, valores):
    for nome, valor in zip(CAMPOS, valores):
        seletor = page.locator(f"#{nome}")
        if nome in ("risco_seguranca", "servico_essencial_interrompido", "recorrente"):
            seletor.select_option(str(valor))
        else:
            seletor.fill(str(valor))


def testar_modo(browser, nome, url, modo_esperado):
    contexto = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=1)
    page = contexto.new_page()
    erros_console, erros_pagina = [], []
    requisicoes_api, respostas_api = [], []
    def registrar_resposta(resposta):
        if resposta.url.endswith('/api/prever') and resposta.request.method == 'POST':
            dados = resposta.json()
            respostas_api.append({"status": resposta.status, "classe": dados.get("classe"), "rotulo": dados.get("rotulo")})
    page.on("request", lambda req: requisicoes_api.append(req.method) if req.url.endswith('/api/prever') else None)
    page.on("response", registrar_resposta)
    page.on("console", lambda msg: erros_console.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda erro: erros_pagina.append(str(erro)))
    try:
        resposta = page.goto(url, wait_until="networkidle", timeout=45000)
        assert resposta and resposta.status == 200, f"Página indisponível: {url}"
        page.get_by_role("button", name="Analisar chamado", exact=True).wait_for()
        config = page.evaluate("async () => (await fetch('./config.json')).json()")
        assert config["modo"] == modo_esperado, config
        assert config["extracao_habilitada"] is False
        assert page.locator("html").get_attribute("lang") == "pt-BR"
        assert page.locator("#extrair").is_disabled() == (modo_esperado == "demonstracao")
        # Exemplos precisam preencher os cinco campos, mantendo a descrição fictícia.
        exemplos_testados = []
        for exemplo in ("macaneta", "agua", "fiacao"):
            page.locator(f"button[data-exemplo='{exemplo}']").click()
            assert page.locator("#descricao").input_value().strip()
            assert all(page.locator(f"#{campo}").input_value() != "" for campo in CAMPOS)
            exemplos_testados.append(exemplo)
        # Não depende apenas de cor: resultado deve conter rótulo textual.
        resultados = []
        cenarios = [
            ("Maçaneta frouxa em sala desocupada", [0, 0, 0, 1, 0], "Normal"),
            ("Falta de água na escola", [0, 1, 180, 0, 0], "Prioritário"),
            ("Fiação exposta em local com pouca circulação", [1, 0, 1, 0, 0], "Prioritário"),
        ]
        for descricao, valores, esperado in cenarios:
            preencher(page, valores)
            page.locator("#descricao").fill(descricao)
            if modo_esperado == "api":
                with page.expect_response(lambda r: r.url.endswith('/api/prever') and r.request.method == 'POST'):
                    page.get_by_role("button", name="Analisar chamado", exact=True).click()
            else:
                page.get_by_role("button", name="Analisar chamado", exact=True).click()
            page.locator("#resultado").wait_for(state="visible")
            page.wait_for_function("(dados) => { const texto = document.querySelector('#resultado').textContent; return texto.includes(dados.rotulo) && texto.includes(dados.descricao); }", arg={"rotulo": esperado, "descricao": descricao})
            texto = page.locator("#resultado").inner_text()
            assert descricao in texto, texto
            resultados.append({"cenario": descricao, "resultado": esperado, "status": "aprovado"})
        # Formulário incompleto deve sinalizar campo, sem produzir previsão nova.
        page.locator("#pessoas_afetadas").fill("")
        page.get_by_role("button", name="Analisar chamado", exact=True).click()
        assert page.locator("#pessoas_afetadas").evaluate("e => !e.checkValidity()")
        assert page.locator("#erro-pessoas_afetadas").inner_text().strip()
        resultados.append({"cenario": "Formulário incompleto", "resultado": "campo obrigatório rejeitado", "status": "aprovado"})
        page.locator("#pessoas_afetadas").fill("-1")
        page.get_by_role("button", name="Analisar chamado", exact=True).click()
        assert page.locator("#pessoas_afetadas").evaluate("e => !e.checkValidity()")
        assert page.locator("#erro-pessoas_afetadas").inner_text().strip()
        page.locator("#pessoas_afetadas").fill("1.5")
        page.get_by_role("button", name="Analisar chamado", exact=True).click()
        assert page.locator("#pessoas_afetadas").evaluate("e => !e.checkValidity()")
        assert page.locator("#erro-pessoas_afetadas").inner_text().strip()
        resultados.append({"cenario": "Valores -1 e 1,5", "resultado": "inteiros inválidos rejeitados", "status": "aprovado"})
        # Foco por teclado alcança elementos úteis; indicador não fica em body.
        page.locator("#descricao").focus()
        page.keyboard.press("Tab")
        foco = page.evaluate("document.activeElement.tagName")
        assert foco in ("BUTTON", "SELECT", "INPUT", "TEXTAREA", "A"), foco
        sem_overflow = page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert sem_overflow, "Há rolagem horizontal em 390px."
        preencher(page, [1, 0, 1, 0, 0])
        if modo_esperado == "api":
            with page.expect_response(lambda r: r.url.endswith('/api/prever') and r.request.method == 'POST'):
                page.get_by_role("button", name="Analisar chamado", exact=True).click()
        else:
            page.get_by_role("button", name="Analisar chamado", exact=True).click()
        page.wait_for_function("document.querySelector('#resultado').textContent.includes('Prioritário')")
        captura = RELATORIOS / f"celular_{nome}_v2.png"
        # Volta ao topo: evita que elementos fixed fora da tela apareçam no full-page.
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        page.screenshot(path=str(captura), full_page=True)
        if modo_esperado == "api":
            assert len(requisicoes_api) == 4 and len(respostas_api) == 4, (requisicoes_api, respostas_api)
            assert all(r["status"] == 200 and r["classe"] in (0, 1) and r["rotulo"] in ("Normal", "Prioritário") for r in respostas_api)
        else:
            assert not requisicoes_api and not respostas_api, (requisicoes_api, respostas_api)
        assert not erros_console, erros_console
        assert not erros_pagina, erros_pagina
        return {"modo": nome, "url": url, "viewport": "390x844", "configuracao": config,
                "cenarios": resultados, "exemplos_preenchiveis": exemplos_testados, "extracao_sem_credencial": "sugestão local disponível" if modo_esperado == "api" else "botão desabilitado", "teclado": "foco útil após Tab", "rolagem_horizontal": False,
                "chamadas_post_api_prever": len(requisicoes_api), "respostas_api_prever": respostas_api, "erros_console": erros_console, "erros_pagina": erros_pagina,
                "captura": str(captura.relative_to(ROOT)), "status": "aprovado"}
    finally:
        contexto.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Testar somente a URL pública (modo demonstração).")
    args = parser.parse_args()
    RELATORIOS.mkdir(exist_ok=True)
    with sync_playwright() as p:
        # Aceita navegador já instalado ou o Chromium baixado pelo Playwright.
        executavel = os.environ.get("CHROMIUM_PATH") or shutil.which("chromium") or shutil.which("google-chrome")
        browser = p.chromium.launch(executable_path=executavel, headless=True, args=["--no-sandbox"])
        try:
            if args.url:
                testes = [testar_modo(browser, "pages_publico", args.url, "demonstracao")]
                destino = RELATORIOS / "teste_pages_publico_v2.json"
                paridade = None
            else:
                with servidores_locais() as modos:
                    testes = [testar_modo(browser, *modo) for modo in modos]
                sys.path.insert(0, str(ROOT / "tests"))
                from test_paridade import medir_paridade
                paridade = medir_paridade()
                destino = RELATORIOS / "testes_automatizados_v2.json"
            relatorio = {"executado_em_utc": datetime.now(timezone.utc).isoformat(),
                         "ambiente": "Codex Cloud Linux; Chromium real via Playwright, modo headless",
                         "dados": "Somente chamados fictícios", "navegador": browser.version,
                         "paridade": paridade, "fluxos": testes, "status": "aprovado"}
            destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(relatorio, ensure_ascii=False, indent=2))
        finally:
            browser.close()


if __name__ == "__main__":
    main()
