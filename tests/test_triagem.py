"""Casos de triagem híbrida. Chamadas semânticas são simuladas."""
import base64
import json
from unittest.mock import Mock, patch

import pytest
import requests

from triagem import ROTULOS, classificar


def complementos(risco=0, **outros):
    return {"risco_seguranca": risco, "servico_essencial_interrompido": 0,
            "pessoas_afetadas": 1, "dias_aguardando": 0, "recorrente": 0, **outros}


@pytest.mark.parametrize("descricao,risco,prioridade,alerta,contradicao", [
    ("Quadro elétrico emitindo fumaça e cheiro de queimado.", 0, 2, True, True),
    ("Computadores de um setor estão sem acesso à rede, prejudicando o trabalho.", 0, 1, False, False),
    ("Solicito substituição de um teclado com uma tecla defeituosa.", 0, 0, False, False),
    ("Vazamento de gás identificado próximo à cozinha.", 0, 2, True, True),
    ("Foi verificado que não há vazamento de gás. É apenas necessário substituir uma etiqueta de identificação.",
     0, 0, False, False),
    ("Solicito um pequeno ajuste em uma gaveta, sem qualquer perigo aparente.", 1, 0, False, True),
    ("Fiação elétrica energizada exposta próxima a uma poça de água.", 0, 2, True, True),
])
def test_casos_obrigatorios_sem_chave(descricao, risco, prioridade, alerta, contradicao):
    with patch("triagem.requests.post") as post:
        resposta = classificar(descricao, complementos(risco))
    post.assert_not_called()
    assert resposta["prioridade"] == prioridade
    assert resposta["rotulo"] == ROTULOS[prioridade]
    assert resposta["alerta_seguranca"] is alerta
    assert resposta["contradicao"] is contradicao
    if contradicao:
        assert resposta["revisao_necessaria"]
    assert resposta["justificativa"] and resposta["fatores"]
    assert resposta["origem"] == "analise_local"
    assert resposta["confianca"] is None


@pytest.mark.parametrize("descricao", [
    "Fio do poste de alimentação elétrica, caido no chão próximo uma poça de água.",
    "Cabo de energia se rompeu e está pendurado sobre a passagem dos alunos.",
    "Um fio de alta tensão está no solo, perto do portão.",
])
def test_condutor_em_posicao_de_risco_independe_da_resposta_negativa(descricao):
    resultado = classificar(descricao, complementos())
    assert resultado["prioridade"] == 2
    assert resultado["alerta_seguranca"]
    assert resultado["contradicao"]
    assert resultado["revisao_necessaria"]


@pytest.mark.parametrize("descricao,esperado", [
    ("Não há um vazamento de gás. Solicito trocar uma etiqueta.", 0),
    ("Vazamento de gás da semana passada foi reparado. Solicito manutenção preventiva.", 0),
    ("Se houver vazamento de gás, as regras são claras. Solicito manutenção preventiva.", 0),
    ("Treinamento sobre 'vazamento de gás'. Solicito um pequeno ajuste.", 0),
    ("Fio exposto ao sol, sem risco. Solicito manutenção preventiva.", 0),
    ("Fios expostos e desenergizados. Solicito inspeção.", 0),
    ("Os fios não estão expostos. Solicito manutenção preventiva.", 0),
    ("A fiação está energizada, exposta junto a uma poça.", 2),
    ("O quadro elétrico não está emitindo fumaça. Solicito manutenção preventiva.", 0),
    ("Não foi descartado vazamento de gás próximo à cozinha.", 2),
    ("Não há vazamento de gás, mas há odor de gás próximo ao fogão.", 2),
    ("O painel elétrico foi desligado, mas está emitindo fumaça.", 2),
    ("Não há falta de água em toda a escola. Solicito manutenção preventiva.", 0),
    ("Falta de água em toda a escola, interrompendo banheiros e refeições.", 2),
    ("Estamos sem água no hospital inteiro.", 2),
    ("O fio do poste não caiu no chão. Solicitamos manutenção preventiva.", 0),
    ("O cabo de energia caiu ontem e já foi recolhido. Solicito manutenção preventiva.", 0),
    ("O cabo de rede caiu no chão da sala. Solicito um pequeno ajuste.", 0),
])
def test_contexto_polaridade_e_continuacao(descricao, esperado):
    assert classificar(descricao, complementos())["prioridade"] == esperado


@pytest.mark.parametrize("descricao,risco", [
    ("O equipamento parou de funcionar.", 0),
    ("O equipamento parou de funcionar.", 1),
    ("Não há água no bebedouro de um corredor, os outros funcionam.", 0),
])
def test_interrupcao_essencial_sem_criticidade_comprovada_pede_revisao(descricao, risco):
    resultado = classificar(descricao, complementos(risco, servico_essencial_interrompido=1))
    assert resultado["prioridade"] == 1
    assert resultado["revisao_necessaria"]
    assert not resultado["alerta_seguranca"]


