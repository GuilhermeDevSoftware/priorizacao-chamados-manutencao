/** Inferência da mesma árvore exportada pelo scikit-learn. Sem regras substitutas. */
export const CAMPOS = Object.freeze([
  'risco_seguranca', 'servico_essencial_interrompido',
  'pessoas_afetadas', 'dias_aguardando', 'recorrente'
]);
export const NOMES = Object.freeze({
  risco_seguranca: 'Risco à segurança',
  servico_essencial_interrompido: 'Serviço essencial interrompido',
  pessoas_afetadas: 'Pessoas afetadas',
  dias_aguardando: 'Dias de espera',
  recorrente: 'Problema recorrente'
});
const BINARIOS = new Set(['risco_seguranca', 'servico_essencial_interrompido', 'recorrente']);

export function validarCampos(entrada) {
  const erros = {};
  const campos = {};
  if (!entrada || typeof entrada !== 'object' || Array.isArray(entrada)) {
    return { valido: false, erros: { formulario: 'Informe os cinco campos do chamado.' }, campos };
  }
  for (const nome of CAMPOS) {
    const original = entrada[nome];
    if (original === null || original === undefined || original === '' ||
        (typeof original === 'string' && original.trim() === '')) {
      erros[nome] = `Informe ${NOMES[nome].toLowerCase()}.`;
      continue;
    }
    // Strings são aceitas somente para ler controles HTML; booleanos nunca viram 0/1.
    if (!['number', 'string'].includes(typeof original) ||
        (typeof original === 'string' && !/^\d+$/.test(original.trim()))) {
      erros[nome] = BINARIOS.has(nome) ? 'Escolha Sim ou Não.' : 'Use um número inteiro igual ou maior que zero.';
      continue;
    }
    const valor = Number(original);
    if (!Number.isSafeInteger(valor) || valor < 0) {
      erros[nome] = 'Use um número inteiro igual ou maior que zero (até 9.007.199.254.740.991).';
    } else if (BINARIOS.has(nome) && valor !== 0 && valor !== 1) {
      erros[nome] = 'Escolha Sim ou Não.';
    } else {
      campos[nome] = valor;
    }
  }
  return { valido: Object.keys(erros).length === 0, erros, campos };
}

export function preverArvore(modelo, entrada) {
  const validacao = validarCampos(entrada);
  if (!validacao.valido) throw new Error(Object.values(validacao.erros).join(' '));
  if (!modelo || !Array.isArray(modelo.nodes) || !Array.isArray(modelo.feature_order) ||
      modelo.feature_order.length !== CAMPOS.length ||
      !modelo.feature_order.every((nome, indice) => nome === CAMPOS[indice])) {
    throw new Error('Arquivo do modelo inválido ou ordem dos campos incompatível.');
  }
  const nos = new Map(modelo.nodes.map(no => [no.id, no]));
  let id = 0;
  for (let passo = 0; passo <= modelo.nodes.length; passo++) {
    const no = nos.get(id);
    if (!no) throw new Error('A árvore contém um nó ausente.');
    if (no.left === -1 && no.right === -1) {
      if (![0, 1].includes(no.prediction)) throw new Error('Classe do modelo inválida.');
      return no.prediction;
    }
    const nome = modelo.feature_order[no.feature_index];
    if (!nome || !Number.isFinite(no.threshold)) throw new Error('Divisão do modelo inválida.');
    // O sklearn converte X para float32 antes de percorrer DecisionTreeClassifier.
    id = Math.fround(validacao.campos[nome]) <= no.threshold ? no.left : no.right;
  }
  throw new Error('A árvore contém um ciclo.');
}
