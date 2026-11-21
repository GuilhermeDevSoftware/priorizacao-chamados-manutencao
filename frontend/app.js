import { CAMPOS, NOMES, validarCampos } from './engine.js';

const $ = seletor => document.querySelector(seletor);
const form = $('#formulario');
const equipes = ['TI', 'Elétrica', 'Hidráulica', 'Triagem geral'];
const rotulos = ['Não prioritário', 'Intermediário', 'Prioritário'];
const confiancas = { baixa: 'Baixa', media: 'Média', alta: 'Alta' };
let configuracao, analiseAtual = null, comprovante = null, fotoArquivo = null, fotoURL = null;
let processando = false, sugestoesPendentes = false, cadastroSalvo = false;
let exemplosPainel = [], detalheAtual = null, versaoPainel = 0, versaoFoto = 0, versaoDetalhe = 0;
let visaoPainel = 'pendentes', assinaturaLista = '', fotoCarregando = false, atualizandoChamado = false;
let consultasPainel = 0;
const exemplos = {
  fiacao: {
    descricao: 'Fiação elétrica energizada exposta próxima a uma poça de água.', local: 'Corredor fictício',
    equipe: 'Elétrica', valores: [0, 0, 2, 0, 0], prioridade: 2, alerta: true, contradicao: true,
    justificativa: 'A associação de fiação energizada exposta com água indica risco grave de choque, apesar da resposta negativa.'
  },
  fumaca: {
    descricao: 'Quadro elétrico emitindo fumaça e cheiro de queimado.', local: 'Sala técnica fictícia',
    equipe: 'Elétrica', valores: [0, 0, 2, 0, 0], prioridade: 2, alerta: true, contradicao: true,
    justificativa: 'A fumaça e o cheiro de queimado no quadro indicam risco de incêndio, apesar da resposta negativa.'
  },
  rede: {
    descricao: 'Computadores de um setor estão sem acesso à rede, prejudicando o trabalho.', local: 'Secretaria fictícia',
    equipe: 'TI', valores: [0, 0, 8, 0, 0], prioridade: 1,
    justificativa: 'A falha afeta o trabalho de um setor. A urgência pode mudar se a rede sustentar um serviço essencial.'
  },
  teclado: {
    descricao: 'Solicito substituição de um teclado com uma tecla defeituosa.', local: 'Biblioteca fictícia',
    equipe: 'TI', valores: [0, 0, 1, 0, 0], prioridade: 0,
    justificativa: 'Trata-se da substituição de um periférico, sem indício de perigo ou interrupção importante no relato.'
  },
  gas: {
    descricao: 'Vazamento de gás identificado próximo à cozinha.', local: 'Cozinha fictícia',
    equipe: 'Triagem geral', valores: [0, 0, 4, 0, 0], prioridade: 2, alerta: true, contradicao: true,
    justificativa: 'O relato afirma um vazamento de gás ocorrido perto da cozinha, com perigo potencial à integridade física.'
  },
  negacao: {
    descricao: 'Foi verificado que não há vazamento de gás. É apenas necessário substituir uma etiqueta de identificação.', local: 'Cozinha fictícia',
    equipe: 'Triagem geral', valores: [0, 0, 1, 0, 0], prioridade: 0,
    justificativa: 'O vazamento foi descartado no relato. A solicitação atual é a troca de uma etiqueta de identificação.'
  },
  gaveta: {
    descricao: 'Solicito um pequeno ajuste em uma gaveta, sem qualquer perigo aparente.', local: 'Escritório fictício',
    equipe: 'Triagem geral', valores: [1, 0, 1, 0, 0], prioridade: 0, contradicao: true,
    justificativa: 'O ajuste descrito é de rotina. Confirme a resposta sobre risco iminente, pois ela contradiz o relato.'
  }
};