def resposta_ia(**dados):
    proposta = {"prioridade": 1, "risco_critico": "ausente",
                "justificativa": "Há prejuízo localizado no serviço do setor.",
                "fatores": ["Processo operacional indisponível"], "confianca": "media",
                "revisao_necessaria": False, "fonte_critica": "nenhuma", "evidencia_critica": None,
                **dados}
    resposta = Mock()
    resposta.json.return_value = {"choices": [{"message": {"content": json.dumps(proposta)}}]}
    return resposta


def test_semantica_reconhece_impacto_alem_das_regras():
    descricao = "As requisições do almoxarifado ficaram represadas com a indisponibilidade do coletor."
    assert classificar(descricao, complementos())["prioridade"] == 0
    foto = b"jpeg-normalizado-para-o-teste"
    with patch("triagem.requests.post", return_value=resposta_ia()) as post:
        resultado = classificar(descricao, complementos(), foto, chave="chave-ficticia")
    assert resultado["prioridade"] == 1
    assert resultado["origem"] == "ia_semantica"
    assert resultado["confianca"] == "media"
    requisicao = post.call_args.kwargs
    conteudo = requisicao["json"]["messages"][1]["content"]
    payload = json.loads(conteudo[0]["text"])
    assert payload["descricao"] == descricao
    assert payload["informacoes_complementares"]["risco_iminente_a_vida"] == 0
    assert conteudo[1]["image_url"]["url"] == "data:image/jpeg;base64," + base64.b64encode(foto).decode()
    assert requisicao["json"]["response_format"]["json_schema"]["strict"]


def test_protecao_critica_prevalece_sobre_proposta_semantica_inadequada():
    with patch("triagem.requests.post", return_value=resposta_ia(prioridade=0)):
        resultado = classificar("Quadro elétrico emitindo fumaça.", complementos(), chave="chave-ficticia")
    assert resultado["prioridade"] == 2
    assert resultado["alerta_seguranca"] and resultado["contradicao"] and resultado["revisao_necessaria"]
    assert resultado["confianca"] is None
    assert "regra crítica" in resultado["justificativa"]


def test_cabo_caido_ainda_nao_desligado_mantem_alerta():
    resultado = classificar("Cabo de energia caiu e ainda não foi desligado.", complementos())
    assert resultado["prioridade"] == 2
    assert resultado["alerta_seguranca"] and resultado["revisao_necessaria"]


def test_interrupcao_essencial_informada_com_proposta_semantica_baixa_pede_revisao():
    with patch("triagem.requests.post", return_value=resposta_ia(prioridade=0)):
        resultado = classificar("O equipamento parou de funcionar.",
                                complementos(servico_essencial_interrompido=1), chave="chave-ficticia")
    assert resultado["prioridade"] == 1
    assert resultado["revisao_necessaria"]
    assert not resultado["alerta_seguranca"]
    assert resultado["confianca"] is None


def test_perigo_semantico_novo_com_evidencia_aplica_limite_critico():
    descricao = "O contrapeso da plataforma se soltou e balança sobre a passagem dos alunos."
    with patch("triagem.requests.post", return_value=resposta_ia(
        prioridade=1, risco_critico="suspeito", fonte_critica="descricao",
        evidencia_critica="balança sobre a passagem dos alunos",
    )):
        resultado = classificar(descricao, complementos(), chave="chave-ficticia")
    assert resultado["prioridade"] == 2
    assert resultado["origem"] == "ia_semantica"
    assert resultado["alerta_seguranca"] and resultado["revisao_necessaria"]


@pytest.mark.parametrize("descricao,fonte,evidencia", [
    ("Não há vazamento de gás. É necessário substituir uma etiqueta.", "descricao", "vazamento de gás"),
    ("Solicito um pequeno ajuste em uma gaveta.", "nenhuma", None),
    ("Solicito um pequeno ajuste em uma gaveta.", "descricao", "resposta de risco iminente: Sim"),
    ("Solicito um pequeno ajuste em uma gaveta.", "foto", "Fiação exposta"),
])
def test_proposta_critica_sem_fonte_valida_nao_sobrescreve_o_contexto(descricao, fonte, evidencia):
    with patch("triagem.requests.post", return_value=resposta_ia(
        prioridade=2, risco_critico="confirmado", fonte_critica=fonte, evidencia_critica=evidencia,
    )):
        resultado = classificar(descricao, complementos(1), chave="chave-ficticia")
    assert resultado["prioridade"] == 0
    assert resultado["origem"] == "analise_local"
    assert resultado["revisao_necessaria"]
    assert not resultado["alerta_seguranca"]


def test_falha_do_provedor_mantem_protecao_e_informa_foto_sem_analise():
    with patch("triagem.requests.post", side_effect=requests.Timeout("falha simulada")):
        resultado = classificar("Vazamento de gás identificado.", complementos(), b"jpeg", chave="chave-ficticia")
    assert resultado["prioridade"] == 2 and resultado["alerta_seguranca"]
    assert resultado["origem"] == "analise_local" and resultado["revisao_necessaria"]
    assert "não interpretou a fotografia" in resultado["justificativa"]
