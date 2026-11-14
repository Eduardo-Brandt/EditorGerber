# Arquitetura — Editor Gerber

## Escopo atual (0.8.0)

Editor 2D Windows (Python >=3.11 / PySide6), com foco em remover marcações de
serigrafia sem modificar o restante da imagem. O MVP suporta RS-274X: unidades
mm/inch, coordenadas absolutas, supressão L/T, apertures C/R/O/P, furos circulares,
linhas, arcos G02/G03 (G74/G75), regiões com vários contornos, polaridade e
atributos X2. Recursos não suportados devem falhar explicitamente, antes de
adicionar uma camada ao projeto. Inclui agora uma prévia 3D, sem ser um CAM completo.
Inclui comandos legados IPPOS/LN/IN, macros com primitivas 1/4/5/20/21/22,
expressões aritméticas Decimal e tradução exata de objetos (Move/Copy).
Inclui formas, texto por fontes instaladas, importação raster e cotas como
geometria Gerber, régua com inversão de cores, unidades consistentes e
preferências persistentes com interface em português/inglês.
Na revisão 0.4, clipboard JSON, deslocamento pelo cursor, Ortho, snap a pontos,
matrizes e propriedades editáveis usam o mesmo histórico de comandos. Textos
mantêm `TextEntity` imutável durante a sessão; os escritores ignoram esse
metadado e exportam exclusivamente a geometria.
Na 0.5 há ZIP por versão, edição sincronizada, fiduciais e roteamento. A função
Route.Cuts e o modo perfil/traço são preservados por atributos de usuário X2.
O modelo físico subtrai o roteamento antes de recortar os materiais.
Na 0.5.1, processamento usa um cartão central com ampulheta vetorial animada.
Lotes de itens/paths da GUI repintam a animação sem processar eventos novamente
no meio da reconstrução. Ferramentas pendentes usam somente a barra de status.
O gestor reaproveita QTreeWidgetItems e adia mudanças originadas na árvore para
o próximo ciclo de eventos, evitando destruir itens dentro de setData/seleção.
Na 0.5.2, uma fila inicia o próximo ImportJob somente após receber e guardar o
resultado anterior. Paths e dados são preparados sem reconstruções intermediárias;
uma CompositeCommand inclui as camadas e monta a cena uma única vez ao final.
Cada lote conserva o bloqueio de entrada enquanto
existir trabalho; arquivos auxiliares conhecidos são classificados antes do
parser e erros de um lote são apresentados ao final. BusyIndicator não chama
processEvents dentro de mutações do documento. O filtro global bloqueia eventos
de usuário nas janelas, preservando os diálogos modais da operação. Ao concluir
o último trabalho, a liberação é imediata para conservar Escape e gestos de arraste.
Uma paleta lateral reorganiza ações existentes em colunas, sem duplicar atalhos.
As pastas de arquivos e exportações são preferências separadas e persistentes.
A área animada da ampulheta é opaca, evitando repintar a PCB sob ela a cada quadro.
Na 0.8, o modelo guarda a pilha visual de trás para frente e o gestor mostra
sua ordem inversa. Ativar uma camada não altera sua prioridade. ReorderLayers
modifica somente a lista de camadas, com undo/redo; a composição e a sequência
de primitivas dentro de cada Gerber continuam independentes. Apenas um lote
aberto com a lista vazia é ordenado automaticamente por função/cobre interno.

Furação Gerber física usa Drill/PTH/NPTH e é composta em `tools.drilling`,
distinta de Drillmap. O modelo 3D simplifica primeiro o contorno e os recortes,
depois subtrai a furação sem simplificar os diâmetros dos furos. Cada material
é simplificado antes de ser recortado pelo contorno já furado. Isso impede que
a tolerância do preview preencha furos pequenos. Os anéis interiores geram
paredes na malha; seus normais apontam para a cavidade. STEP reutiliza os anéis
como vazios nos sólidos. Furação cega/enterrada é recusada sem stackup apropriado.