function persistente() { return configuracao?.modo === 'api' && configuracao.armazenamento_habilitado === true; }
function processar(ativo) {
  processando = ativo;
  for (const controle of form.querySelectorAll('input, select, textarea, button')) controle.disabled = ativo;
  for (const botao of document.querySelectorAll('[data-exemplo]')) botao.disabled = ativo;
  $('#analisar').disabled = ativo || fotoCarregando || !configuracao;
  $('#extrair').disabled = ativo || fotoCarregando || !persistente();
  $('#salvar').disabled = ativo || fotoCarregando || !persistente() || cadastroSalvo;
}
function contador() { $('#contador').textContent = `${$('#descricao').value.length} / 2000`; }
function limparErros() {
  for (const campo of [...CAMPOS, 'descricao', 'local', 'equipe_confirmada']) {
    const el = document.getElementById(campo);
    el?.removeAttribute('aria-invalid');
    const msg = document.getElementById(`erro-${campo}`); if (msg) msg.textContent = '';
  }
  $('#form-status').textContent = '';
}
function mostrarErros(erros) {
  let primeiro;
  for (const [campo, mensagem] of Object.entries(erros || {})) {
    const el = document.getElementById(campo), msg = document.getElementById(`erro-${campo}`);
    if (el) { el.setAttribute('aria-invalid', 'true'); primeiro ||= el; }
    if (msg) msg.textContent = mensagem;
  }
  primeiro?.focus();
}
function alterado(evento) {
  if (evento?.target?.id === 'confirmar-campos') return;
  const campo = evento?.target?.id;
  if (!campo || ['descricao', 'foto', 'foto-camera', ...CAMPOS].includes(campo)) comprovante = null;
  $('#confirmar-campos').checked = false;
  cadastroSalvo = false;
  if (!$('#resultado').hidden) $('#resultado-atualizacao').hidden = false;
  if (['descricao', 'foto', 'foto-camera'].includes(campo)) invalidarAnalise();
  if (!processando) processar(false);
}
function invalidarAnalise() {
  analiseAtual = null; sugestoesPendentes = false;
  $('#analise-detalhes').hidden = true;
  $('#equipe-sugerida').textContent = 'Triagem geral';
  $('#justificativa-equipe').textContent = 'Descrição ou foto alterada. Revise a equipe ou solicite novas sugestões.';
  $('#equipe_confirmada').value = '';
  $('#extracao-status').textContent = '';
}
function obterCampos() { return Object.fromEntries(CAMPOS.map(campo => [campo, document.getElementById(campo).value])); }
function preencher(campos) {
  for (const nome of CAMPOS) document.getElementById(nome).value = campos[nome] == null ? '' : String(campos[nome]);
}
async function requisitar(url, opcoes = {}) {
  const controle = new AbortController(), timer = setTimeout(() => controle.abort(), 35000);
  try {
    const r = await fetch(url, { ...opcoes, signal: controle.signal });
    let dados;
    try { dados = await r.json(); } catch { throw new Error('O serviço não devolveu uma resposta válida.'); }
    if (!r.ok) { const erro = new Error(dados.erro || 'Não foi possível concluir.'); erro.detalhes = dados.detalhes; erro.status = r.status; throw erro; }
    return dados;
  } catch (erro) {
    if (erro.name === 'AbortError') throw new Error('O serviço demorou para responder. Continue pelo preenchimento manual.');
    throw erro;
  } finally { clearTimeout(timer); }
}
function retirarFoto(avisar = true) {
  versaoFoto++;
  fotoCarregando = false;
  if (fotoURL) URL.revokeObjectURL(fotoURL);
  fotoURL = null; fotoArquivo = null;
  $('#foto').value = ''; $('#foto-camera').value = '';
  $('#foto-box').hidden = true; $('#foto-previa').removeAttribute('src');
  if (avisar) { $('#foto-status').textContent = 'Foto removida. O chamado pode ser enviado somente com descrição.'; invalidarAnalise(); alterado(); }
}
async function escolherFoto(evento) {
  const arquivo = evento.target.files?.[0];
  if (!arquivo) return;
  retirarFoto(false); invalidarAnalise(); alterado();
  const versao = versaoFoto;
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(arquivo.type)) {
    $('#foto-status').textContent = 'Formato inválido. Escolha uma imagem JPG, PNG ou WebP.'; return;
  }
  if (arquivo.size > 5 * 1024 * 1024) { $('#foto-status').textContent = 'A foto excede 5 MiB. Escolha um arquivo menor.'; return; }
  const url = URL.createObjectURL(arquivo), imagem = new Image(); imagem.src = url;
  fotoCarregando = true; processar(false);
  try {
    await imagem.decode();
    if (versao !== versaoFoto) { URL.revokeObjectURL(url); return; }
    if (imagem.naturalWidth * imagem.naturalHeight > 25000000) throw new Error('A foto excede 25 megapixels. Escolha uma resolução menor.');
    fotoArquivo = arquivo; fotoURL = url;
    comprovante = null;
    $('#foto-previa').src = url; $('#foto-box').hidden = false;
    $('#foto-status').textContent = 'Foto selecionada para prévia. Ela só será gravada ao salvar pelo Flask.';
  } catch (erro) { URL.revokeObjectURL(url); if (versao !== versaoFoto) return; $('#foto-status').textContent = erro.message.startsWith('A foto') ? erro.message : 'Não foi possível abrir a imagem. Escolha uma foto válida.'; }
  finally { if (versao === versaoFoto) { fotoCarregando = false; if (!processando) processar(false); } }
}
$('#foto').addEventListener('change', escolherFoto);
$('#foto-camera').addEventListener('change', escolherFoto);
$('#remover-foto').addEventListener('click', () => retirarFoto());
window.addEventListener('pagehide', () => { if (fotoURL) URL.revokeObjectURL(fotoURL); });

