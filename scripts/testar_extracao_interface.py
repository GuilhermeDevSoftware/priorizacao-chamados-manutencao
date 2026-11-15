"""Teste da extração opcional na interface, inteiramente com respostas simuladas.

Uso: python scripts/testar_extracao_interface.py
O Playwright intercepta configuração, extração e previsão. Nenhuma credencial
é necessária e nenhuma solicitação é enviada à OpenAI ou a outro provedor.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

class ServidorSemLog(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(ServidorSemLog, directory=str(ROOT / 'frontend')))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        checks=[]
        requests=[]
        with sync_playwright() as p:
            executavel = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
            browser=p.chromium.launch(executable_path=executavel,headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':390,'height':844})
            page.route('**/config.json',lambda route: route.fulfill(json={'modo':'api','extracao_habilitada':True}))
            def extract(route):
                assert route.request.post_data_json=={'descricao':'Fiação exposta em corredor de pouca circulação.'}
                route.fulfill(json={'campos':{'risco_seguranca':1,'servico_essencial_interrompido':None,'pessoas_afetadas':None,'dias_aguardando':0,'recorrente':None},'origem':'Dados simulados para teste da interface','confirmacao_necessaria':True})
            page.route('**/api/extrair',extract)
            def predict(route):
                requests.append(route.request.post_data_json)
                route.fulfill(json={'classe':1,'rotulo':'Prioritário','campos':route.request.post_data_json})
            page.route('**/api/prever',predict)
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.wait_for_function("!document.querySelector('#extrair').disabled")
            page.locator('#descricao').fill('Fiação exposta em corredor de pouca circulação.')
            page.locator('#extrair').click()
            page.locator('#confirmacao-box').wait_for(state='visible')
            assert page.locator('#risco_seguranca').input_value()=='1'
            assert page.locator('#dias_aguardando').input_value()=='0'
            assert all(page.locator('#'+field).input_value()=='' for field in ['servico_essencial_interrompido','pessoas_afetadas','recorrente'])
            assert len(requests)==0
            checks.append({'cenario':'Sugestões simuladas com informações ausentes','resultado':'Campos ausentes continuam vazios; campos conhecidos preenchidos; nenhuma previsão automática.'})
            page.locator('#analisar').click()
            assert page.locator('#erro-pessoas_afetadas').inner_text()
            assert len(requests)==0
            checks.append({'cenario':'Analisar com sugestões desconhecidas','resultado':'Validação bloqueou a previsão antes de chamar a API.'})
            page.locator('#servico_essencial_interrompido').select_option('0')
            page.locator('#pessoas_afetadas').fill('2')
            page.locator('#recorrente').select_option('0')
            page.locator('#analisar').click()
            assert 'marque a confirmação' in page.locator('#form-status').inner_text()
            assert len(requests)==0
            checks.append({'cenario':'Campos completos sem confirmação humana','resultado':'Previsão bloqueada; solicitada confirmação explícita.'})
            page.locator('#confirmar-campos').check()
            page.locator('#pessoas_afetadas').fill('3')
            assert not page.locator('#confirmar-campos').is_checked()
            checks.append({'cenario':'Editar campo após confirmar sugestões','resultado':'Confirmação foi desmarcada automaticamente.'})
            page.locator('#confirmar-campos').check()
            page.locator('#analisar').click()
            page.locator('#resultado').wait_for(state='visible')
            assert page.locator('#resultado-titulo').inner_text()=='1 · Prioritário'
            assert len(requests)==1 and requests[0]['pessoas_afetadas']==3
            checks.append({'cenario':'Campos completos e confirmados','resultado':'Uma chamada à API de previsão com campos revisados; resultado prioritário exibido.'})
            page.locator('#limpar').click()
            page.unroute('**/api/extrair',extract)
            page.route('**/api/extrair',lambda route:route.fulfill(status=502,json={'erro':'Serviço de IA indisponível (simulado).'}))
            page.locator('#descricao').fill('Descrição fictícia do teste de indisponibilidade.')
            page.locator('#extrair').click()
            page.wait_for_function("document.querySelector('#extracao-status').textContent.includes('Serviço de IA indisponível')")
            page.locator("[data-exemplo='fiacao']").click()
            page.locator('#analisar').click()
            page.locator('#resultado').wait_for(state='visible')
            assert len(requests)==2
            checks.append({'cenario':'Serviço externo indisponível simulado','resultado':'Mensagem de falha exibida e entrada manual continuou funcionando com previsão pela API.'})
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    report={'script':'scripts/testar_extracao_interface.py','executado_em':datetime.now(timezone.utc).isoformat(),'ambiente':'Chromium headless local, viewport móvel 390 x 844','integracao_externa':'Simulada com interceptação Playwright; nenhuma chamada real à OpenAI.','chamadas_previsao_simuladas':len(requests),'verificacoes':checks,'resultado':'6 verificações aprovadas'}
    (ROOT/'relatorios'/'teste_extracao_interface.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