## Fronteiras

- `core`: dataclasses independentes de Qt; coordenadas `Decimal` em mm, IDs,
  apertures, objetos lógicos, camadas, board e stackup.
- `gerber`: tokenizer sem perda de bytes; parser de estados e writer. O texto
  de origem e os intervalos de tokens são metadados, não o modelo geométrico.
- `geometry`: bounds analíticos de curvas; Shapely somente sob demanda para
  renderização/composição e consultas. Discretização nunca volta ao arquivo.
- `commands`: histórico independente da GUI; inclusão/exclusão atômica por ID
  com restauração da ordem original. Propriedades visuais também são comandos.
- `graphics`: paths Qt em cache, composição sequencial dark/clear por camada,
  índice BSP da cena para seleção, zoom/pan e snap à grade.
- `tools`: fonte stroke própria, contornos de fontes instaladas, formas,
  raster P&B e cotas; todas as inserções usam o mesmo histórico. Fontes são
  convertidas em macros de outlines com vazados locais transparentes.
- `ui` e `app`: painéis, ações e coordenação. Nenhum parser importa Qt.
  Arquivos, desenho e preferências têm controladores separados. Ações mantêm
  IDs estáveis e atalhos independentes dos catálogos de idioma.
- `locales`: catálogos JSON; `core.units` faz conversões físicas exatas, e campos
  dimensionais mantêm seu valor canônico em mm ao trocar a unidade exibida.
- `validation`: validação sem reparos automáticos e comparação semântica na saída.
- `future3d`: contrato e estudo de opções. Stackup/material são dados do board,
  não comandos inseridos no Gerber.
- `viewer3d`: snapshots imutáveis para worker, contorno/recortes, substrato
  extrudado e superfícies funcionais, triangulação restrita e buffers OpenGL.
  Câmera, vistas e materiais são independentes do canvas e do writer.
  A janela 3D não tem pai Qt; isso permite entradas/janelas próprias no sistema.
  Refresh do editor apenas marca uma revisão pendente. WindowActivate/Show
  agenda uma única reconstrução quando a janela está ativa. Resultados de
  workers com revisão antiga são descartados; a próxima entrada usa o estado
  atual. Alterações de espessura/detalhe continuam atualizando a janela ativa.
  Não há workers de malha concorrentes e a câmera sobrevive à troca da malha.
  Exportação JPG usa FBO no tamanho solicitado. WRL serializa malhas em metros;
  STEP usa XCAF/AP214, polígonos extrudados, cores, validação e gravação atômica.

`app.diagnostics` registra exceções Python/threads e mensagens Qt em logs por
processo, e usa faulthandler para diagnóstico de falhas nativas. Esses registros
não são uma recuperação automática do documento e ficam fora dos ZIPs fonte.

## Segurança do salvamento

O original é guardado em bytes. Abrir não escreve em disco. Preservation sem
edições é idêntico byte a byte. Exclusão troca operações gráficas por movimentos
e explicita o D-code nas operações modais seguintes; apagar uma região remove
seus delimitadores e converte seu conteúdo em movimentos. Assim a posição e os
estados posteriores continuam corretos. Comentários, atributos, apertures e
espaçamento são preservados. Novas linhas são inseridas antes de M02 com estado
explícito, usando a grade de coordenadas original; inserções não representáveis
na precisão original são recusadas. Objetos importados movidos são exportados
em Normalized; a estratégia de patch para transformação in-place fica para
uma fase posterior. Cópias mantêm a ordem original, inclusive para clear/dark.