function exibirResultado(classificacao, campos, registro = null) {
  const nivel = classificacao.prioridade;
  if (![0, 1, 2].includes(nivel)) throw new Error('A triagem devolveu uma prioridade inválida.');
  $('#resultado-titulo').textContent = rotulos[nivel];
  $('#resultado-destaque').className = `result-banner tier-${nivel}`;
  $('#resultado-explicacao').textContent = classificacao.justificativa;
  mostrarTriagem($('#resultado-triagem'), classificacao);
  $('#resumo-descricao').textContent = $('#descricao').value.trim() || 'Descrição não informada.';
  const lista = $('#resumo-campos'); lista.replaceChildren();
  for (const campo of CAMPOS) {
    const linha = document.createElement('div'), dt = document.createElement('dt'), dd = document.createElement('dd');
    dt.textContent = NOMES[campo]; dd.textContent = ['pessoas_afetadas', 'dias_aguardando'].includes(campo) ? new Intl.NumberFormat('pt-BR').format(campos[campo]) : campos[campo] === 1 ? 'Sim' : 'Não';
    linha.append(dt, dd); lista.append(linha);
  }
  $('#resultado-equipe').textContent = registro?.equipe_confirmada || $('#equipe_confirmada').value || 'A confirmar';
  $('#resultado-status').textContent = registro ? situacao(registro.status) : 'Ainda não cadastrado';
  $('#resultado-vazio').hidden = true; $('#resultado').hidden = false;
  $('#resultado-atualizacao').hidden = true;
  $('#form-status').textContent = registro ? `Chamado #${registro.id} inserido na fila. Situação ${situacao(registro.status)}.` : 'Análise concluída. Revise os dados antes de cadastrar.';
  $('#resultado').focus();
}
for (const botao of document.querySelectorAll('[data-exemplo]')) botao.addEventListener('click', () => {
  if (processando) return;
  retirarFoto(false); invalidarAnalise();
  const ex = exemplos[botao.dataset.exemplo];
  preencher(Object.fromEntries(CAMPOS.map((nome, i) => [nome, ex.valores[i]])));
  $('#descricao').value = ex.descricao; $('#local').value = ex.local;
  $('#equipe-sugerida').textContent = ex.equipe; $('#equipe_confirmada').value = ex.equipe;
  $('#justificativa-equipe').textContent = 'Equipe preenchida pelo exemplo fictício. Confirme ou altere após revisar.';
  $('#foto-status').textContent = ''; limparErros(); contador(); alterado();
  $('#form-status').textContent = 'Exemplo fictício preenchido. Revise os campos e analise o chamado.';
});
form.addEventListener('input', evento => { contador(); alterado(evento); const msg = document.getElementById(`erro-${evento.target.id}`); if (msg) msg.textContent = ''; evento.target.removeAttribute('aria-invalid'); });
form.addEventListener('change', evento => { if (!['foto', 'foto-camera'].includes(evento.target.id)) alterado(evento); });
form.addEventListener('submit', async evento => {
  evento.preventDefault(); if (processando || fotoCarregando) return; limparErros();
  const validacao = validarCampos(obterCampos());
  const descricao = $('#descricao').value.trim();
  if (!descricao || descricao.length > 2000) validacao.erros.descricao = 'Informe uma descrição de até 2.000 caracteres.';
  if (Object.keys(validacao.erros).length) { mostrarErros(validacao.erros); $('#form-status').textContent = 'Revise os campos indicados para analisar o chamado.'; return; }
  if (sugestoesPendentes && !$('#confirmar-campos').checked) { $('#form-status').textContent = 'Revise os campos e marque a confirmação das sugestões antes de analisar.'; $('#confirmar-campos').focus(); return; }
  if (!configuracao) return;
  processar(true); $('#form-status').textContent = 'Analisando o chamado…';
  try {
    let classificacao;
    if (persistente()) {
      classificacao = await requisitar('./api/classificar', { method: 'POST', body: formularioComFoto({ descricao, ...validacao.campos }) });
      comprovante = classificacao.comprovante || null;
    } else {
      const exemplo = Object.values(exemplos).find(item => item.descricao === descricao && CAMPOS.every((c, i) => item.valores[i] === validacao.campos[c]));
      if (!exemplo || fotoArquivo) throw new Error('Escolha um dos exemplos fictícios para pré-visualizar a triagem. A análise de uma nova descrição ou foto exige o Flask.');
      classificacao = {
        prioridade: exemplo.prioridade, justificativa: exemplo.justificativa, origem: 'demonstracao',
        contradicao: exemplo.contradicao, revisao_necessaria: exemplo.contradicao, alerta_seguranca: exemplo.alerta
      };
    }
    exibirResultado(classificacao, validacao.campos);
  } catch (erro) { processar(false); $('#form-status').textContent = erro.message; mostrarErros(erro.detalhes); }
  finally { processar(false); }
});
function formularioComFoto(payload) {
  const dados = new FormData();
  dados.append('dados', JSON.stringify(payload));
  if (fotoArquivo) dados.append('foto', fotoArquivo);
  return dados;
}
function mostrarAnalise(analise) {
  const caixa = $('#analise-detalhes'); caixa.replaceChildren();
  const titulo = document.createElement('strong'); titulo.textContent = analise.tipo_defeito || 'Sugestão de encaminhamento'; caixa.append(titulo);
  for (const [rotulo, valores] of [['Indícios observados', analise.indicios_observados], ['Precisa confirmar', analise.informacoes_confirmar]]) {
    if (!Array.isArray(valores) || !valores.length) continue;
    const p = document.createElement('p'); p.textContent = `${rotulo}: ${valores.join('; ')}`; caixa.append(p);
  }
  const fonte = document.createElement('p'); fonte.textContent = analise.origem === 'ia_multimodal' ? 'Sugestões da IA. A descrição e a eventual foto foram enviadas ao provedor; revise todas as informações.' : 'Regra textual local. A foto não foi interpretada por IA.'; caixa.append(fonte); caixa.hidden = false;
}
$('#extrair').addEventListener('click', async () => {
  if (processando || fotoCarregando || !persistente()) return;
  if (!$('#descricao').value.trim()) { $('#extracao-status').textContent = 'Escreva uma descrição antes de solicitar sugestões.'; $('#descricao').focus(); return; }
  processar(true); limparErros(); $('#extracao-status').textContent = 'Solicitando sugestões…';
  try {
    const dados = new FormData(); dados.append('descricao', $('#descricao').value.trim()); if (fotoArquivo) dados.append('foto', fotoArquivo);
    const analise = await requisitar('./api/analisar', { method: 'POST', body: dados });
    if (!analise.campos || !equipes.includes(analise.equipe_sugerida) || analise.confirmacao_necessaria !== true) throw new Error('Sugestões inválidas. Continue preenchendo manualmente.');
    const campos = {};
    for (const nome of CAMPOS) {
      const base = Object.fromEntries(CAMPOS.map(c => [c, 0]));
      const manual = validarCampos({ ...base, [nome]: document.getElementById(nome).value });
      const sugerido = validarCampos({ ...base, [nome]: analise.campos[nome] });
      // A resposta sobre risco iminente à vida é declarada pela pessoa.
      campos[nome] = nome !== 'risco_seguranca' && sugerido.valido ? sugerido.campos[nome] : manual.campos[nome] ?? null;
    }
    preencher(campos); analiseAtual = analise; sugestoesPendentes = true;
    comprovante = null;
    $('#equipe-sugerida').textContent = analise.equipe_sugerida;
    $('#justificativa-equipe').textContent = analise.justificativa_equipe;
    $('#equipe_confirmada').value = analise.equipe_sugerida;
    $('#confirmar-campos').checked = false; mostrarAnalise(analise);
    if (!$('#resultado').hidden) $('#resultado-atualizacao').hidden = false;
    cadastroSalvo = false;
    $('#extracao-status').textContent = `${analise.aviso || ''} Revise as sugestões, complete os campos desconhecidos e confirme a equipe.`.trim();
    processar(false); document.getElementById(CAMPOS.find(campo => campos[campo] === null) || CAMPOS[0]).focus();
  } catch (erro) { $('#extracao-status').textContent = `${erro.message} O cadastro manual continua disponível.`; }
  finally { processar(false); }
});
$('#salvar').addEventListener('click', async () => {
  if (processando || fotoCarregando || !persistente() || cadastroSalvo) return; limparErros();
  const validacao = validarCampos(obterCampos()), erros = { ...validacao.erros };
  const descricao = $('#descricao').value.trim(), local = $('#local').value.trim(), equipe = $('#equipe_confirmada').value;
  if (!descricao || descricao.length > 2000) erros.descricao = 'Informe uma descrição de até 2.000 caracteres.';
  if (!local || local.length > 200) erros.local = 'Informe o local com até 200 caracteres.';
  if (!equipes.includes(equipe)) erros.equipe_confirmada = 'Selecione a equipe responsável.';
  if (Object.keys(erros).length) { mostrarErros(erros); $('#form-status').textContent = 'Revise os campos para salvar. Nenhum chamado foi cadastrado.'; return; }
  if (!$('#confirmar-campos').checked) { $('#form-status').textContent = 'Confirme a revisão dos campos e da equipe antes de salvar.'; $('#confirmar-campos').focus(); return; }
  processar(true); $('#form-status').textContent = 'Salvando chamado…';
  try {
    const registro = await requisitar('./api/chamados', { method: 'POST', body: formularioComFoto({
      descricao, local, ...validacao.campos, equipe_confirmada: equipe, confirmado: true,
      ...(analiseAtual ? { analise: analiseAtual } : {}), ...(comprovante ? { comprovante } : {})
    }) });
    cadastroSalvo = true;
    exibirResultado(registro.classificacao, validacao.campos, registro);
    await carregarPainel();
  } catch (erro) { processar(false); $('#form-status').textContent = `Não foi possível salvar. ${erro.message}`; mostrarErros(erro.detalhes); }
  finally { processar(false); }
});
$('#limpar').addEventListener('click', () => {
  if (processando) return;
  form.reset(); retirarFoto(false); invalidarAnalise(); limparErros(); contador(); cadastroSalvo = false;
  comprovante = null;
  $('#foto-status').textContent = ''; $('#resultado-vazio').hidden = false; $('#resultado').hidden = true;
  processar(false); $('#descricao').focus();
});

