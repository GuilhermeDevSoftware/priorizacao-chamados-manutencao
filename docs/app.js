import { CAMPOS, NOMES, validarCampos, preverArvore } from './engine.js';

const $ = seletor => document.querySelector(seletor);
const form = $('#formulario');
const equipes = ['TI', 'Elétrica', 'Hidráulica', 'Triagem geral'];
let configuracao, modelo, analiseAtual = null, fotoArquivo = null, fotoURL = null;
let processando = false, sugestoesPendentes = false, cadastroSalvo = false;
let exemplosPainel = [], detalheAtual = null, versaoPainel = 0, versaoFoto = 0;
const exemplos = {
  macaneta: { descricao: 'Maçaneta frouxa em uma sala desocupada, sem risco identificado e sem interromper atividades.', local: 'Sala desocupada · exemplo fictício', equipe: 'Triagem geral', valores: [0, 0, 0, 1, 0] },
  agua: { descricao: 'Falta de água em toda a escola, interrompendo o uso dos banheiros e o preparo das refeições.', local: 'Escola · exemplo fictício', equipe: 'Hidráulica', valores: [0, 1, 250, 0, 0] },
  fiacao: { descricao: 'Fiação exposta em um corredor de pouca circulação, com risco de choque para quem passar pelo local.', local: 'Corredor · exemplo fictício', equipe: 'Elétrica', valores: [1, 0, 2, 0, 0] }
};

function persistente() { return configuracao?.modo === 'api' && configuracao.armazenamento_habilitado === true; }
function processar(ativo) {
  processando = ativo;
  for (const controle of form.querySelectorAll('input, select, textarea, button')) controle.disabled = ativo;
  for (const botao of document.querySelectorAll('[data-exemplo]')) botao.disabled = ativo;
  $('#analisar').disabled = ativo || !configuracao;
  $('#extrair').disabled = ativo || !persistente();
  $('#salvar').disabled = ativo || !persistente() || cadastroSalvo;
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
  $('#confirmar-campos').checked = false;
  cadastroSalvo = false;
  if (!$('#resultado').hidden) $('#resultado-atualizacao').hidden = false;
  if (['descricao', 'foto', 'foto-camera'].includes(evento?.target?.id)) invalidarAnalise();
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
    if (!r.ok) { const erro = new Error(dados.erro || 'Não foi possível concluir.'); erro.detalhes = dados.detalhes; throw erro; }
    return dados;
  } catch (erro) {
    if (erro.name === 'AbortError') throw new Error('O serviço demorou para responder. Continue pelo preenchimento manual.');
    throw erro;
  } finally { clearTimeout(timer); }
}
function retirarFoto(avisar = true) {
  versaoFoto++;
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
  try {
    await imagem.decode();
    if (versao !== versaoFoto) { URL.revokeObjectURL(url); return; }
    if (imagem.naturalWidth * imagem.naturalHeight > 25000000) throw new Error('A foto excede 25 megapixels. Escolha uma resolução menor.');
    fotoArquivo = arquivo; fotoURL = url;
    $('#foto-previa').src = url; $('#foto-box').hidden = false;
    $('#foto-status').textContent = 'Foto selecionada para prévia. Ela só será gravada ao salvar pelo Flask.';
  } catch (erro) { URL.revokeObjectURL(url); if (versao !== versaoFoto) return; $('#foto-status').textContent = erro.message.startsWith('A foto') ? erro.message : 'Não foi possível abrir a imagem. Escolha uma foto válida.'; }
}
$('#foto').addEventListener('change', escolherFoto);
$('#foto-camera').addEventListener('change', escolherFoto);
$('#remover-foto').addEventListener('click', () => retirarFoto());
window.addEventListener('pagehide', () => { if (fotoURL) URL.revokeObjectURL(fotoURL); });

