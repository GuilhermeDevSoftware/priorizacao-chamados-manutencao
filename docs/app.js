import { CAMPOS, NOMES, validarCampos, preverArvore } from './engine.js';

const form = document.querySelector('#formulario');
const analisar = document.querySelector('#analisar');
const status = document.querySelector('#form-status');
const extrair = document.querySelector('#extrair');
const extracaoStatus = document.querySelector('#extracao-status');
const confirmacaoBox = document.querySelector('#confirmacao-box');
const confirmar = document.querySelector('#confirmar-campos');
const descricao = document.querySelector('#descricao');
const vazio = document.querySelector('#resultado-vazio');
const resultado = document.querySelector('#resultado');
let configuracao;
let modelo;
let sugestoesPendentes = false;
let processando = false;

const exemplos = {
  macaneta: {
    descricao: 'Maçaneta frouxa em uma sala desocupada, sem risco identificado e sem interromper atividades.',
    risco_seguranca: 0, servico_essencial_interrompido: 0,
    pessoas_afetadas: 0, dias_aguardando: 1, recorrente: 0
  },
  agua: {
    descricao: 'Falta de água em toda a escola, interrompendo o uso dos banheiros e o preparo das refeições.',
    risco_seguranca: 0, servico_essencial_interrompido: 1,
    pessoas_afetadas: 250, dias_aguardando: 0, recorrente: 0
  },
  fiacao: {
    descricao: 'Fiação exposta em um corredor de pouca circulação, com risco de choque para quem passar pelo local.',
    risco_seguranca: 1, servico_essencial_interrompido: 0,
    pessoas_afetadas: 2, dias_aguardando: 0, recorrente: 0
  }
};

function definirProcessando(ativo) {
  processando = ativo;
  analisar.disabled = ativo;
  extrair.disabled = ativo || !configuracao?.extracao_habilitada;
  for (const controle of form.querySelectorAll('input, select, textarea')) controle.disabled = ativo;
  document.querySelector('#limpar').disabled = ativo;
  for (const botao of document.querySelectorAll('[data-exemplo]')) botao.disabled = ativo;
}

function atualizarContador() {
  document.querySelector('#contador').textContent = `${descricao.value.length} / 2000`;
}

function limparErros() {
  for (const campo of CAMPOS) {
    document.querySelector(`#erro-${campo}`).textContent = '';
    document.getElementById(campo).removeAttribute('aria-invalid');
  }
  status.textContent = '';
}

function mostrarErros(erros) {
  for (const [campo, mensagem] of Object.entries(erros)) {
    const elemento = document.getElementById(campo);
    const erro = document.querySelector(`#erro-${campo}`);
    if (elemento && erro) {
      elemento.setAttribute('aria-invalid', 'true');
      erro.textContent = mensagem;
    }
  }
  const primeiro = CAMPOS.find(campo => erros[campo]);
  if (primeiro) document.getElementById(primeiro).focus();
}

function marcarAlteracao(evento) {
  if (evento?.target === confirmar) return;
  if (!resultado.hidden) document.querySelector('#resultado-atualizacao').hidden = false;
  if (sugestoesPendentes) confirmar.checked = false;
}

function preencher(campos) {
  for (const nome of CAMPOS) {
    document.getElementById(nome).value = campos[nome] === null || campos[nome] === undefined ? '' : String(campos[nome]);
  }
}

function obterEntrada() {
  return Object.fromEntries(CAMPOS.map(nome => [nome, document.getElementById(nome).value]));
}

async function requisitar(url, opcoes = {}) {
  const controller = new AbortController();
  const limite = setTimeout(() => controller.abort(), 30000);
  try {
    const resposta = await fetch(url, { ...opcoes, signal: controller.signal });
    let dados;
    try { dados = await resposta.json(); }
    catch { throw new Error('O serviço não devolveu uma resposta JSON válida. Tente novamente.'); }
    if (!resposta.ok) {
      const erro = new Error(dados.erro || 'Não foi possível concluir a solicitação.');
      erro.detalhes = dados.detalhes;
      throw erro;
    }
    return dados;
  } catch (erro) {
    if (erro.name === 'AbortError') throw new Error('O serviço demorou para responder. A entrada manual continua disponível.');
    throw erro;
  } finally {
    clearTimeout(limite);
  }
}