function criarTexto(tag, texto, classe) {
  const el = document.createElement(tag);
  el.textContent = texto;
  if (classe) el.className = classe;
  return el;
}

const formatoData = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
function dataLegivel(data) {
  const instante = new Date(data);
  return data && Number.isFinite(instante.getTime()) ? formatoData.format(instante) : 'Abertura não informada';
}
function situacao(status) { return status === 'Resolvido' ? 'Concluído' : status; }
function prioridadeAtual(registro) { return registro.prioridade_atual ?? registro.prioridade_sugerida; }
function ordenarFila(registros) {
  return [...registros].sort((a, b) => prioridadeAtual(b) - prioridadeAtual(a)
    || new Date(a.data_abertura) - new Date(b.data_abertura)
    || String(a.id).localeCompare(String(b.id), 'pt-BR', { numeric: true }));
}

function mostrarTriagem(container, classificacao, incluirJustificativa = false) {
  container.replaceChildren();
  if (!classificacao) {
    container.append(criarTexto('p', 'Classificação registrada antes da triagem em três níveis.', 'field-help'));
    return;
  }
  const fontes = { ia_semantica: 'Análise semântica por IA', analise_local: 'Análise contextual local', demonstracao: 'Exemplo fictício' };
  const fonte = fontes[classificacao.origem] ?? 'Análise de triagem';
  const confianca = Object.hasOwn(confiancas, classificacao.confianca) ? confiancas[classificacao.confianca] : null;
  const meta = confianca ? `${fonte} · Confiança informada: ${confianca.toLowerCase()}` : fonte;
  container.append(criarTexto('p', meta, 'triage-source'));
  if (incluirJustificativa) container.append(criarTexto('p', classificacao.justificativa, 'triage-explanation'));
  if (classificacao.alerta_seguranca) {
    const alerta = document.createElement('div');
    alerta.className = 'safety-alert';
    alerta.setAttribute('role', 'alert');
    alerta.append(criarTexto('strong', 'Alerta de segurança'), criarTexto('p', 'Siga os procedimentos de emergência da instituição. A triagem não substitui o atendimento emergencial.'));
    container.append(alerta);
  }
  if (classificacao.revisao_necessaria || classificacao.contradicao) {
    container.append(criarTexto('p', classificacao.contradicao
      ? 'Revisão necessária. A descrição e a resposta sobre risco iminente divergem.'
      : 'Revisão humana necessária. Confirme a gravidade e o impacto antes de encaminhar.', 'triage-review'));
  }
  if (Array.isArray(classificacao.fatores) && classificacao.fatores.length) {
    const lista = document.createElement('ul');
    for (const fator of classificacao.fatores) lista.append(criarTexto('li', fator));
    container.append(criarTexto('strong', 'Fatores da decisão'), lista);
  }
}

