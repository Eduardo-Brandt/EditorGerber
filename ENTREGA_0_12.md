# Editor Gerber 0.12.0 — Excellon, preenchimento e edição múltipla

Entrega de 14/11/2026. O backup estável anterior permanece em
`Backup/Editor_Gerber_v0.11.0.zip`, SHA-256
`57b2707b38ff9d23231da97006d3de1b62e70f5d89bd97dbfb43f1145f601ba4`.

## Furação Excellon

O mesmo fluxo de abertura, pasta e progresso aceita arquivos Excellon com
cabeçalho M48, independentemente da extensão. A geometria usa Decimal em mm,
sem inverter coordenadas em relação aos Gerbers. São lidos:

- METRIC/INCH e M71/M72, coordenadas decimais e eixos modais;
- formato declarado por FORMAT, FILE_FORMAT ou máscara 000.000;
- TZ/LZ, coordenadas absolutas/incrementais, ferramentas circulares e
  comentários de atributos X2 usados pelo KiCad;
- furos, rasgos G85, roteamento linear e circular com G00/G01/G02/G03,
  M15/M16/M17 e repetição R com deslocamento.

Coordenadas inteiras sem formato declarado são recusadas com uma mensagem
específica, evitando presumir uma escala incorreta. Comandos não implementados
também são recusados. Não se pretende executar todos os ciclos de uma máquina
Excellon; o suporte é ao intercâmbio de furação/rasgos de PCB. Furos cegos e
enterrados continuam exigindo um stackup não disponível no visualizador.

As funções Drill.PTH/NPTH são identificadas pelos atributos. A furação passa
a recortar o substrato e as superfícies no 3D, inclusive quando sua camada
está oculta no 2D. Arquivos NPTH vazios abrem como camadas vazias válidas.

Preservation conserva os bytes originais quando a geometria não foi alterada.
Após edições, a saída Excellon usa mm e coordenadas com ponto decimal. Furos e
trajetórias mantêm a ordem e os atributos; a gravação é atômica e validada por
reabertura. Salvar como .gbr converte para Gerber; .drl/.xln mantém Excellon.
Formas preenchidas, polaridade Clear e ferramentas não circulares exigem
saída Gerber e recebem uma orientação caso se tente gravá-las em Excellon.

A interpretação foi conferida com o
[leitor Excellon do KiCad](https://docs.kicad.org/doxygen/excellon__read__drill__file_8cpp_source.html)
e com o
[emissor Excellon do KiCad](https://docs.kicad.org/doxygen/gendrill__excellon__writer_8cpp_source.html).
Em particular, TZ indica zeros finais presentes, e LZ indica zeros iniciais
presentes; essa nomenclatura não é a supressão L/T do Gerber.

## Formas preenchidas e propriedades

**Preenchido**, na barra de parâmetros, cria círculos, retângulos e quadrados
sólidos. Arcos preenchidos são setores circulares fechados por dois raios.
As formas usam regiões Gerber com linhas/arcos exatos, sem aproximar a
geometria de exportação por polígonos de exibição.

**Editar propriedades (E)** reconhece círculos/arcos e regiões canônicas,
inclusive após salvar/reabrir. A conversão entre preenchido e contorno
mantém as coordenadas quando não se alteram dimensões. Retângulos de contorno
novos entram agrupados. Suas quatro arestas podem ser editadas como uma forma.
Uma alteração que muda a quantidade de objetos ocupa a posição original no
documento e aceita desfazer/refazer sem alterar objetos vizinhos.

## Edição simultânea

Seleções de formas compatíveis ou objetos do mesmo tipo abrem um diálogo
com aplicação por campo. Diferenças são indicadas por **Vários valores**.
Alterar um valor marca o respectivo campo; também é possível marcar um campo
para aplicar o valor mostrado a todos. Campos desmarcados usam o valor original
de cada objeto.

Alterar somente a espessura conserva a geometria exata das curvas. Alterar
somente o raio dos círculos mantém os centros, espessuras e outros valores.
Linhas, flashes e regiões também permitem editar campos compatíveis em lote.
Todas as substituições são validadas antes de entrar no histórico em uma
única operação. Os valores iniciais de grandes seleções são calculados sem
criar um diálogo para cada objeto.

## Matrizes

O botão **Matriz de cópias** foi acrescentado à barra superior, mantendo o
menu Editar. A matriz retangular oferece passo e quantidade em X/Y. A polar
conserva o centro por mouse/coordenadas e acrescenta **Definir matriz polar
pelo raio**, com raio e direção do centro em relação ao centro da seleção.
O original fica no primeiro ponto e não é movido. Direção 180° coloca o centro
à esquerda do original. As quantidades incluem o original; 4 posições geram
3 cópias. A opção de girar os objetos permanece disponível.

## Progresso 3D

A barra no rodapé acompanha preparação do contorno, furação, composição,
substrato e malhas das camadas. O worker envia as atualizações para a interface
por sinais Qt. O percentual indica etapas concluídas, sem estimar o tempo
restante. Também funciona ao mudar detalhe ou atualizar a PCB. Os caches
existentes continuam sendo reaproveitados. A exportação mantém seu indicador
indeterminado próprio.

## Verificação e backup

A suíte completa passou com **248 testes em 104,10 segundos**. Após a melhoria
de custo da edição múltipla, os 63 testes de propriedades, arquivos e novos
recursos também passaram. Ruff verifica código, testes e scripts.

Os 24 testes novos verificam formatos mm/inch/TZ/LZ, eixos modais, furos,
rasgos, arcos, repetição, rejeição de formato ambíguo, gravação/conversão,
recorte físico no 3D, quatro tipos de preenchimento, edição seletiva de
raio/espessura/diâmetro, preservação de posições, undo/redo, matrizes e progresso.

O ensaio nativo está em `scripts/verify_v012.py`, com resultados em
`output/v012/native/`. Usa apenas destinos de saída para gravar e confere os
SHA-256 dos arquivos originais. A ajuda HTML em português e inglês foi atualizada.

No Windows, os onze arquivos NexCLP abriram juntos, incluindo os dois Excellon
e seus 1.076 furos. A PCB foi gerada com os furos e atualizada ao trocar o
detalhe; o progresso percorreu 0–100% nas duas operações. Também foram
conferidos visualmente os quatro preenchimentos, o diálogo de edição múltipla
e os parâmetros da matriz polar por raio. A edição de raio preservou os
centros e as espessuras individuais. Os Excellon foram gravados como cópias
.drl e .gbr, sem alterar os arquivos originais.

Backup desta entrega: `Backup/Editor_Gerber_v0.12.0.zip`. A versão 0.11.0
permanece preservada.