function exibirResultado(classe, campos) {
  if (classe !== 0 && classe !== 1) throw new Error('O serviço retornou uma classe inválida.');
  document.querySelector('#resultado-titulo').textContent = classe === 1 ? '1 · Prioritário' : '0 · Normal';
  document.querySelector('#resultado-destaque').classList.toggle('priority', classe === 1);
  document.querySelector('#resultado-explicacao').textContent = classe === 1
    ? 'O modelo sugere priorizar a avaliação deste chamado pelo responsável pela manutenção.'
    : 'O modelo sugere atendimento na programação habitual, após revisão do responsável pela manutenção.';
  document.querySelector('#resumo-descricao').textContent = descricao.value.trim() || 'Descrição não informada.';
  const lista = document.querySelector('#resumo-campos');
  lista.replaceChildren();
  for (const campo of CAMPOS) {
    const linha = document.createElement('div');
    const nome = document.createElement('dt');
    const valor = document.createElement('dd');
    nome.textContent = NOMES[campo];
    valor.textContent = ['pessoas_afetadas', 'dias_aguardando'].includes(campo)
      ? new Intl.NumberFormat('pt-BR').format(campos[campo])
      : campos[campo] === 1 ? 'Sim' : 'Não';
    linha.append(nome, valor);
    lista.append(linha);
  }
  vazio.hidden = true;
  resultado.hidden = false;
  document.querySelector('#resultado-atualizacao').hidden = true;
  status.textContent = 'Análise concluída. Revise a sugestão e o resumo do chamado.';
  resultado.focus();
}

for (const botao of document.querySelectorAll('[data-exemplo]')) {
  botao.addEventListener('click', () => {
    if (processando) return;
    const exemplo = exemplos[botao.dataset.exemplo];
    preencher(exemplo);
    descricao.value = exemplo.descricao;
    atualizarContador();
    limparErros();
    sugestoesPendentes = false;
    confirmacaoBox.hidden = true;
    confirmar.checked = false;
    extracaoStatus.textContent = '';
    marcarAlteracao();
    status.textContent = 'Exemplo fictício preenchido. Revise os campos e clique em Analisar chamado.';
  });
}

form.addEventListener('input', evento => {
  atualizarContador();
  marcarAlteracao(evento);
  if (CAMPOS.includes(evento.target.id)) {
    evento.target.removeAttribute('aria-invalid');
    document.querySelector(`#erro-${evento.target.id}`).textContent = '';
  }
});
form.addEventListener('change', marcarAlteracao);

form.addEventListener('submit', async evento => {
  evento.preventDefault();
  if (processando) return;
  limparErros();
  const validacao = validarCampos(obterEntrada());
  if (!validacao.valido) {
    status.textContent = 'Revise os campos indicados. Nenhuma previsão foi realizada.';
    mostrarErros(validacao.erros);
    return;
  }
  if (sugestoesPendentes && !confirmar.checked) {
    status.textContent = 'Revise os campos e marque a confirmação das sugestões antes de analisar.';
    confirmar.focus();
    return;
  }
  if (!configuracao) {
    status.textContent = 'A configuração não foi carregada. Atualize a página para tentar novamente.';
    return;
  }
  definirProcessando(true);
  status.textContent = 'Analisando o chamado…';
  try {
    let classe;
    if (configuracao.modo === 'api') {
      const resposta = await requisitar('./api/prever', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...validacao.campos, descricao: descricao.value.trim() })
      });
      classe = resposta.classe;
    } else {
      classe = preverArvore(modelo, validacao.campos);
    }
    exibirResultado(classe, validacao.campos);
  } catch (erro) {
    definirProcessando(false);
    status.textContent = `Não foi possível analisar. ${erro.message}`;
    if (erro.detalhes) mostrarErros(erro.detalhes);
  } finally {
    definirProcessando(false);
  }
});