function renderizarLista(registros) {
  const lista = $('#lista-chamados');
  const assinatura = JSON.stringify(registros.map(r => [r.id, r.descricao, r.local, r.data_abertura, r.equipe_confirmada, r.status, prioridadeAtual(r), r.prioridade_sugerida, r.classificacao?.revisao_necessaria, r.classificacao?.alerta_seguranca]));
  if (assinatura === assinaturaLista) return;
  assinaturaLista = assinatura;
  const focado = document.activeElement?.closest('#lista-chamados article')?.dataset.chamadoId;
  lista.replaceChildren();
  $('#painel-contagem').textContent = registros.length === 1 ? '1 chamado' : `${registros.length} chamados`;
  if (!registros.length) {
    lista.append(criarTexto('p', 'Nenhum chamado encontrado nesta visualização.', 'panel-empty'));
    if (focado) $('#visao-' + visaoPainel).focus();
    return;
  }
  for (const registro of registros) {
    const nivel = prioridadeAtual(registro);
    const item = document.createElement('article');
    item.className = `ticket-item ticket-tier-${nivel}`;
    item.dataset.chamadoId = String(registro.id);
    const topo = document.createElement('div');
    topo.className = 'ticket-title';
    const resumo = registro.descricao.length > 145 ? registro.descricao.slice(0, 142).trimEnd() + '…' : registro.descricao;
    topo.append(criarTexto('span', `#${registro.id}`, 'ticket-id'), criarTexto('h3', resumo));
    const meta = document.createElement('div');
    meta.className = 'ticket-tags';
    meta.append(criarTexto('span', rotulos[nivel], `tier-badge tier-${nivel}`));
    meta.append(criarTexto('span', `Setor: ${registro.equipe_confirmada}`));
    meta.append(criarTexto('span', situacao(registro.status)));
    if (nivel !== registro.prioridade_sugerida) {
      meta.append(criarTexto('span', `Sugestão original: ${rotulos[registro.prioridade_sugerida]}`));
    }
    if (registro.classificacao?.alerta_seguranca) meta.append(criarTexto('span', 'Alerta de segurança', 'ticket-safety'));
    if (registro.classificacao?.revisao_necessaria) meta.append(criarTexto('span', 'Revisão necessária', 'ticket-review'));
    const botao = criarTexto('button', 'Ver detalhes', 'detail-button');
    botao.type = 'button';
    botao.setAttribute('aria-label', `Ver detalhes do chamado ${registro.id}`);
    botao.addEventListener('click', () => abrirDetalhe(registro.id));
    item.append(topo, criarTexto('p', `${registro.local} · ${dataLegivel(registro.data_abertura)}`, 'ticket-location'), meta, botao);
    lista.append(item);
  }
  if (focado) (botaoDoChamado(focado) || $('#visao-' + visaoPainel)).focus({ preventScroll: true });
}

