"""Verifica cadastro local, foto, painel e reinício real; usa dados fictícios.

Uso: python scripts/testar_evolucao.py
     python scripts/testar_evolucao.py --url https://usuario.github.io/repositorio/
O modo --url verifica somente a demonstração pública, sem gravar nada.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CAMPOS = ['risco_seguranca', 'servico_essencial_interrompido', 'pessoas_afetadas', 'dias_aguardando', 'recorrente']
RELATORIOS = ROOT / 'relatorios'


def imagem_sintetica():
    foto = Image.new('RGB', (800, 600), '#ece7df')
    d = ImageDraw.Draw(foto)
    d.rectangle((40, 50, 190, 200), fill='#8c9399')
    for x, cor in [(100, '#c2322a'), (130, '#1c5095'), (160, '#29804b')]:
        d.line([(x, 160), (x+80, 300), (x+200, 350)], fill=cor, width=10)
        d.line([(x+200, 350), (x+230, 370)], fill='#b77935', width=5)
    b = io.BytesIO(); foto.save(b, format='JPEG')
    return {'name': 'fiacao-sintetica.jpg', 'mimeType': 'image/jpeg', 'buffer': b.getvalue()}


class FlaskTemporario:
    def __init__(self, pasta):
        self.pasta = Path(pasta)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); self.porta = s.getsockname()[1]
        self.url = f'http://127.0.0.1:{self.porta}/'
        self.processo = None

    def iniciar(self):
        config = {'OPENAI_API_KEY': '', 'DATABASE_PATH': str(self.pasta/'chamados.sqlite3'), 'UPLOAD_FOLDER': str(self.pasta/'uploads')}
        codigo = f"from app import create_app; create_app({config!r}).run(host='127.0.0.1', port={self.porta}, use_reloader=False)"
        ambiente = dict(os.environ); ambiente['OPENAI_API_KEY'] = ''
        self.processo = subprocess.Popen([sys.executable, '-c', codigo], cwd=ROOT, env=ambiente, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with urlopen(self.url+'config.json', timeout=1) as r:
                    if r.status == 200: return
            except OSError:
                if self.processo.poll() is not None: raise RuntimeError('Flask encerrou durante inicialização.')
                time.sleep(.1)
        raise RuntimeError('Flask não ficou pronto.')

    def encerrar(self):
        if self.processo:
            self.processo.terminate()
            try: self.processo.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.processo.kill(); self.processo.wait()
            self.processo = None


@contextmanager
def pages_temporario():
    subprocess.run([sys.executable, str(ROOT/'scripts/preparar_pages.py')], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix='chamados-estatico-') as pasta:
        (Path(pasta)/'priorizacao-chamados-manutencao').symlink_to(ROOT/'docs', target_is_directory=True)
        class Silencioso(SimpleHTTPRequestHandler):
            def log_message(self, *_): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Silencioso, directory=pasta))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try: yield f'http://127.0.0.1:{server.server_port}/priorizacao-chamados-manutencao/'
        finally: server.shutdown(); server.server_close()


def observar(page):
    erros = []
    page.on('pageerror', lambda e: erros.append(str(e)))
    page.on('console', lambda msg: erros.append(msg.text) if msg.type == 'error' else None)
    return erros


def preencher(page, descricao, valores, equipe):
    page.locator('#descricao').fill(descricao)
    page.locator('#local').fill('Local fictício para teste automatizado')
    for nome, valor in zip(CAMPOS, valores):
        campo = page.locator('#'+nome)
        if nome in ('risco_seguranca', 'servico_essencial_interrompido', 'recorrente'): campo.select_option(str(valor))
        else: campo.fill(str(valor))
    page.locator('#equipe_confirmada').select_option(equipe)


def testar_flask(browser):
    with tempfile.TemporaryDirectory(prefix='chamados-persistencia-') as pasta:
        flask = FlaskTemporario(pasta)
        context = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        page = context.new_page(); erros = observar(page)
        try:
            flask.iniciar()
            page.goto(flask.url, wait_until='networkidle')
            page.wait_for_function("!document.querySelector('#salvar').disabled")
            assert page.locator('#foto-camera').get_attribute('capture') == 'environment'
            page.locator('#foto').set_input_files(imagem_sintetica())
            page.locator('#foto-previa').wait_for(state='visible')
            page.locator('#remover-foto').click()
            assert not page.locator('#foto-previa').is_visible()
            page.locator('#foto').set_input_files({'name':'invalida.txt','mimeType':'text/plain','buffer':b'nao e imagem'})
            assert 'inválido' in page.locator('#foto-status').inner_text()
            cenarios = [
                ('Fiação exposta em corredor de pouca circulação — imagem sintética de teste.', [1,0,1,0,0], 'Elétrica', 1),
                ('Vazamento na torneira auxiliar — cenário fictício sem foto.', [0,0,3,1,0], 'Hidráulica', 0),
                ('Computador com defeito — cenário fictício de TI.', [0,0,2,1,0], 'TI', 0),
                ('Internet sem conexão e tomada danificada — caso fictício de duas áreas.', [1,0,4,0,0], 'Triagem geral', 1),
            ]
            criados = []
            for i, (descricao, valores, equipe, prioridade) in enumerate(cenarios):
                page.locator('#limpar').click()
                preencher(page, descricao, valores, equipe)
                if i == 0:
                    page.locator('#foto').set_input_files(imagem_sintetica())
                    page.locator('#foto-previa').wait_for(state='visible')
                    # Trocar a foto invalida sugestões e seleção de equipe.
                    page.locator('#equipe_confirmada').select_option(equipe)
                with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/api/analisar')) as analise:
                    page.locator('#extrair').click()
                sugestao = analise.value.json()
                assert sugestao['origem'] == 'regra_local'
                assert sugestao['aviso'] and sugestao['equipe_sugerida'] == equipe
                # A regra local não cria valores; os campos manuais permanecem revisáveis.
                assert all(v is None for v in sugestao['campos'].values())
                page.locator('#salvar').click()
                assert 'Confirme' in page.locator('#form-status').inner_text()
                page.locator('#confirmar-campos').check()
                with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/api/chamados')) as resposta:
                    page.locator('#salvar').click()
                assert resposta.value.status == 201, resposta.value.text()
                registro = resposta.value.json()
                assert registro['prioridade_sugerida'] == prioridade
                assert registro['equipe_confirmada'] == equipe
                assert bool(registro['foto_caminho']) == (i == 0)
                page.locator(f"#lista-chamados article[data-chamado-id='{registro['id']}']").wait_for()
                criados.append(registro)
            primeiro = criados[0]
            page.locator(f"#lista-chamados article[data-chamado-id='{primeiro['id']}'] button").click()
            page.locator('#detalhe-chamado').wait_for(state='visible')
            page.locator('#detalhe-foto').wait_for(state='visible')
            page.locator('#detalhe-equipe').select_option('Triagem geral')
            page.locator('#detalhe-status').select_option('Em atendimento')
            with page.expect_response(lambda r: r.request.method == 'PATCH' and '/api/chamados/' in r.url) as atualizacao:
                page.locator('#atualizar-chamado').click()
            atualizado = atualizacao.value.json()
            assert atualizado['equipe_sugerida'] == 'Elétrica'
            assert atualizado['equipe_confirmada'] == 'Triagem geral'
            assert atualizado['status'] == 'Em atendimento'
            page.locator('#filtro-equipe').select_option('Triagem geral')
            page.locator('#filtro-prioridade').select_option('1')
            page.locator('#filtro-status').select_option('Em atendimento')
            page.wait_for_function("document.querySelectorAll('#lista-chamados article').length === 1")
            assert page.locator('#lista-chamados article').get_attribute('data-chamado-id') == str(primeiro['id'])
            foto_antes = page.request.get(flask.url+f"api/chamados/{primeiro['id']}/foto").body()
            flask.encerrar(); flask.iniciar()
            page.reload(wait_until='networkidle')
            page.wait_for_function("document.querySelectorAll('#lista-chamados article').length === 4")
            depois = page.request.get(flask.url+'api/chamados').json()
            assert depois['total'] == 4
            foto_depois = page.request.get(flask.url+f"api/chamados/{primeiro['id']}/foto").body()
            assert hashlib.sha256(foto_antes).digest() == hashlib.sha256(foto_depois).digest()
            persistido = page.request.get(flask.url+f"api/chamados/{primeiro['id']}").json()
            assert persistido['status'] == 'Em atendimento' and persistido['equipe_confirmada'] == 'Triagem geral'
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#descricao').focus(); page.keyboard.press('Tab')
            assert page.evaluate('document.activeElement.tagName') != 'BODY'
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(RELATORIOS/'evolucao_flask_celular.png'), full_page=True)
            assert not erros, erros
            return {'status':'aprovado','viewport':'390x844','cadastros':[
                {'cenario':c[0], 'equipe':c[2], 'prioridade':c[3], 'foto':i==0} for i,c in enumerate(cenarios)],
                'previa_remocao_foto':'aprovado','arquivo_invalido':'rejeitado no formulário',
                'confirmacao_obrigatoria':True,'ia_sem_chave':'regra local identificada; foto não analisada por IA',
                'correcao_manual_equipe':'Elétrica sugerida preservada; responsável alterado para Triagem geral',
                'status_chamado':'Em atendimento preservado após reinício','filtros_combinados':'um registro esperado',
                'persistencia':'processo Flask encerrado e outro iniciado com mesmo SQLite/uploads; quatro registros e foto íntegra',
                'captura_camera':'atributo capture=environment verificado; câmera física não exercitada',
                'rolagem_horizontal':False,'erros_console_e_pagina':erros,'captura':'relatorios/evolucao_flask_celular.png'}
        finally: context.close(); flask.encerrar()


def testar_pages(browser, url):
    context = browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    page=context.new_page(); erros=observar(page); envios=[]
    page.on('request',lambda r:envios.append(r.url) if r.method in ('POST','PATCH','PUT','DELETE') else None)
    try:
        resposta=page.goto(url,wait_until='networkidle'); assert resposta.status==200
        page.wait_for_function("document.querySelectorAll('#lista-chamados article').length === 4")
        assert page.locator('#salvar').is_disabled() and page.locator('#extrair').is_disabled()
        page.locator('#filtro-equipe').select_option('Hidráulica')
        page.locator('#filtro-prioridade').select_option('0')
        page.locator('#filtro-status').select_option('Em atendimento')
        assert page.locator('#lista-chamados article').count()==1
        page.locator('#lista-chamados article button').click()
        page.locator('#detalhe-chamado').wait_for(state='visible')
        assert page.locator('#detalhe-equipe').is_disabled()
        assert page.locator('#detalhe-status').is_disabled()
        assert page.locator('#atualizar-chamado').is_disabled()
        assert 'Flask' in page.locator('#detalhe-mensagem').inner_text()
        page.locator("[data-exemplo='fiacao']").click()
        page.locator('#analisar').click()
        page.wait_for_function("document.querySelector('#resultado-titulo').textContent.includes('Prioritário')")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.evaluate('window.scrollTo(0,0)')
        nome='evolucao_pages_publico.png' if url.startswith('https:') else 'evolucao_pages_local.png'
        page.screenshot(path=str(RELATORIOS/nome),full_page=True)
        assert not envios and not erros,(envios,erros)
        return {'status':'aprovado','url':url,'viewport':'390x844','exemplos_fixos':4,'filtros_combinados':'Hidráulica/Normal/Em atendimento = um exemplo',
                'alteracoes':'desabilitadas com explicação Flask','previsao_arvore':'fiação exposta = Prioritário',
                'envios_de_dados':envios,'rolagem_horizontal':False,'erros_console_e_pagina':erros,'captura':'relatorios/'+nome}
    finally: context.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--url'); args=parser.parse_args()
    RELATORIOS.mkdir(exist_ok=True)
    with sync_playwright() as p:
        executavel=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
        browser=p.chromium.launch(executable_path=executavel,headless=True,args=['--no-sandbox'])
        try:
            report={'executado_em_utc':datetime.now(timezone.utc).isoformat(),'ambiente':'Codex Cloud Linux, Chromium real headless via Playwright',
                    'navegador':browser.version,'dados':'Somente exemplos fictícios; imagem sintética de teste; SQLite e uploads temporários'}
            if args.url:
                report['pages_publico']=testar_pages(browser,args.url); destino=RELATORIOS/'testes_evolucao_pages_publico.json'
            else:
                report['flask']=testar_flask(browser)
                with pages_temporario() as url: report['pages_local']=testar_pages(browser,url)
                destino=RELATORIOS/'testes_evolucao_navegador.json'
            report['resultado']='aprovado'; destino.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps(report,ensure_ascii=False,indent=2))
        finally: browser.close()


if __name__=='__main__': main()