extrair.addEventListener('click', async () => {
  if (processando || !configuracao?.extracao_habilitada) return;
  if (!descricao.value.trim()) {
    extracaoStatus.textContent = 'Escreva uma descrição fictícia para solicitar sugestões.';
    descricao.focus();
    return;
  }
  limparErros();
  definirProcessando(true);
  extracaoStatus.textContent = 'Solicitando sugestões de campos. Aguarde…';
  try {
    const resposta = await requisitar('./api/extrair', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ descricao: descricao.value.trim() })
    });
    if (!resposta.campos || resposta.confirmacao_necessaria !== true) {
      throw new Error('Resposta de extração inválida. Preencha os campos manualmente.');
    }
    const campos = {};
    for (const nome of CAMPOS) {
      const valor = resposta.campos[nome];
      const individual = validarCampos({ ...Object.fromEntries(CAMPOS.map(campo => [campo, 0])), [nome]: valor });
      campos[nome] = individual.valido ? individual.campos[nome] : null;
    }
    preencher(campos);
    sugestoesPendentes = true;
    confirmacaoBox.hidden = false;
    confirmar.checked = false;
    marcarAlteracao();
    const desconhecidos = CAMPOS.filter(nome => campos[nome] === null);
    extracaoStatus.textContent = `${resposta.origem || 'Sugestões da IA'}. ${desconhecidos.length
      ? `Complete as informações desconhecidas: ${desconhecidos.map(nome => NOMES[nome].toLowerCase()).join(', ')}. `
      : ''}Revise todos os campos e confirme antes de analisar.`;
    definirProcessando(false);
    document.getElementById(desconhecidos[0] || CAMPOS[0]).focus();
  } catch (erro) {
    extracaoStatus.textContent = `${erro.message} Você pode continuar preenchendo os campos manualmente.`;
  } finally {
    definirProcessando(false);
  }
});

document.querySelector('#limpar').addEventListener('click', () => {
  if (processando) return;
  form.reset();
  limparErros();
  atualizarContador();
  sugestoesPendentes = false;
  confirmacaoBox.hidden = true;
  extracaoStatus.textContent = '';
  vazio.hidden = false;
  resultado.hidden = true;
  descricao.focus();
});

async function iniciar() {
  analisar.disabled = true;
  try {
    configuracao = await requisitar('./config.json', { cache: 'no-store' });
    if (!['api', 'demonstracao'].includes(configuracao.modo)) throw new Error('Modo de funcionamento inválido.');
    configuracao.extracao_habilitada = configuracao.modo === 'api' && configuracao.extracao_habilitada === true;
    if (configuracao.modo === 'demonstracao') {
      modelo = await requisitar('./modelo/arvore.json');
      // Valida o contrato do artefato antes de habilitar o formulário.
      preverArvore(modelo, Object.fromEntries(CAMPOS.map(nome => [nome, 0])));
      document.querySelector('#modo-titulo').textContent = 'Modo demonstração';
      document.querySelector('#modo-descricao').textContent = 'A árvore treinada é carregada de um arquivo JSON e executada neste navegador, sem enviar o chamado a uma API.';
      document.querySelector('#extracao-info').textContent = 'A extração com IA está disponível apenas na versão Flask configurada.';
    } else {
      document.querySelector('#modo-titulo').textContent = 'Modo local · API Flask';
      document.querySelector('#modo-descricao').textContent = 'A análise usa a API Flask local e a mesma árvore treinada exportada para a demonstração.';
      if (configuracao.extracao_habilitada) {
        document.querySelector('#extracao-info').textContent = 'Ao clicar, a descrição fictícia será enviada à OpenAI. Revise e confirme todas as sugestões.';
        document.querySelector('#privacy-text').textContent = 'Sem armazenamento de chamados. A extração opcional envia a descrição ao provedor de IA.';
      } else {
        document.querySelector('#extracao-info').textContent = 'Extração não configurada no servidor. Preencha os campos manualmente.';
      }
    }
    extrair.disabled = !configuracao.extracao_habilitada;
    analisar.disabled = false;
  } catch (erro) {
    configuracao = undefined;
    status.textContent = `Não foi possível carregar a ferramenta. ${erro.message} Atualize a página para tentar novamente.`;
    document.querySelector('#modo-titulo').textContent = 'Carregamento indisponível';
    document.querySelector('#modo-descricao').textContent = 'A configuração ou o modelo não pôde ser carregado. Verifique a conexão e os arquivos publicados.';
    analisar.disabled = true;
  }
}

iniciar();