function botaoDoChamado(id) {
  return [...document.querySelectorAll('#lista-chamados article')]
    .find(el => el.dataset.chamadoId === String(id))?.querySelector('button');
}

async function carregarPainel(silencioso = false) {
  const versao = ++versaoPainel;
  if (!silencioso) $('#painel-status').textContent = 'Carregando chamados…';
  const filtros = { equipe: $('#filtro-equipe').value, prioridade: $('#filtro-prioridade').value, status: $('#filtro-status').value };
  consultasPainel++;
  try {
    let registros, contagens;
    if (persistente()) {
      const query = new URLSearchParams(Object.entries({ visao: visaoPainel, ...filtros }).filter(([, valor]) => valor !== ''));
      const resposta = await requisitar(`./api/chamados?${query}`, { cache: 'no-store' });
      registros = resposta.chamados;
      contagens = resposta.contagens;
    } else {
      const pendentes = exemplosPainel.filter(r => r.status !== 'Resolvido');
      contagens = [0, 1, 2].map(nivel => pendentes.filter(r => prioridadeAtual(r) === nivel).length);
      registros = ordenarFila(exemplosPainel.filter(r => (visaoPainel === 'historico') === (r.status === 'Resolvido')
        && (!filtros.equipe || r.equipe_confirmada === filtros.equipe)
        && (!filtros.prioridade || String(prioridadeAtual(r)) === filtros.prioridade)
        && (!filtros.status || r.status === filtros.status)));
    }
    if (versao !== versaoPainel) return;
    renderizarLista(registros);
    for (const nivel of [0, 1, 2]) $(`#contagem-${nivel}`).textContent = String(contagens?.[nivel] ?? 0);
    $('#painel-status').textContent = '';
  } catch (erro) {
    if (versao === versaoPainel) $('#painel-status').textContent = `Não foi possível atualizar a fila. ${erro.message}`;
  } finally {
    consultasPainel--;
  }
}

const camposRegistro = { prioridade_atual: 'Prioridade', equipe_confirmada: 'Setor', status: 'Situação' };
function valorAuditado(campo, valor) {
  if (campo === 'prioridade_atual') return rotulos[valor] ?? 'A confirmar';
  return campo === 'status' ? situacao(valor) : valor;
}
function mostrarAuditoria(alteracoes) {
  const lista = $('#detalhe-alteracoes');
  lista.replaceChildren();
  $('#detalhe-auditoria').hidden = !alteracoes.length;
  for (const alteracao of alteracoes) {
    const item = document.createElement('li');
    item.append(criarTexto('strong', `${alteracao.responsavel} · ${dataLegivel(alteracao.data)}`));
    for (const campo of Object.keys(camposRegistro)) {
      if (!Object.hasOwn(alteracao.novo, campo)) continue;
      const anterior = valorAuditado(campo, alteracao.anterior[campo]);
      const novo = valorAuditado(campo, alteracao.novo[campo]);
      item.append(criarTexto('p', `${camposRegistro[campo]} mudou de ${anterior} para ${novo}.`));
    }
    if (alteracao.motivo) item.append(criarTexto('p', `Motivo: ${alteracao.motivo}`));
    lista.append(item);
  }
}