Normalized reemite os objetos lógicos preferindo mm e usando inch quando
necessário. Na mesma unidade, mantém a resolução original (até seis decimais):
um arco validado em grade de 0,001 mm pode ter pequena discrepância entre raios,
e trocar FS para 0,000001 mm tornaria esse mesmo arco inválido. Não se ajusta
centro/extremidade silenciosamente. Mantém arcos, regiões, apertures, nomes LN
e atributos. Macros são reemitidas como primitivas exatas na unidade de saída. A GUI
explica os dois modos. Antes de gravar, o resultado é reparsed e comparado objeto
a objeto (tipo, coordenadas, aperture, polaridade, atributos e ordem), além de
bounds e contagem. Arquivo temporário no destino e substituição atômica.
Salvar usa o arquivo atual; a primeira substituição do original aberto pede
confirmação por sessão. Salvar como confirma destino existente e torna o novo
destino atual. A API exige parâmetro explícito para sobrescrever. O nome sugerido
de uma nova cópia continua `nome_edited.gbr`.

## Precisão e limites

Decimal representa coordenadas/unidades exatas; arcos conservam centro, sentido
e extremidades. Bounds usam extremos cardinais. Shapely/Qt usam float apenas
para exibição/hit testing, com tolerância de discretização documentada. Clear
subtrai somente o que veio antes na própria camada, nunca outras camadas.
Regiões abertas, raios incoerentes e comandos desconhecidos são erros.
Contornos separados de uma região são unidos, conforme a especificação; furos
de macros são resolvidos dentro da aperture antes de aplicar sua polaridade.
Fontes novas têm curvas aproximadas em contornos com tolerância de 0,00025 mm
e quantização à grade do arquivo; objetos importados não sofrem essa conversão.
Raster novo vira retângulos agrupados por runs e pode ser limitado em resolução
para controlar tamanho/custo. Nada disso rasteriza curvas já existentes.
Não há inferência silenciosa de formato. Recursos AB/SR/LM/LR/LS, IPNEG e
primitivas macro 6/7 ficam bloqueados. Definições AM não usadas são conservadas.
Macros são avaliadas por uma whitelist de nós AST, sem eval(), com limites de
complexidade, valores finitos e coordenadas lógicas Decimal. A rasterização de
curvas ou booleanas nunca volta ao Gerber.

## Bibliotecas avaliadas (11/11/2026)

