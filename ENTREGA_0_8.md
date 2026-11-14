# Editor Gerber 0.8.0 — ícone, furação 3D, janelas e camadas

Entrega de 13/11/2026 com as quatro melhorias solicitadas. A referência anterior
foi conferida contra `Backup/Editor_Gerber_v0.7.0.zip`, preservado nesta entrega.

## Ícone ampliado

O ícone agora representa somente as PCBs, aproximadas, com trilhas e pads
grandes. A ferramenta integrada `image_gen`, pela skill `imagegen`, editou a
arte anterior; spindle/laser e arcos decorativos foram retirados. A área opaca
ocupa cerca de 96% da largura e 87% da altura. O ICO contém tamanhos próprios
de 16, 24, 32, 48, 64, 128 e 256 pixels.

Arquivos finais: [PNG](gerber_editor/assets/app_icon.png) e
[ICO](gerber_editor/assets/app_icon.ico).
O [prompt completo](gerber_editor/assets/ICON_PROMPT.md) registra a geração.
O preview [em tamanhos pequenos](output/v08/native/03_icon_sizes.png) foi
conferido em fundos claro e escuro. A splashscreen mantém sua arte anterior.

## Furos reais no 3D

O arquivo legado `fur` do conjunto disponível contém **1.161 flashes circulares**,
com diâmetros de 0,85, 1,15, 1,35, 1,45 e 2,1 mm. Ele era classificado como
`Drill drawing`, ignorado pelo 3D. Agora é reconhecido como `Drill` e sua
geometria remove material do substrato, cobre e demais superfícies.

As funções `Drill`, `Drill.PTH` e `Drill.NPTH` representam furos/rasgos passantes.
Os atributos X2 `Plated` e `NonPlated` também são reconhecidos. `Drillmap` continua
como desenho auxiliar, pois pode conter legendas e símbolos que não são cortes.
Essa distinção segue a [especificação Gerber da Ucamco](https://www.ucamco.com/files/downloads/file_en/456/gerber-layer-format-specification-revision-2024-05_en.pdf).

A subtração da furação ocorre depois de simplificar o contorno, para conservar
furos pequenos mesmo com detalhe 3D rápido. As superfícies dos materiais são
recortadas pelo contorno já furado. A malha inclui paredes interiores orientadas
para a cavidade. Ocultar a camada Drill no 2D não fecha fisicamente os furos.
Os vazios são conservados também nas exportações STEP e WRL.

Esta revisão usa **furação em Gerber**, incluindo o `fur` existente. Leitura de
Excellon, metalização das paredes e stackup completo continuam fora do escopo
atual. Dados X2 de furação cega/enterrada são recusados no 3D com mensagem
explícita, para não representá-los incorretamente como furos passantes.

## Abertura maximizada

O comando normal de inicialização abre o editor maximizado. A janela 3D
também abre maximizada quando é criada ou reaberta após fechada. Se já estiver
visível, Alt+3 apenas a traz para frente, conservando um tamanho restaurado
manualmente durante o uso. A splash continua respeitando os quatro segundos.

## Ordem das camadas

O gestor tem botões **Subir camada** e **Descer camada**. A primeira camada da
lista é desenhada à frente; selecionar uma camada ativa não muda a pilha.
Essa regra substitui o comportamento anterior de trazer a camada ativa à
frente automaticamente, permitindo que os botões determinem a sobreposição.
Os botões são desabilitados nos limites da lista e sem camadas abertas.

Ctrl+Z/Ctrl+Y desfaz/refaz a ordenação. O comando altera somente a lista de
camadas da sessão; IDs, objetos, polaridades e ordem de fabricação dentro
de cada Gerber continuam intactos.

Se o editor estiver vazio ao receber um lote, as funções identificadas
determinam a ordem inicial de cima para baixo:

1. F.Silk, F.Paste e F.Mask;
2. F.Cu;
3. camadas internas por número, com In2 antes de In10;
4. B.Cu, B.Mask, B.Paste e B.Silk;
5. furação, contorno, recortes e camadas auxiliares.

A inclusão é um único comando de lote, mantendo o desfazer/refazer conjunto.
Lotes adicionados a uma sessão existente conservam a ordem já escolhida e
incluem os novos arquivos no topo. O modelo guarda as camadas de trás para
frente; o painel mostra a ordem inversa. A ordenação não reescreve Gerbers.

## Verificação

- **160 testes passaram em 74,88 s**, incluindo 14 casos novos de identificação
  de Drill/Drillmap, furos e rasgos através dos materiais, parede interior,
  camada oculta, blind/buried, STEP, ordenação natural, setas/undo/redo,
  pilha existente, tamanhos do ícone e chamada de maximização do 3D.
- Um teste abre o STEP no OpenCascade e verifica que um ponto no furo está
  fora do sólido, enquanto um ponto no material está dentro.
- **Windows/OpenGL nativo aprovado**: as duas janelas maximizaram; o lote
  inicial foi ordenado; setas e undo/redo funcionaram; o framebuffer 3D mostrou
  o furo circular, o rasgo e o furo pequeno. STEP e WRL foram exportados.
- O arquivo real `fur` foi reaberto sem alteração. Os 1.161 centros ficaram
  fora do substrato e a malha de verificação gerou 239.856 triângulos. O contorno
  desse ensaio foi um retângulo de teste envolvendo a furação, não uma inferência
  do contorno real da PCB. O SHA-256 foi comparado antes/depois.
- Ruff e formatação aprovados. As preferências e saídas dos ensaios ficaram
  em `output/v08`, sem usar as preferências reais do usuário.

[Relatório nativo](output/v08/native/report.json) ·
[Editor maximizado](output/v08/native/01_editor_maximized.png) ·
[Furos e rasgo no 3D](output/v08/native/04_3d_through_holes.png) ·
[Paredes interiores](output/v08/native/06_3d_inner_walls.png).

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check gerber_editor tests scripts
.\.venv\Scripts\python.exe -m scripts.verify_v08 --drill "C:\Temp\Gerbers\PCB Teste\fur"
```

## Sobre a velocidade do KiCad

O GerbView tem núcleo C++ e dispõe de renderização acelerada pela GPU, com
geometrias e triangulações em cache. Zoom e pan podem reutilizar esses dados
no motor gráfico. O nosso 2D usa atualmente raster Qt em CPU e cache por blocos;
Qt e GEOS já executam cálculos nativos, embora o controle seja Python.
São arquiteturas gráficas diferentes; trocar a linguagem sozinha não reproduz
todo o motor do KiCad.

Referências primárias: [painter C++ do GerbView](https://docs.kicad.org/doxygen/gerbview__painter_8cpp_source.html)
e [OpenGL GAL](https://docs.kicad.org/doxygen/classKIGFX_1_1OPENGL__GAL.html).

[Backup 0.8.0](Backup/Editor_Gerber_v0.8.0.zip). Para carregar o novo código
e ícone, salve o trabalho e reinicie pelo `Iniciar.bat`.