function renderizarDetalhe(r, moverFoco) {
  detalheAtual = r;
  $('#detalhe-titulo').textContent = `Chamado #${r.id}`;
  $('#detalhe-descricao').textContent = r.descricao;
  const resumo = $('#detalhe-resumo');
  resumo.replaceChildren();
  const pares = [
    ['Local', r.local], ['Abertura', dataLegivel(r.data_abertura)], ['Situação', situacao(r.status)],
    ['Prioridade atual', rotulos[prioridadeAtual(r)]], ['Prioridade sugerida', rotulos[r.prioridade_sugerida]],
    ['Setor responsável', r.equipe_confirmada], ['Equipe sugerida', r.equipe_sugerida], ['Encaminhamento', r.justificativa_equipe],
    ...CAMPOS.map(campo => [
      campo === 'risco_seguranca' && !r.classificacao ? 'Risco à segurança (registro anterior)' : NOMES[campo],
      ['pessoas_afetadas', 'dias_aguardando'].includes(campo) ? String(r[campo]) : r[campo] ? 'Sim' : 'Não'
    ])
  ];
  for (const [nome, valor] of pares) {
    const div = document.createElement('div');
    div.append(criarTexto('dt', nome), criarTexto('dd', valor));
    resumo.append(div);
  }
  const foto = $('#detalhe-foto');
  foto.hidden = !r.foto_url;
  if (r.foto_url) foto.src = new URL(r.foto_url, document.baseURI).href;
  else foto.removeAttribute('src');
  mostrarTriagem($('#detalhe-triagem'), r.classificacao, true);
  $('#detalhe-analise').replaceChildren();
  if (r.analise) {
    $('#detalhe-analise').append(criarTexto('strong', r.analise.tipo_defeito || 'Informações de apoio'));
    if (r.analise.indicios_observados?.length) $('#detalhe-analise').append(criarTexto('p', r.analise.indicios_observados.join('; ')));
    if (r.analise.informacoes_confirmar?.length) $('#detalhe-analise').append(criarTexto('p', `A confirmar: ${r.analise.informacoes_confirmar.join('; ')}`));
  }
  mostrarAuditoria(r.historico_alteracoes || []);
  $('#detalhe-prioridade').value = String(prioridadeAtual(r));
  $('#detalhe-equipe').value = r.equipe_confirmada;
  $('#detalhe-status').value = r.status;
  $('#detalhe-motivo').value = '';
  $('#detalhe-credencial').value = '';
  const podeAlterar = persistente() && configuracao.administracao_habilitada;
  $('#detalhe-administracao').hidden = !podeAlterar;
  $('#atualizar-chamado').disabled = !podeAlterar || atualizandoChamado;
  $('#detalhe-mensagem').textContent = podeAlterar ? '' : persistente()
    ? 'Configure a credencial administrativa no servidor para registrar alterações.'
    : 'Exemplo fictício. As alterações reais exigem o Flask e a credencial administrativa.';
  $('#detalhe-chamado').hidden = false;
  if (moverFoco) $('#detalhe-chamado').focus();
}

async function abrirDetalhe(id) {
  const versao = ++versaoDetalhe;
  try {
    const r = persistente() ? await requisitar(`./api/chamados/${encodeURIComponent(id)}`, { cache: 'no-store' }) : exemplosPainel.find(ex => ex.id === id);
    if (versao === versaoDetalhe && r) renderizarDetalhe(r, true);
  } catch (erro) {
    if (versao === versaoDetalhe) $('#painel-status').textContent = `Não foi possível consultar o chamado. ${erro.message}`;
  }
}

function selecionarVisao(visao) {
  visaoPainel = visao;
  const historico = visao === 'historico';
  $('#visao-pendentes').setAttribute('aria-pressed', String(!historico));
  $('#visao-historico').setAttribute('aria-pressed', String(historico));
  const status = $('#filtro-status');
  status.value = '';
  for (const opcao of status.options) opcao.hidden = opcao.value !== '' && historico !== (opcao.value === 'Resolvido');
  carregarPainel();
}