function exibirResultado(classe, campos, registro = null) {
  if (![0, 1].includes(classe)) throw new Error('Classe retornada inválida.');
  $('#resultado-titulo').textContent = classe === 1 ? '1 · Prioritário' : '0 · Normal';
  $('#resultado-destaque').classList.toggle('priority', classe === 1);
  $('#resultado-explicacao').textContent = classe === 1 ? 'O modelo sugere priorizar a avaliação pelo responsável pela manutenção.' : 'O modelo sugere atendimento na programação habitual, após revisão do responsável.';
  $('#resumo-descricao').textContent = $('#descricao').value.trim() || 'Descrição não informada.';
  const lista = $('#resumo-campos'); lista.replaceChildren();
  for (const campo of CAMPOS) {
    const linha = document.createElement('div'), dt = document.createElement('dt'), dd = document.createElement('dd');
    dt.textContent = NOMES[campo]; dd.textContent = ['pessoas_afetadas', 'dias_aguardando'].includes(campo) ? new Intl.NumberFormat('pt-BR').format(campos[campo]) : campos[campo] === 1 ? 'Sim' : 'Não';
    linha.append(dt, dd); lista.append(linha);
  }
  $('#resultado-equipe').textContent = registro?.equipe_confirmada || $('#equipe_confirmada').value || 'A confirmar';
  $('#resultado-status').textContent = registro?.status || 'Ainda não cadastrado';
  $('#resultado-vazio').hidden = true; $('#resultado').hidden = false;
  $('#resultado-atualizacao').hidden = true;
  $('#form-status').textContent = registro ? `Chamado #${registro.id} salvo no SQLite local. Status: ${registro.status}.` : 'Análise concluída. A previsão não salva o chamado. Revise os dados antes de cadastrar.';
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
  evento.preventDefault(); if (processando) return; limparErros();
  const validacao = validarCampos(obterCampos());
  if (!validacao.valido) { mostrarErros(validacao.erros); $('#form-status').textContent = 'Revise os campos indicados. Nenhuma previsão foi realizada.'; return; }
  if (sugestoesPendentes && !$('#confirmar-campos').checked) { $('#form-status').textContent = 'Revise os campos e marque a confirmação das sugestões antes de analisar.'; $('#confirmar-campos').focus(); return; }
  if (!configuracao) return;
  processar(true); $('#form-status').textContent = 'Analisando o chamado…';
  try {
    const classe = configuracao.modo === 'api' ? (await requisitar('./api/prever', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...validacao.campos, descricao: $('#descricao').value.trim() }) })).classe : preverArvore(modelo, validacao.campos);
    exibirResultado(classe, validacao.campos);
  } catch (erro) { $('#form-status').textContent = erro.message; mostrarErros(erro.detalhes); }
  finally { processar(false); }
});
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
  if (processando || !persistente()) return;
  if (!$('#descricao').value.trim()) { $('#extracao-status').textContent = 'Escreva uma descrição antes de solicitar sugestões.'; $('#descricao').focus(); return; }
  processar(true); limparErros(); $('#extracao-status').textContent = 'Solicitando sugestões…';
  try {
    const dados = new FormData(); dados.append('descricao', $('#descricao').value.trim()); if (fotoArquivo) dados.append('foto', fotoArquivo);
    const analise = await requisitar('./api/analisar', { method: 'POST', body: dados });
    if (!analise.campos || !equipes.includes(analise.equipe_sugerida) || analise.confirmacao_necessaria !== true) throw new Error('Sugestões inválidas. Continue preenchendo manualmente.');
    const campos = {};
    for (const nome of CAMPOS) { const v = validarCampos({ ...Object.fromEntries(CAMPOS.map(c => [c, 0])), [nome]: analise.campos[nome] }); const manual = validarCampos({ ...Object.fromEntries(CAMPOS.map(c => [c, 0])), [nome]: document.getElementById(nome).value }); campos[nome] = v.valido ? v.campos[nome] : manual.valido ? manual.campos[nome] : null; }
    preencher(campos); analiseAtual = analise; sugestoesPendentes = true;
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
  if (processando || !persistente() || cadastroSalvo) return; limparErros();
  const validacao = validarCampos(obterCampos()), erros = { ...validacao.erros };
  const descricao = $('#descricao').value.trim(), local = $('#local').value.trim(), equipe = $('#equipe_confirmada').value;
  if (!descricao || descricao.length > 2000) erros.descricao = 'Informe uma descrição de até 2.000 caracteres.';
  if (!local || local.length > 200) erros.local = 'Informe o local com até 200 caracteres.';
  if (!equipes.includes(equipe)) erros.equipe_confirmada = 'Selecione a equipe responsável.';
  if (Object.keys(erros).length) { mostrarErros(erros); $('#form-status').textContent = 'Revise os campos para salvar. Nenhum chamado foi cadastrado.'; return; }
  if (!$('#confirmar-campos').checked) { $('#form-status').textContent = 'Confirme a revisão dos campos e da equipe antes de salvar.'; $('#confirmar-campos').focus(); return; }
  processar(true); $('#form-status').textContent = 'Salvando chamado…';
  try {
    const dados = new FormData(); dados.append('dados', JSON.stringify({ descricao, local, ...validacao.campos, equipe_confirmada: equipe, confirmado: true, ...(analiseAtual ? { analise: analiseAtual } : {}) }));
    if (fotoArquivo) dados.append('foto', fotoArquivo);
    const registro = await requisitar('./api/chamados', { method: 'POST', body: dados });
    cadastroSalvo = true; exibirResultado(registro.prioridade_sugerida, validacao.campos, registro);
    await carregarPainel();
  } catch (erro) { $('#form-status').textContent = `Não foi possível salvar. ${erro.message}`; mostrarErros(erro.detalhes); }
  finally { processar(false); }
});
$('#limpar').addEventListener('click', () => {
  if (processando) return;
  form.reset(); retirarFoto(false); invalidarAnalise(); limparErros(); contador(); cadastroSalvo = false;
  $('#foto-status').textContent = ''; $('#resultado-vazio').hidden = false; $('#resultado').hidden = true;
  processar(false); $('#descricao').focus();
});

