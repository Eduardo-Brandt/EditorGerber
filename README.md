# Editor Gerber — 0.14.0

Editor desktop para Windows, Linux e macOS, em Python/PySide6. Abre Gerbers com ou sem
extensão, sobrepõe camadas e permite selecionar, excluir, mover, copiar e criar
geometria. O layout segue a organização do GerbView do KiCad.

**Criador:** Eduardo Guilherme Brandt · Indaial-Brasil. Criação: 11/11/2026.
[brandttecnologia.com.br/EditorGerber](https://brandttecnologia.com.br/EditorGerber).
**SOFTWARE LIVRE — [GPLv3](LICENSE)**. Direitos autorais: [COPYRIGHT.md](COPYRIGHT.md).

## Instaladores e versões portáteis

Há instaladores e pacotes portáteis sem instalação de Python para Windows x64,
Linux x64 e macOS Intel/Apple Silicon. A compilação inclui Qt e o backend
de exportação STEP, testa o executável e gera arquivo compactado e SHA-256.
O workflow do GitHub Actions compila cada sistema no seu ambiente nativo e
publica as tags de versão em GitHub Releases.

[Repositório no GitHub](https://github.com/Eduardo-Brandt/EditorGerber) ·
[Downloads da versão mais recente](https://github.com/Eduardo-Brandt/EditorGerber/releases/latest)

| Sistema | Instalador 0.14.0 | Portátil 0.14.0 |
| --- | --- | --- |
| Windows 10/11 x64 | [Setup EXE](https://github.com/Eduardo-Brandt/EditorGerber/releases/download/v0.14.0/EditorGerber-v0.14.0-setup-windows-x64.exe) | [ZIP](https://github.com/Eduardo-Brandt/EditorGerber/releases/download/v0.14.0/EditorGerber-v0.14.0-windows-x64.zip) |
| Ubuntu 22.04+ / Debian 12+ x64 | [DEB](https://github.com/Eduardo-Brandt/EditorGerber/releases/download/v0.14.0/EditorGerber-v0.14.0-setup-linux-x64.deb) | [TAR.GZ](https://github.com/Eduardo-Brandt/EditorGerber/releases/download/v0.14.0/EditorGerber-v0.14.0-linux-x64.tar.gz) |
| macOS 14+ Intel | [PKG](https://github.com/Eduardo-Brandt/EditorGerber/releases/download/v0.14.0/EditorGerber-v0.14.0-setup-macos-x64.pkg) | [ZIP](https://github.com/Eduardo-Brandt/EditorGerber/releases/download/v0.14.0/EditorGerber-v0.14.0-macos-x64.zip) |
| macOS 14+ Apple Silicon | [PKG](https://github.com/Eduardo-Brandt/EditorGerber/releases/download/v0.14.0/EditorGerber-v0.14.0-setup-macos-arm64.pkg) | [ZIP](https://github.com/Eduardo-Brandt/EditorGerber/releases/download/v0.14.0/EditorGerber-v0.14.0-macos-arm64.zip) |

Extraia a pasta inteira. No Windows, abra `EditorGerber.exe`; no Linux,
execute `./EditorGerber`; no macOS, abra `EditorGerber.app`.

Veja [como abrir, compilar e publicar](DISTRIBUICAO.md). A pasta `dist/`
contém os pacotes gerados localmente. Código-fonte, licenças e relatório de
verificação acompanham a distribuição.

## Executar pelo projeto

Na versão 0.14.0, você pode arrastar um ou vários Gerbers ou arquivos Excellon
do explorador para a janela do editor, inclusive sobre o desenho e o gestor
de camadas. Arquivos sem extensão também são aceitos. Eles são adicionados às
camadas abertas, com barra de progresso no rodapé. A ajuda local explica o uso.

Clique duas vezes em **Iniciar.bat** nesta pasta. **Iniciar.ps1** também está
disponível. O ambiente `.venv` já está preparado.

No VS Code, abra **Terminal → Novo terminal**, na pasta do projeto, e execute:

```powershell
.\.venv\Scripts\python.exe -m gerber_editor
```

Esse comando deixa os registros visíveis no terminal. Para abrir diretamente o
arquivo de teste, acrescente `"C:\Temp\Gerbers\PCB Teste\srlc"` ao final.
**Ctrl+C** no terminal encerra o processo; para fechar normalmente e receber o
aviso de alterações não salvas, use o botão de fechar da janela.

Para uma instalação nova, Python 3.11 ou superior (validado com 3.13):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m gerber_editor
```

```powershell
.\.venv\Scripts\python.exe -m gerber_editor --demo
.\.venv\Scripts\python.exe -m gerber_editor "C:\Temp\Gerbers\PCB Teste\srlc"
.\.venv\Scripts\python.exe -m gerber_editor --lang en
```

`--no-splash` pula a tela de apresentação. O menu Preferências permite trocar
português/inglês sem reiniciar e sem alterar atalhos ou arquivos.
A splashscreen respeita o tempo configurado em `SplashScreen.MINIMUM_SECONDS`,
atualmente **8 segundos**, no arquivo `gerber_editor/ui/splash.py`.
O editor abre maximizado. A janela 3D também abre maximizada, inclusive ao ser
reaberta após fechada. O ícone agora mostra a PCB ampliada, com versões próprias
para os tamanhos pequenos do Windows.

## Posicionamento no cursor na versão 0.12.2

**Colar (Ctrl+V)**, **Duplicar (Ctrl+D)**, **Cópia espelhada** e **Mover (M)**
usam o canto inferior esquerdo do conjunto como referência do cursor. O canto
considera a extensão visível dos traços e pads; no espelhamento ele é calculado
após a reflexão. A prévia e o clique de confirmação usam a mesma referência,
respeitando o snap e a resolução da camada.

Ao arrastar diretamente, o ponto onde você pegou o objeto continua preso ao
mouse. A importação interativa de imagens conserva a referência pelo centro.
[Detalhes da versão 0.12.2](ENTREGA_0_12_2.md).

## Barra de edição e campos na versão 0.12.1

Os quinze comandos do menu **Editar** também aparecem como ícones na mesma
seção da barra superior, com seus atalhos nas dicas. Os botões compartilham
as ações do menu, inclusive habilitação, histórico e clipboard.

Campos desabilitados ou de somente leitura usam fundo e texto cinza. Isso
inclui os controles de matrizes, importação de imagem, texto e consulta de
propriedades. Campos habilitados voltam à aparência normal; campos de somente
leitura continuam permitindo selecionar e copiar o conteúdo quando aplicável.
[Detalhes da versão 0.12.1](ENTREGA_0_12_1.md).

## Furação, formas e edição múltipla na versão 0.12

Agora é possível abrir e salvar **Excellon (.drl/.xln)**, com furos e rasgos
passantes usados também no visualizador 3D. A identificação usa o cabeçalho
M48, incluindo arquivos sem extensão. São aceitas unidades mm/inch,
coordenadas decimais ou formato explícito, G85 e roteamento G00/G01/G02/G03
com M15/M16. Sem uma declaração de formato para coordenadas inteiras, o editor
informa a falta de dados em vez de presumir uma escala. O Excellon original é
preservado byte a byte quando não há edição; após alterações, a gravação usa
mm e coordenadas decimais, validada por reabertura. **Salvar como** permite
converter a furação para Gerber.

Marque **Preenchido** na barra de parâmetros antes de desenhar um círculo,
retângulo ou quadrado sólido. O arco preenchido é um setor circular, fechado
pelos dois raios. A opção também está em **Editar propriedades (E)** para
formas reconhecidas. Retângulos de contorno entram agrupados para selecionar
as quatro arestas juntas.

Selecione vários objetos compatíveis e use **Editar propriedades**. Marque
somente os campos desejados; editar um valor marca sua aplicação automaticamente.
Campos não marcados conservam o valor individual de cada objeto. Assim, é
possível alterar o raio ou a espessura de vários círculos mantendo os centros,
posições e outros parâmetros.

**Matriz de cópias** agora também está na barra superior. A matriz retangular
recebe passos e quantidades em X/Y. A polar permite escolher o centro ou
informar **raio e direção do centro**, mantendo o original no primeiro ponto.
As quantidades incluem o original: quatro posições criam três cópias.

O rodapé do visualizador 3D exibe progresso percentual por etapas na geração
e atualização da PCB. [Detalhes da entrega e validação](ENTREGA_0_12.md).

## KiCad, operações em lote e problemas na versão 0.11

Os Gerbers KiCad com recortes internos ligados por segmentos coincidentes de
ida e volta (cut-ins) agora abrem conservando os vazios do cobre. Aberturas
circulares de diâmetro zero também são aceitas e não produzem área visível.
Contornos realmente cruzados continuam sendo recusados. A leitura Excellon
foi acrescentada na versão 0.12, conforme descrito acima.

A abertura de vários arquivos exibe progresso no rodapé a cada arquivo
processado. **Salvar todos os arquivos**, no menu Arquivo e na barra superior,
grava camadas alteradas ou sem arquivo salvo. Camadas novas pedem destino
antes de iniciar. Um aviso permite conferir os destinos e informa que o
processo pode demorar; a barra avança após cada gravação validada. O trabalho
ocorre em sequência fora da interface, que continua exibindo o progresso.
Se houver falha, o lote para e as camadas restantes permanecem pendentes.

**Fechar todos os arquivos** também está na barra superior, conservando a
confirmação de alterações não salvas. **Ajuda → Relatar problemas**, disponível
no editor e no 3D, abre o formulário em
[brandttecnologia.com.br/EditorGerber/RelatarProblemas](https://brandttecnologia.com.br/EditorGerber/RelatarProblemas).
[Detalhes e validação da versão 0.11.0](ENTREGA_0_11.md).

## Ajuda e grupos na versão 0.10

**Ajuda → Como usar** abre um guia HTML dentro do programa, com índice de
tópicos, busca por texto e tabela dos atalhos atuais. A janela pode permanecer
aberta durante o trabalho e acompanha o idioma da interface. No visualizador
3D, a mesma ajuda abre diretamente no tópico de 3D.

Imagens importadas entram agrupadas durante a sessão. Clique em uma parte para
selecionar o conjunto e mover, copiar ou excluir a imagem inteira.
**Editar → Agrupar objetos (Ctrl+G)** agrupa dois ou mais objetos da mesma camada;
**Desagrupar objetos (Ctrl+Shift+G)** separa os componentes. Ambas as operações
aceitam Ctrl+Z/Ctrl+Y. Cópias e instâncias de matrizes recebem grupos independentes.

O agrupamento organiza a seleção da sessão e conserva a ordem, polaridades e
geometria de fabricação. Ele não marca o Gerber como alterado nem provoca nova
geração 3D. Salvar conserva o grupo na sessão aberta; fechar e reabrir um Gerber
recupera sua geometria, sem os grupos. [Detalhes da entrega](ENTREGA_0_10.md).

## Desempenho 3D na versão 0.9

O visualizador aproveita a composição geométrica já calculada no 2D e conserva
os resultados por camada. Depois de uma edição, as camadas, o substrato e as
malhas com dependências intactas são reaproveitados. Cor, opacidade, ordem da
pilha 2D e idioma não provocam uma nova geração 3D. Contorno, recortes, furação,
função e geometria continuam atualizando as partes físicas correspondentes.

A montagem dos vértices ocorre em lote, e as duas faces do substrato usam uma
única triangulação. No ensaio com `olc`, `srlc` e `fur` (123.268 objetos), a
geração inicial passou de **53,8 s para 12,6 s**; uma atualização após mover um
objeto da serigrafia passou de **46,7 s para 4,1 s**. São tempos do cálculo 3D,
com os Gerbers já preparados no 2D, e variam conforme a placa e o computador.
Método e limites: [ENTREGA_0_9.md](ENTREGA_0_9.md).

## Desempenho 2D na versão 0.7

Camadas grandes são compostas em blocos espaciais. Zoom e deslocamento pintam
somente os blocos visíveis, com o mesmo detalhe das curvas. Ao editar um objeto,
os blocos tocados pelas posições antiga e nova são recompostos; os demais são
reaproveitados. A composição mantém a ordem das operações dark/clear.

O pan dispensa buscas de pontos magnéticos enquanto desloca a vista. O snap
também reutiliza o resultado quando cursor, escala e desenho não mudaram.
As formas das camadas de apresentação não participam das buscas de seleção;
cada objeto continua com sua forma precisa de clique, janela e destaque.
O cache de imagens do Qt tem orçamento de 64 MiB, usado sob demanda, para
reaproveitar a vista de várias camadas sem descartar uma ao desenhar a próxima.

Coordenadas Decimal e saída Gerber conservam a implementação anterior. Uma
edição que afete uma região extensa ainda pode recompor muitos blocos. O
comparativo com a versão 0.6 e os limites estão em [ENTREGA_0_7.md](ENTREGA_0_7.md).

## Melhorias anteriores da versão 0.6

Cor, opacidade e visibilidade são atualizadas na cena existente. Ao editar,
somente os itens alterados são adicionados, removidos ou atualizados; as outras
camadas conservam seus itens e caches. Objetos sem seleção mantêm suas formas
para clique e snap, sem executar uma pintura Python vazia a cada quadro.
O destaque é reativado automaticamente quando o objeto é selecionado.

Camadas opacas usam o cache gráfico do Qt durante deslocamentos; alterações de
zoom, cor e geometria invalidam o cache automaticamente. Camadas transparentes
usam pintura direta para preservar a mistura exata de cores. O cache de imagens
é administrado pelo limite compartilhado do Qt. Enquadrar e ativar camadas
também aproveitam os limites e grupos já preparados.

A precisão Decimal, o parser e o writer não foram alterados. A primeira abertura
e a composição geométrica de uma camada editada ainda podem demorar em arquivos
grandes. Resultados e limites das medições estão em [ENTREGA_0_6.md](ENTREGA_0_6.md).

## Abrir, editar e salvar

1. **Ctrl+O** abre um ou vários arquivos. **Arquivo → Abrir pasta de Gerbers**
   reconhece arquivos pelo conteúdo, inclusive aqueles sem extensão.
   O auxiliar `fp-info-cache` do KiCad é ignorado, com aviso na barra inferior.
   Não contém o desenho Gerber. Arquivos Gerber inválidos continuam sendo
   informados; em um lote, os erros aparecem juntos ao concluir o carregamento.
2. A camada nova fica na frente e no topo do gestor. Clique no nome para
   ativá-la; dois cliques abrem **Cor / Opacidade / Função**. O botão **x** fecha
   uma camada. **Ctrl+Shift+W** fecha todas.
   Use as setas **Subir / Descer** para mudar a ordem. A primeira camada da lista
   determina a ordem das camadas inativas. Ao clicar em uma camada, ela fica
   à frente das demais enquanto estiver ativa, sem mudar a ordem no gestor. Ctrl+Z/Ctrl+Y
   também desfaz/refaz a ordenação, sem alterar objetos dos Gerbers.
   Novas camadas abrem com opacidade de 100%.
   Ao abrir um lote com o editor vazio, a ordem é organizada por função:
   F.Silk, F.Paste, F.Mask, F.Cu, internas em ordem numérica, B.Cu, B.Mask,
   B.Paste, B.Silk e auxiliares. Lotes posteriores preservam a ordem existente.
3. O scroll aproxima no ponto do cursor. Botão central pressionado desloca.
   **Home** enquadra; **F1/F2** aproximam/afastam.
4. Arraste da esquerda para a direita para selecionar objetos inteiros, ou
   da direita para a esquerda para selecionar os que cruzam a janela.
   **Ctrl+clique** adiciona/remove; **Delete** exclui; **Ctrl+Z/Ctrl+Y** desfaz/refaz.
   **M** move pelo cursor; **Ctrl+C/Ctrl+X/Ctrl+V** copiam/recortam/colam.
   **Ctrl+D** duplica pelo cursor. Selecionar e arrastar também move.
   **E** abre propriedades; **Editar propriedades** altera o objeto/texto.
   Dois cliques sobre o objeto abrem a edição diretamente. Comprimento e ângulo
   das linhas atualizam suas coordenadas; mudar coordenadas recalcula as medidas.
5. **Ctrl+S** ou o ícone do disquete salva a camada ativa no arquivo atual.
   Na primeira gravação sobre o original aberto há uma confirmação. Uma
   camada nova solicita um destino. **Ctrl+Shift+S** ou o segundo disquete abre
   **Salvar como**; o destino escolhido passa a ser o arquivo atual.

Cada camada é salva separadamente. Fechar arquivos modificados oferece
Salvar / Descartar / Cancelar. Fechamento de camadas também admite Undo/Redo.
As exportações são reabertas e conferidas antes da substituição atômica do destino.
Abrir e Salvar como lembram a última pasta escolhida, inclusive após reiniciar.
Salvar continua gravando no arquivo atual e atualiza essa pasta de referência.

## Medir e desenhar

**Shift+A** inicia a régua: clique no início e mova o cursor para ver distância,
Delta X/Y e ângulo em tempo real. O segundo clique fixa a medida; **Esc** cancela.
O pontilhado inverte as cores atravessadas. Os botões **mm / in / mil** alteram
coordenadas, medidas, propriedades e campos dimensionais. A geometria conserva
suas dimensões físicas.

Em **Ferramentas**, escolha linha, arco, círculo, quadrado, retângulo, texto,
cota ou importação de gráfico. Arco: centro, início e direção do fim; **Shift**
ativa Ortho, com passo **45°/90°** em **Ferramentas → Ortho com Shift**.
O sentido dos arcos tem a opção **Arcos no sentido horário**.
Círculo: centro e raio. Retângulo/quadrado: cantos opostos.
A espessura e a polaridade são escolhidas na barra superior.

Texto permite fonte PCB simples ou uma fonte instalada, altura, rotação,
negrito e itálico. Cota usa dois pontos medidos e um terceiro para sua posição;
o diálogo define setas, fonte, altura, precisão, mm/in/mil e ângulo polar.
Textos e cotas exportados são geometria Gerber; a fonte não precisa estar
instalada para visualizar o arquivo. Na mesma sessão, textos inseridos mantêm
conteúdo/fonte editáveis, inclusive após salvar. Ao reabrir o Gerber, o texto
é geometria e não se recupera a informação tipográfica automaticamente.
Texto, fonte, altura, espessura, rotação e estilos usados por último são lembrados
para a próxima inserção; a posição continua sendo a escolhida no canvas.

**Snap a extremidades e pontos** atrai o cursor a finais de linhas, vértices,
centros de flashes e centros/extremidades de arcos. A marca verde indica o ponto
capturado. **Shift** restringe construções e posicionamentos ao passo angular
escolhido; **Esc** cancela a operação pendente.
O snap inclui o meio das linhas e pontos a cada 45° nos círculos e no trecho
efetivamente existente dos arcos.

**Editar → Cópia espelhada** escolhe X/Y/ambos e posiciona pelo cursor.
**Matriz de cópias** cria linhas/colunas com passos X/Y ou cópias em torno de um
centro, com orientação opcional. As quantidades incluem o original. O centro
polar pode ser escolhido por clique. Uma matriz admite Undo/Redo único.

**Importar gráfico P&B** aceita PNG, JPG, BMP, TIFF e WebP. Imagens coloridas
são convertidas; ajuste o limiar, inversão, resolução e largura no preview.
Branco/transparência não cria desenho, e preto vira geometria preenchida.
Por padrão, **Posicionar pelo mouse** faz a prévia seguir o cursor após confirmar
o diálogo. Clique para fixar o centro da imagem; **Esc** ou botão direito cancela.
A importação entra no histórico somente após o clique e admite Ctrl+Z/Ctrl+Y.
As regiões geradas pela imagem formam um grupo de seleção durante a sessão.
Para inserir por coordenadas, desmarque essa opção e informe X/Y, que representam
o canto inferior esquerdo da imagem.

## Fiduciais e recortes

**Ferramentas → Inserir fiducial** usa clique/snap e aceita coordenadas exatas,
diâmetro do cobre, abertura da máscara e face F/B/ambas. Cobre e abertura são
inseridos nas camadas correspondentes, criando-as se necessário, com Undo único.

Para rasgos, desenhe objetos comuns e use **Recortes e rasgos da seleção**:
**Rasgo pela largura do traço** remove a área do traço; **Recorte por contorno
fechado** remove o interior. Um rasgo circular pode manter uma ilha central.
Também é possível criar **Nova camada de recortes** e desenhar diretamente nela:
contornos fechados removem o interior e linhas/arcos abertos usam sua largura.

Os objetos são copiados para **Route.Cuts**, preservando o desenho original.
Essa camada usa metadados X2 próprios para conservar sua função ao reabrir.
No 3D, os recortes atravessam substrato e materiais, mesmo se a camada de
roteamento estiver oculta no canvas. No CAM de fabricação, atribua a camada
à operação mecânica adequada ao processo utilizado.

## Preferências

- Edite o valor da grade na barra, inclusive `50 mil`, ou use **Configurar grade**
  para manter uma lista. **N / Shift+N** alternam valores. Snap é independente
  da visibilidade da grade.
- **Teclas de atalho** permite personalizar ações, rejeita duplicações e
  restaura padrões. Os atalhos seguem convenções do KiCad para ações comuns,
  com **Shift+A** para a régua conforme solicitado; a lista completa está no diálogo.
- **Visualizar** alterna cursor pequeno/tela inteira, coordenadas polares
  e negativos em cinza fantasma. Essas opções não alteram o Gerber.
- Durante o processamento, uma ampulheta gira em um cartão no centro da área
  de desenho, tanto no editor quanto no 3D. O texto informa a operação atual.
  Ferramentas aguardando um ponto mantêm apenas o aviso discreto na barra inferior.
- **Mostrar todas as ferramentas à esquerda** distribui os botões em mais
  colunas quando falta altura. A opção vem ativada e é salva nas preferências;
  desativá-la restaura a barra vertical com o comportamento padrão do Qt.

Enquanto há processamento, cliques, atalhos, arrastes e fechamento ficam
bloqueados nas janelas do aplicativo. Diálogos de erro/confirmação da operação
continuam utilizáveis. Os arquivos são lidos e preparados em sequência; a cena
é montada uma única vez ao terminar o lote, sem atualizações reentrantes.
Abrir um lote corresponde a uma ação de Desfazer/Refazer.
Essa proteção evita ações conflitantes; não é garantia contra toda falha externa.

As preferências são persistidas no perfil do Windows, normalmente em
`%LOCALAPPDATA%\EBRANDT Tecnologia\Editor Gerber\preferences.json`.
`EDITOR_GERBER_SETTINGS` permite escolher outro arquivo para testes/instalações.
Novos idiomas usam catálogos JSON em `gerber_editor/locales` e registro em `Locale.languages`.
**Ajuda → Tela de apresentação** reabre a splashscreen; clique fora do link ou Esc fecha.

## Visualizador 3D inicial

**Alt+3**, o ícone do cubo ou **Visualizar → Visualizador 3D** abre a PCB em
janela própria. Botão esquerdo orbita, central/direito desloca, scroll aproxima
e Home enquadra. Há vistas superior, inferior, frontal, lateral e isométrica,
perspectiva/ortográfica, materiais, detalhe da malha e espessura da placa.
Após editar no 2D, a prévia é reconstruída automaticamente ao voltar à janela
3D, inclusive se ela permaneceu aberta. Várias edições são reunidas em uma
atualização, preservando a câmera. Voltar sem alterações não recalcula a PCB.
**Atualizar PCB** continua disponível para solicitar uma reconstrução manual.
**F** inverte frente/verso com animação pelo eixo Y. O pan vertical acompanha
o arraste em ambas as faces. A janela 3D é independente e compartilha o novo
ícone do programa na barra de tarefas.

A função determina a altura: F.Cu/B.Cu, camadas internas, Mask, Silk e Paste.
Ajuste funções no gestor 2D quando necessário. Edge.Cuts fechado fornece o
contorno e recortes; sem ele, a janela informa que estima um retângulo pelos
limites das camadas. Ocultar Edge.Cuts no canvas conserva seu contorno físico.
As funções **Drill / Drill.PTH / Drill.NPTH** recortam furos e rasgos passantes
no substrato e nos materiais. O Gerber legado **fur** é reconhecido como Drill;
arquivos X2 Plated/NonPlated também são reconhecidos. Ocultar essa camada no 2D
conserva seus furos físicos. **Drill drawing / Drillmap** continua sendo desenho
auxiliar. Furos cegos/enterrados exigem stackup e são recusados explicitamente.
Esta função usa dados de furação Gerber ou Excellon.
As trilhas ficam visíveis sob a máscara por cor e relevo. Nomes Inner/Iner/In
numerados são reconhecidos. Para inspecionar camadas internas, oculte substrato
e máscaras na lista de materiais. **Realista** alterna iluminação e reflexos
por material; é um render em tempo real, sem ray tracing.

Mudar **Detalhe 3D** reutiliza as geometrias já compostas da PCB e recalcula
apenas a malha para a nova tolerância. Voltar a um detalhe já calculado usa
o cache, sem gerar a PCB novamente. O cache mantém até três combinações de
detalhe/espessura, limitado a 128 MiB de vértices. Editar a PCB atualiza os
resultados afetados; **Atualizar PCB** também reaproveita os cálculos válidos.
Câmera e materiais ocultos
são preservados ao mudar o detalhe.

Em **Arquivo**, o 3D exporta **JPG** com largura/altura e qualidade escolhidas,
**WRL com cores** e **STEP com cores**. JPG usa renderização na resolução pedida,
até 8192 px por lado e 32 MP. STEP usa sólidos OpenCascade/AP214, reabertos e
validados antes de gravar; curvas seguem a aproximação do detalhe 3D selecionado.
WRL usa metros e STEP usa mm, conservando a origem XY dos Gerbers. Os modelos
exportam os materiais visíveis; a inversão da câmera não muda o modelo físico.
As três exportações compartilham uma última pasta própria, preservada ao
reiniciar. **Visualizar** oferece vistas, enquadramento, inversão e materiais;
**Preferências**, perspectiva, render Realista, espessura/detalhe, atalhos e
idioma. **Ajuda** possui os mesmos itens do editor principal, incluindo Relatar problemas.

O backend STEP já está instalado neste ambiente. Para uma nova instalação:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-step.txt
```

O substrato é um sólido extrudado, com superfícies dos materiais em alturas
distintas. Esta versão não inclui componentes STEP,
metalização de furos ou edição completa de stackup. Usa Qt/OpenGL 3.3 e malhas
em worker; a aproximação da prévia não altera os Gerbers.

## Backups e apoio ao criador

Na inicialização pelo projeto, cada nova versão gera
`Backup/Editor_Gerber_vVERSAO.zip`. ZIPs existentes são preservados e verificados.
A pasta está no `.gitignore`. São incluídos código, recursos, documentação e
dependências declaradas; `.venv`, caches, saídas de testes e os próprios backups
ficam de fora. Gerbers em outras pastas não fazem parte do backup do software.

```powershell
.\.venv\Scripts\python.exe -m scripts.backup_project
```

**Ajuda → Suporte / doar ao criador** oferece QR Pix sem valor fixo, chave e
Pix Copia e Cola. O campo PayPal fica identificado como “link em breve” até
receber a URL. Sobre e splashscreen mostram SOFTWARE LIVRE/GPLv3.
A frase de convite ao apoio nessas duas telas também abre os dados de doação.

## Compatibilidade

RS-274X: apertures C/R/O/P e furos circulares em flashes; linhas, arcos e regiões;
polaridade sequencial dark/clear, mm/inch, supressão L/T e atributos X2.
Inclui comandos legados IPPOS/LN/IN/G54 e G1/G2/G3/D1/D2/D3, CAMMaster 3.3 e
macros 1/4/5/20/21/22 com expressões Decimal.

**Preservation** conserva bytes sem edição e mantém comandos originais ao
excluir/adicionar. **Normalized** reemite a geometria lógica, mantendo a resolução
necessária aos arcos legados; é sugerido ao mover objetos importados.
Não há ajuste silencioso da geometria existente. Novos desenhos respeitam a
resolução da camada; fontes muito pequenas e gráficos mais finos que essa
resolução são recusados com orientação.

Ainda não suportados: macro 6/7, draw com macro/aperture furada, AB/SR,
transformações de entrada Gerber, IPNEG, SVG e projeto `.gproj`.
Arquivos com 100 mil objetos podem consumir muita memória; edição e exportação
ainda fazem processamento síncrono, com indicador visível.

## Registros de falhas

Na execução pelo projeto, `output/logs/editor_<PID>.log` guarda mensagens,
exceções Python e avisos Qt. `fault_<PID>.log` recebe o diagnóstico de falhas
nativas quando o Python consegue registrá-las; fica vazio se não houve falha.
Isso funciona também com `Iniciar.ps1`, que usa `pythonw` sem console.
`EDITOR_GERBER_LOG_DIR` permite escolher outra pasta. Na instalação empacotada,
o padrão é a pasta de dados locais do aplicativo, em `logs`.

A revisão 0.5.1 também conserva os itens do gestor ao trocar camada ou
visibilidade e adia callbacks destrutivos até o evento Qt terminar. Detalhes
da investigação e dos testes estão no guia desta revisão.

[Mudanças da versão 0.12.2](ENTREGA_0_12_2.md) · [Versão 0.12.1](ENTREGA_0_12_1.md) · [Versão 0.12.0](ENTREGA_0_12.md) · [Versão 0.11.0](ENTREGA_0_11.md) · [Validação](VALIDATION.md) ·
[Arquitetura](README_DESIGN.md) · [Roadmap](ROADMAP.md).

## Desenvolvimento

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m compileall -q gerber_editor scripts tests
.\.venv\Scripts\python.exe -m gerber_editor --demo --smoke-test
```

Execução: PySide6-Essentials, Shapely, NumPy e QRCode. OpenCascade é o componente
opcional de STEP. Pytest/Ruff são apenas ferramentas
de desenvolvimento. Gerbonara é um verificador opcional usado nesta entrega,
fora das dependências do aplicativo. Os testes automatizados usam preferências
temporárias e não gravam nos arquivos originais do usuário.
