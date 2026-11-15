/** Executa o motor real do navegador em Node, sem duplicar a árvore. */
import fs from 'node:fs';
import { preverArvore, validarCampos } from '../frontend/engine.js';

const entrada = JSON.parse(fs.readFileSync(0, 'utf8'));
const modelo = JSON.parse(fs.readFileSync(entrada.modelo, 'utf8'));
const previsoes = entrada.casos.map((campos, indice) => {
  const validacao = validarCampos(campos);
  if (!validacao.valido) {
    throw new Error(`Caso válido ${indice} foi rejeitado: ${JSON.stringify(validacao.erros)}`);
  }
  return preverArvore(modelo, validacao.campos);
});
process.stdout.write(JSON.stringify(previsoes));