function criarTexto(tag, texto, classe) { const el = document.createElement(tag); el.textContent = texto; if (classe) el.className = classe; return el; }
function dataLegivel(data) { return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(data)); }
function renderizarLista(registros) {
  const lista = $('#lista-chamados'); lista.replaceChildren(); $('#painel-contagem').textContent = `${registros.length} chamado(s)`;
  if (!registros.length) { lista.append(criarTexto('p', 'Nenhum chamado encontrado para estes filtros.', 'panel-empty')); return; }
  for (const registro of registros) {
    const item = document.createElement('article'); item.className = 'ticket-item'; item.dataset.chamadoId = String(registro.id);
    const topo = document.createElement('div'); topo.className = 'ticket-title';
    topo.append(criarTexto('span', `#${registro.id}`, 'ticket-id'), criarTexto('h3', registro.descricao));
    const meta = document.createElement('div'); meta.className = 'ticket-tags';
    for (const [rotulo, valor] of [['Equipe', registro.equipe_confirmada], ['Prioridade', `${registro.prioridade_sugerida} · ${registro.rotulo_prioridade}`], ['Status', registro.status]]) meta.append(criarTexto('span', `${rotulo}: ${valor}`, rotulo === 'Prioridade' && registro.prioridade_sugerida === 1 ? 'priority-tag' : ''));
    const botao = criarTexto('button', 'Ver detalhes', 'detail-button'); botao.type = 'button'; botao.setAttribute('aria-label', `Ver detalhes do chamado ${registro.id}`); botao.addEventListener('click', () => abrirDetalhe(registro.id));
    item.append(topo, criarTexto('p', `${registro.local} · ${dataLegivel(registro.data_abertura)}`, 'ticket-location'), meta, botao); lista.append(item);
  }
}
async function carregarPainel() {
  const versao = ++versaoPainel; $('#painel-status').textContent = 'Carregando chamados…';
  const filtros = { equipe: $('#filtro-equipe').value, prioridade: $('#filtro-prioridade').value, status: $('#filtro-status').value };
  try {
    let registros;
    if (persistente()) {
      const query = new URLSearchParams(Object.entries(filtros).filter(([, valor]) => valor !== ''));
      registros = (await requisitar(`./api/chamados?${query}`)).chamados;
    } else registros = exemplosPainel.filter(r => (!filtros.equipe || r.equipe_confirmada === filtros.equipe) && (!filtros.prioridade || String(r.prioridade_sugerida) === filtros.prioridade) && (!filtros.status || r.status === filtros.status));
    if (versao !== versaoPainel) return;
    renderizarLista(registros); $('#painel-status').textContent = '';
  } catch (erro) { if (versao === versaoPainel) $('#painel-status').textContent = `Não foi possível carregar o painel. ${erro.message}`; }
}
async function abrirDetalhe(id, moverFoco = true) {
  try {
    const r = persistente() ? await requisitar(`./api/chamados/${encodeURIComponent(id)}`) : exemplosPainel.find(ex => ex.id === id);
    if (!r) return; detalheAtual = r;
    $('#detalhe-titulo').textContent = `Chamado #${r.id}`; $('#detalhe-descricao').textContent = r.descricao;
    const resumo = $('#detalhe-resumo'); resumo.replaceChildren();
    const pares = [['Local', r.local], ['Abertura', dataLegivel(r.data_abertura)], ['Prioridade sugerida', `${r.prioridade_sugerida} · ${r.rotulo_prioridade}`], ['Equipe sugerida', r.equipe_sugerida], ['Justificativa', r.justificativa_equipe], ...CAMPOS.map(c => [NOMES[c], ['pessoas_afetadas', 'dias_aguardando'].includes(c) ? String(r[c]) : r[c] ? 'Sim' : 'Não'])];
    for (const [nome, valor] of pares) { const div = document.createElement('div'); div.append(criarTexto('dt', nome), criarTexto('dd', valor)); resumo.append(div); }
    $('#detalhe-foto').hidden = !r.foto_url;
    if (r.foto_url) $('#detalhe-foto').src = new URL(r.foto_url, document.baseURI).href; else $('#detalhe-foto').removeAttribute('src');
    $('#detalhe-analise').replaceChildren();
    if (r.analise) {
      $('#detalhe-analise').append(criarTexto('strong', r.analise.tipo_defeito || 'Análise de apoio'), criarTexto('p', (r.analise.indicios_observados || []).join('; ')), criarTexto('p', `A confirmar: ${(r.analise.informacoes_confirmar || []).join('; ') || 'sem itens adicionais registrados'}`));
    }
    $('#detalhe-equipe').value = r.equipe_confirmada; $('#detalhe-status').value = r.status;
    for (const idControle of ['detalhe-equipe', 'detalhe-status', 'atualizar-chamado']) document.getElementById(idControle).disabled = !persistente();
    $('#detalhe-mensagem').textContent = persistente() ? 'Você pode alterar a equipe responsável e o status. A sugestão original permanece registrada.' : 'Exemplo fictício fixo. Alterar equipe e status exige o Flask local.';
    $('#detalhe-chamado').hidden = false; if (moverFoco) $('#detalhe-chamado').focus();
  } catch (erro) { $('#painel-status').textContent = `Não foi possível consultar o chamado. ${erro.message}`; }
}
for (const id of ['filtro-equipe', 'filtro-prioridade', 'filtro-status']) document.getElementById(id).addEventListener('change', carregarPainel);
$('#fechar-detalhe').addEventListener('click', () => { $('#detalhe-chamado').hidden = true; detalheAtual = null; });
$('#atualizar-chamado').addEventListener('click', async () => {
  if (!persistente() || !detalheAtual) return;
  $('#atualizar-chamado').disabled = true; $('#detalhe-mensagem').textContent = 'Atualizando chamado…';
  try {
    const r = await requisitar(`./api/chamados/${detalheAtual.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ equipe_confirmada: $('#detalhe-equipe').value, status: $('#detalhe-status').value }) });
    await carregarPainel(); await abrirDetalhe(r.id, false); $('#detalhe-mensagem').textContent = 'Equipe e status atualizados no SQLite local.';
  } catch (erro) { $('#detalhe-mensagem').textContent = erro.message; }
  finally { $('#atualizar-chamado').disabled = !persistente(); }
});

async function iniciar() {
  processar(true);
  try {
    configuracao = await requisitar('./config.json', { cache: 'no-store' });
    if (!['api', 'demonstracao'].includes(configuracao.modo)) throw new Error('Modo inválido.');
    if (configuracao.modo === 'demonstracao') {
      [modelo, exemplosPainel] = await Promise.all([requisitar('./modelo/arvore.json'), requisitar('./chamados_demo.json')]);
      preverArvore(modelo, Object.fromEntries(CAMPOS.map(c => [c, 0])));
      $('#modo-titulo').textContent = 'Modo demonstração';
      $('#modo-descricao').textContent = 'Previsão no navegador e painel de exemplos fictícios fixos. Salvar chamados, analisar fotos e atualizar o atendimento exigem Flask.';
      $('#extracao-info').textContent = 'Análise de descrição e foto exige Flask. A prévia da imagem fica somente neste navegador.';
      $('#painel-info').textContent = 'Quatro exemplos fictícios fixos. Os filtros funcionam; os exemplos não podem ser alterados e nenhum cadastro é salvo.';
      $('#privacy-text').textContent = 'Nesta demonstração, dados e fotos selecionados não são enviados nem armazenados.';
    } else {
      $('#modo-titulo').textContent = 'Modo local · Flask e SQLite';
      $('#modo-descricao').textContent = 'Salvar chamado grava os dados e a foto no computador que executa o Flask. A árvore continua sugerindo a prioridade.';
      $('#extracao-info').textContent = configuracao.extracao_habilitada ? 'Ao solicitar sugestões, a descrição e a foto opcional serão enviadas à OpenAI. Revise o resultado.' : 'IA não configurada: a sugestão de equipe usa regra textual local. Preencha os campos manualmente; a foto pode ser salva.';
      $('#painel-info').textContent = 'Chamados salvos no SQLite local. Filtre, consulte os detalhes e atualize equipe e status.';
      $('#privacy-text').textContent = 'O cadastro salva dados e foto no computador. A análise opcional com IA envia descrição e foto ao provedor.';
      $('#salvar-info').textContent = 'Analisar mostra a prioridade. Salvar grava o chamado no SQLite local, após sua confirmação.';
    }
    processar(false); await carregarPainel();
  } catch (erro) {
    configuracao = undefined; processar(false); $('#analisar').disabled = true;
    $('#form-status').textContent = `Não foi possível carregar a ferramenta. ${erro.message}`;
    $('#modo-titulo').textContent = 'Carregamento indisponível'; $('#painel-status').textContent = 'Atualize a página para tentar novamente.';
  }
}
iniciar();