- [Gerbonara](https://gerbolyze.gitlab.io/gerbonara/): leitura/escrita e macros,
  Apache-2.0, candidato a backend futuro. Seu modelo geométrico não mantém a
  estrutura textual original; a versão 1.6.3 declara Python >=3.12. Não foi
  adotado como dependência para manter a exigência >=3.11 e o controle
  de preservação. Foi usado como oráculo opcional na revisão 0.3, com adaptações
  explicitadas em VALIDATION.md.
- [PyGerber](https://argmaster.github.io/pygerber/stable/): tokenizer/parser e
  renderização extensíveis, candidato a adaptador futuro; não resolve sozinho
  a edição por comandos e a preservação de bytes do editor.
- Parser próprio deliberadamente limitado e com rejeição explícita; nenhuma
  alegação de compatibilidade universal. A migração de backend termina em
  `GerberLayer`, mantendo GUI, comandos e stackup independentes.

Referência normativa: [Ucamco — especificações e arquivos de teste](https://www.ucamco.com/en/guest/downloads/gerber-format).

## Evolução e desempenho

Objetos lógicos não são convertidos em polígonos no parsing. Paths de desenho
são calculados uma vez por revisão da camada e reaproveitados; cena Qt tem BSP.
`ImportJob` prepara parser, geometrias e QPainterPaths
em worker Qt serial, transferindo os caches prontos para a interface. Somente
a thread principal cria itens de cena/widgets. Composição de arquivos muito
grandes e memória continuam sujeitas à complexidade e ao número dos objetos.

Na versão 0.6, `Canvas.rebuild` sincroniza a cena incrementalmente. Snapshots
imutáveis das listas de objetos detectam inclusão, remoção e substituição,
inclusive alterações feitas sem incrementar `revision`. Atributos de aparência
são comparados separadamente, sem chamar o renderer quando só eles mudam.
Cada camada conserva seu path composto, seus itens de hit testing e um pai
gráfico sem conteúdo. Visibilidade e ordem desse pai afetam a camada inteira;
os limites preparados são reutilizados pelo enquadramento.

Itens de hit testing usam `ItemHasNoContents` até serem selecionados. O sinal
de seleção da cena atualiza somente a diferença entre os IDs destacados antes
e depois, sem um callback Python de `itemChange` para cada objeto inserido.
Camadas opacas usam `DeviceCoordinateCache`; o Qt invalida por geometria,
brush e escala e administra a memória no `QPixmapCache` compartilhado.
Transparência usa pintura direta porque o arredondamento de alpha de um pixmap
intermediário pode alterar pixels. As camadas mantêm a composição dark/clear
original do renderer; o cache não altera os objetos nem a saída Gerber.

Na versão 0.7, `TiledComposition` usa STRtree para recuperar os objetos de cada
célula, ordena os índices pela ordem Gerber e compõe as polaridades localmente.
O tamanho inicial é 16 mm, ampliado em potências de dois para limitar a grade
a 1.024 células. Camadas com menos de 512 objetos conservam a composição simples.
Uma atualização compara snapshots por identidade/conteúdo e reutiliza as células
que não intersectam os limites antigos/novos dos objetos alterados. Remover ou
inserir não invalida o restante por mero deslocamento de índices; uma reordenação
real invalida a composição. O índice espacial é reconstruído para cada snapshot.

Cada célula guarda a geometria central e uma margem de 1/16 do seu tamanho.
`TiledLayerItem` pinta o path com margem sob clip retangular, que divide os pixels
entre as células. Isso evita antialiasing de bordas artificiais e acúmulo de alpha
na junção. A aproximação das curvas permanece em 0,001 mm; nenhum LOD foi aplicado.
Em zoom extremamente afastado, quando a margem fica menor que um pixel, a pintura
retorna ao path completo. Diferenças pequenas de antialiasing pela divisão são
conferidas em imagens; a precisão dos objetos exportados não depende desses paths.

O display tem `shape()` vazia: somente ObjectItem participa de hit testing.
O snap guarda um resultado por cursor/escala/âncora/configuração; sincronizar
o desenho invalida esse resultado. Durante o pan, a busca de pontos de objetos
é dispensada e volta a funcionar ao terminar o deslocamento.
O orçamento compartilhado do `QPixmapCache` é elevado para pelo menos 64 MiB,
alocado sob demanda. Isso permite conservar vários pixmaps de viewport ao mesmo
tempo; com o limite padrão pequeno, camadas sucessivas podem expulsar os caches
umas das outras. A memória de geometrias e paths é separada desse orçamento.

O modelo 3D consome as curvas e geometrias booleanas sem modificar os objetos.
Qt/OpenGL 3.3 usa VBO/VAO e shaders. As superfícies usam triangulação restrita,
preservando recortes; a tolerância Fino/Normal/Rápido afeta somente o preview.
No STEP, essa mesma geometria aproximada é convertida em sólidos. Coordenadas
CAD são ajustadas a 0,000001 mm; ShapeFix só é aceito após validar o sólido e
comparar volume. A máscara é particionada em áreas sobre cobre e sobre FR4,
criando relevo sem apagar visualmente as trilhas.

Distribuição Qt: `PySide6-Essentials` fornece os módulos PySide6 QtCore/QtGui/
QtWidgets/QtTest usados aqui. O metapacote completo acrescentaria WebEngine,
PDF e Addons desnecessários ao editor. NumPy também faz a conversão P&B de
imagens. Preferências têm esquema versionado e gravação JSON atômica no perfil
do usuário. A splashscreen é um PNG incluído no pacote com dados sobrepostos
pelo Qt. Pytest/Ruff são apenas dev.