for (const id of ['filtro-equipe', 'filtro-prioridade', 'filtro-status']) {
  document.getElementById(id).addEventListener('change', () => carregarPainel());
}
$('#visao-pendentes').addEventListener('click', () => selecionarVisao('pendentes'));
$('#visao-historico').addEventListener('click', () => selecionarVisao('historico'));
$('#atualizar-painel').addEventListener('click', () => carregarPainel());
$('#fechar-detalhe').addEventListener('click', () => {
  const id = detalheAtual?.id;
  versaoDetalhe++;
  $('#detalhe-chamado').hidden = true;
  $('#detalhe-credencial').value = '';
  detalheAtual = null;
  (botaoDoChamado(id) || $('#visao-' + visaoPainel)).focus();
});
$('#atualizar-chamado').addEventListener('click', async () => {
  if (!persistente() || !configuracao.administracao_habilitada || !detalheAtual || atualizandoChamado) return;
  const id = detalheAtual.id;
  const versao = versaoDetalhe;
  const mudancas = {};
  const prioridade = Number($('#detalhe-prioridade').value);
  if (prioridade !== prioridadeAtual(detalheAtual)) mudancas.prioridade_atual = prioridade;
  if ($('#detalhe-equipe').value !== detalheAtual.equipe_confirmada) mudancas.equipe_confirmada = $('#detalhe-equipe').value;
  if ($('#detalhe-status').value !== detalheAtual.status) mudancas.status = $('#detalhe-status').value;
  if (!Object.keys(mudancas).length) {
    $('#detalhe-mensagem').textContent = 'Escolha a prioridade, o setor ou a situação que deseja alterar.';
    return;
  }
  const motivo = $('#detalhe-motivo').value.trim();
  if (Object.hasOwn(mudancas, 'prioridade_atual') && !motivo) {
    $('#detalhe-mensagem').textContent = 'Informe o motivo para alterar a prioridade.';
    $('#detalhe-motivo').focus();
    return;
  }
  if (motivo) mudancas.motivo = motivo;
  const campoCredencial = $('#detalhe-credencial');
  const credencial = campoCredencial.value.trim();
  if (!credencial) {
    $('#detalhe-mensagem').textContent = 'Informe a credencial do responsável.';
    campoCredencial.focus();
    return;
  }
  campoCredencial.value = '';
  atualizandoChamado = true;
  $('#atualizar-chamado').disabled = true;
  $('#detalhe-mensagem').textContent = 'Registrando alteração…';
  try {
    const r = await requisitar(`./api/chamados/${encodeURIComponent(id)}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${credencial}` },
      body: JSON.stringify(mudancas)
    });
    if (versao === versaoDetalhe) {
      renderizarDetalhe(r, false);
      $('#detalhe-mensagem').textContent = 'Alteração registrada no histórico do chamado.';
    }
    await carregarPainel(true);
  } catch (erro) {
    if (versao === versaoDetalhe) {
      $('#detalhe-mensagem').textContent = erro.status === 401 ? 'Credencial recusada. Confira o valor e tente novamente.' : erro.message;
      if (erro.status === 401) campoCredencial.focus();
    }
  } finally {
    atualizandoChamado = false;
    $('#atualizar-chamado').disabled = !configuracao.administracao_habilitada;
  }
});

async function iniciar() {
  processar(true);
  try {
    configuracao = await requisitar('./config.json', { cache: 'no-store' });
    if (!['api', 'demonstracao'].includes(configuracao.modo)) throw new Error('Modo inválido.');
    if (configuracao.modo === 'demonstracao') {
      exemplosPainel = await requisitar('./chamados_demo.json');
      $('#modo-titulo').textContent = 'Modo demonstração';
      $('#modo-metodo').textContent = 'Exemplos fictícios';
      $('#modo-descricao').textContent = 'Explore as três prioridades nos exemplos. Use o Flask para analisar uma nova descrição, cadastrar chamados e registrar alterações.';
      $('#extracao-info').textContent = 'As sugestões de descrição e foto exigem o Flask.';
      $('#painel-info').textContent = 'Fila de exemplos fictícios, ordenada por prioridade e da abertura mais antiga para a mais recente.';
      $('#privacy-text').textContent = 'Dados e fotos selecionados ficam nesta página de demonstração.';
      $('#salvar-info').textContent = 'Escolha um exemplo para ver sua análise. O cadastro real exige o Flask.';
    } else {
      $('#modo-titulo').textContent = 'Fila em operação';
      $('#modo-metodo').textContent = configuracao.extracao_habilitada ? 'IA semântica e regras de segurança' : 'Análise contextual local';
      $('#modo-descricao').textContent = 'O Flask grava os chamados no SQLite e organiza a fila por prioridade e horário de abertura.';
      $('#extracao-info').textContent = configuracao.extracao_habilitada ? 'A OpenAI pode sugerir campos e equipe a partir da descrição e da foto opcional.' : 'A sugestão de equipe usa a descrição. Revise os campos antes de analisar ou salvar.';
      $('#painel-info').textContent = 'Pendentes em ordem de prioridade e abertura. Os indicadores mostram os totais de pendentes antes dos filtros.';
      $('#privacy-text').textContent = configuracao.extracao_habilitada
        ? 'A triagem com IA pode enviar a descrição, as respostas e a foto ao provedor configurado. O cadastro fica no servidor Flask.'
        : 'O cadastro e a foto são armazenados no servidor Flask. A análise contextual usa a descrição e as respostas.';
      $('#salvar-info').textContent = 'Analise para pré-visualizar a prioridade. Confirme os dados para cadastrar na fila.';
      $('#atualizar-painel').hidden = false;
      const atualizarEmFoco = () => { if (!document.hidden && !consultasPainel) carregarPainel(true); };
      setInterval(atualizarEmFoco, 15000);
      document.addEventListener('visibilitychange', atualizarEmFoco);
    }
    processar(false);
    selecionarVisao('pendentes');
  } catch (erro) {
    configuracao = undefined;
    processar(false);
    $('#form-status').textContent = `Não foi possível carregar a ferramenta. ${erro.message}`;
    $('#modo-titulo').textContent = 'Carregamento indisponível';
    $('#painel-status').textContent = 'Atualize a página para tentar novamente.';
  }
}
iniciar();
