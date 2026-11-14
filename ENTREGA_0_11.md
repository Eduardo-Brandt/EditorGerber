# Editor Gerber 0.11.0 — KiCad e operações em lote

Entrega de 14/11/2026. A versão estável anterior foi preservada em
`Backup/Editor_Gerber_v0.10.0.zip`, SHA-256
`6c35504d5fc71b983eb347694ac804c6c84bba64ecb435989230488a5e7e2327`.
A splash continua configurada em oito segundos.

## Correção de abertura dos Gerbers KiCad

Os arquivos NexCLP de cobre contêm regiões com recortes internos ligados ao
contorno por segmentos coincidentes percorridos em sentidos opostos. São os
cut-ins previstos na especificação Gerber. A geometria de exibição agora
separa esses segmentos e reconstrói os contornos externos e internos, mantendo
os recortes vazios. Os segmentos e suas coordenadas originais permanecem no
documento e nas duas modalidades de salvamento.

Somente pares exatos de segmentos lineares horizontais ou verticais, todos
na mesma direção, são reconhecidos. Os anéis restantes precisam ser simples,
os recortes precisam estar dentro do contorno e as pontes só podem tocar os
limites nas extremidades. Regiões cruzadas ou malformadas continuam sendo
recusadas; não se aplica um reparo genérico aos polígonos.

A serigrafia NexCLP define uma abertura circular de diâmetro zero. O parser
agora aceita essa definição e a geometria ignora seus desenhos/flashes na
imagem, preservando os comandos no arquivo. Dimensões negativas e apertures
de outros tipos com dimensão nula continuam sendo recusadas.

Essas regras seguem as seções 4.3.3 e 4.10 da
[especificação Gerber da Ucamco](https://www.ucamco.com/files/downloads/file_en/554/gerber-layer-format-specification-revision-2026-05_en.pdf).

Arquivos de furação Excellon com cabeçalho M48 agora recebem uma mensagem
específica, em vez de “comando sem terminador no byte 0”. **A leitura Excellon
ainda não foi implementada.** Para o editor e o 3D, a furação deve ser fornecida
em formato Gerber.

## Salvar, abrir e fechar todos os arquivos

- **Salvar todos os arquivos:** novo botão na barra superior e item no menu
  Arquivo. Salva camadas alteradas, novas ou cujo arquivo de destino esteja
  ausente; arquivos já salvos e intactos não são regravados.
- Os destinos de camadas novas são escolhidos antes de gravar. Destinos
  duplicados interrompem a preparação. Cancelar essa etapa ou o aviso final
  não grava nenhum arquivo.
- O aviso informa que o salvamento pode demorar e que arquivos existentes,
  incluindo originais usados como destino, serão substituídos. Os detalhes
  permitem conferir todos os caminhos. Cancelar é a opção padrão.
- A gravação e a validação ocorrem por arquivo, em sequência, em um worker.
  A barra inferior avança após cada arquivo salvo com sucesso. A interface
  continua processando eventos e bloqueia edições/fechamento durante o lote.
- Cada arquivo continua usando a validação por reabertura e a substituição
  atômica existentes no programa. O lote inteiro não é uma transação: se um
  arquivo falhar, os anteriores permanecem salvos, o lote para e informa a
  contagem; os demais continuam pendentes.
- **Fechar todos os arquivos:** novo ícone, conservando o aviso de alterações,
  cancelamento de importações e fechamento reversível pelo histórico.
- **Abertura em lote:** a barra do rodapé avança a cada arquivo processado,
  incluindo erros e arquivos auxiliares ignorados. Novos arquivos adicionados
  durante a importação ampliam o total; cancelar limpa o progresso.

## Ajuda

**Ajuda → Relatar problemas**, no editor e no visualizador 3D, abre
`https://brandttecnologia.com.br/EditorGerber/RelatarProblemas` no navegador.
O guia HTML local também contém esse link e documenta os botões e o progresso
em português e inglês.

## Verificação

**224 testes passaram em 97,26 segundos.** Ruff passou nos módulos, testes
e scripts. Os casos novos cobrem cut-ins horizontais/verticais e múltiplos
recortes, rejeição de cruzamentos, abertura circular nula, preservação dos
comandos, salvamento/reabertura, Excellon identificado, destinos duplicados,
cancelamento, falha parcial, progresso e processamento de eventos durante
gravação em worker.

O ensaio Windows está em `scripts/verify_v011.py`. Os resultados e capturas
ficam em `output/v011/native/`. Ele usa cópias em diretórios de saída para o
salvamento e compara os SHA-256 de todos os arquivos de entrada ao terminar.

Na pasta NexCLP, foram processados onze arquivos: os nove Gerbers abriram,
com 47.653 objetos, e os dois Excellon receberam a identificação específica.
A abertura em lote levou 28,27 segundos neste computador. Foram mantidos
58 recortes internos nas regiões de cobre inferior, 72 no cobre superior e
seis na serigrafia superior. A saída Preservation foi idêntica byte a byte
para os nove arquivos; a saída Normalized foi reaberta e validada. O aviso,
as barras 0–11/0–9 e os botões foram exercitados na interface nativa. Todos
os arquivos originais mantiveram seus SHA-256.

## Backup

Backup desta entrega: `Backup/Editor_Gerber_v0.11.0.zip`. O arquivo inclui
código-fonte, testes, ajuda e documentação; exclui ambiente virtual, resultados
de ensaios e outros backups. A versão 0.10.0 permanece preservada.
