# Verificação — versão 0.8.0 (13/11/2026)

## Furação, ordem visual, ícone e maximização

- **160 testes passaram em 74,88 s**, com 14 novos casos para detecção de Drill,
  geometria vazada, rasgos, furos pequenos, paredes, camada Drill oculta,
  dados blind/buried, STEP, ordenação inicial, setas/undo/redo e ícone.
- Um ponto dentro do furo foi classificado fora do sólido STEP pelo
  OpenCascade; um ponto no material foi classificado dentro. Os normais
  das paredes dos furos apontam para a cavidade.
- **Windows/OpenGL nativo aprovado**: editor e 3D maximizados, ordem automática,
  subir/descer e undo/redo, framebuffer com furos e rasgo, exportações STEP/WRL.
- No arquivo real `fur`, foram identificados 1.161 flashes de diâmetros
  0,85/1,15/1,35/1,45/2,1 mm. Todos os centros ficaram fora do substrato;
  o Gerber original manteve seu SHA-256. A malha de verificação do substrato
  gerou 239.856 triângulos, usando um retângulo de teste como contorno.
- O ícone foi conferido em fundo claro/escuro nos tamanhos 16 a 128; ICO inclui
  também 256. Gerado com imagegen, com prompt em assets/ICON_PROMPT.md.
- A primeira camada da lista define a frente, substituindo a promoção automática
  da camada ativa. Ordenação afeta apenas a sessão e não as primitivas Gerber.
- Drillmap não remove material. Excellon ainda não é lido; furação cega/enterrada
  é recusada no 3D sem stackup. A furação passante Gerber é conservada mesmo
  quando sua camada é ocultada no 2D.
- Ruff e formatação aprovados; preferências/saídas isoladas em `output/v08`.

[Guia 0.8.0](ENTREGA_0_8.md) · [Relatório nativo](output/v08/native/report.json) ·
[Ícone em tamanhos pequenos](output/v08/native/03_icon_sizes.png) ·
[Furos no 3D](output/v08/native/04_3d_through_holes.png).

## Registro da entrega 0.7.0 (13/11/2026)

## Composição espacial e navegação 2D

- **146 testes passaram em 73,83 s**, incluindo 12 novos casos para células,
  dark/clear, visibilidade, exclusão/undo/reordenação, geometrias vazias,
  pintura em cinco combinações de escala/opacidade, snap e múltiplos caches.
  Os 119 arquivos Python passaram na formatação e Ruff foi aprovado.
- Camadas grandes usam células de 16 mm e STRtree, com grade limitada a 1.024
  células. Edições invalidam células nos limites anteriores/novos do objeto;
  nenhuma simplificação das curvas foi aplicada.
- Comparação com código arquivado da 0.6.0, em processos separados e sem
  profiler: na `olc` de 110.457 objetos, zoom de **0,922 para 0,127 s**,
  pan de **0,035 para 0,018 s**, cor de **0,934 para 0,121 s** e alteração
  de uma linha pequena de **27,02 para 1,41 s**. Apenas 2/216 células mudaram.
- Na `srlc`, zoom de **0,133 para 0,044 s** e edição de **3,85 para 0,182 s**.
  O pan com cursor sobre a placa variou de 5,0 para 7,3 ms, sem melhoria
  nesse ensaio; não se afirma ganho universal para toda ação/arquivo.
- Comparadas as vistas inicial/cor/seleção/negativos/edição: diferença máxima
  de 3/255 por canal e média inferior a 0,0003, por arredondamento do
  antialiasing. O cache e a pintura direta coincidiram na vista de referência.
- **Windows nativo aprovado** com 11.607 objetos: seleção por mouse,
  cor/opacidade/visibilidade, movimento/desfazer, zoom ancorado e pan central,
  exclusão/exportação/reabertura. Movimento e captura levaram 0,28 s nessa
  execução. Timer da GUI recebeu 159 pulsações no carregamento; nenhum erro.
- Memória residente cresceu aproximadamente 56 MiB na `olc` e 20 MiB na
  `srlc` por manter células e índice espacial. O cache de imagens tem orçamento
  de 64 MiB sob demanda, separado das geometrias; oito camadas reutilizaram
  seus pixmaps sem novas chamadas de pintura no teste.
- Originais externos mantidos em bytes; referência 0.6.0 conferida contra
  o backup. Parser/modelo/writer continuam sob as verificações anteriores.

[Guia 0.7.0](ENTREGA_0_7.md) · [Desempenho olc](output/v07/performance_olc.json) ·
[Desempenho srlc](output/v07/performance_srlc.json) ·
[Relatório nativo](output/v07/native/report.json).

## Registro da entrega 0.6.0 (13/11/2026)

## Otimização incremental da cena 2D

- **134 testes passaram** em 69,14 s. Os oito novos casos verificam pintura
  apenas dos selecionados, clique/janela/snap preservados, aparência sem
  recomposição, reutilização de itens, edição/exclusão/undo/fechamento e
  equivalência entre cache e pintura direta em diferentes escalas/opacidades.
- **Ruff aprovado** em `gerber_editor`, `tests` e `scripts`.
- **Windows nativo aprovado:** importação assíncrona de `srlc` com 11.607
  objetos, seleção por mouse, destaque, cor/opacidade/visibilidade e undo,
  exclusão/exportação/reabertura e restauração dos objetos. Timer da GUI
  registrou 163 pulsações durante a importação; nenhum erro foi registrado.
  As preferências e saídas desse ensaio ficaram em `output/v06/native`.
- `olc` e `srlc` foram comparados com o código da 0.5.2 em processos separados,
  sem profiler nos tempos. As quatro imagens de cada arquivo coincidiram
  pixel a pixel entre as versões, e os originais ficaram idênticos em bytes.
- `olc`: deslocamento **36,6×**, zoom **2,32×**, troca de cor **4,37×**.
  `srlc`: deslocamento **16,1×**, troca de cor **2,46×** e zoom próximo do
  anterior (153 para 161 ms). São tempos de quadro com captura offscreen,
  não FPS da janela nativa.
- Com a abertura mantida igual por arquivo, o ciclo calculado de uma abertura,
  20 deslocamentos, dez zooms e cinco trocas de cor ficou **71,8% mais rápido**
  na `olc` e **31,5%** na `srlc`. A abertura/composição continua como próxima
  etapa; não se atribui ganho universal ao módulo.
- O ZIP datado da 0.5.2 conservou seu SHA-256, e a cópia de referência foi
  conferida arquivo a arquivo contra ele.

[Guia 0.6.0](ENTREGA_0_6.md) · [Desempenho olc](output/v06/performance_olc.json) ·
[Desempenho srlc](output/v06/performance_srlc.json) ·
[Relatório nativo](output/v06/native/report.json).

## Registro da entrega 0.5.2 (12/11/2026)

## Inicialização, menus, caminhos e importação em lote

- **126 testes passaram** em 74,34 s. Os 12 testes novos verificam a splash
  mínima de quatro segundos, proteção contra fechamento antecipado, links de
  website/apoio, paleta completa em janelas pequenas, persistência das pastas,
  menus do 3D e idiomas, bloqueio de entrada nas duas janelas, diálogo modal
  utilizável durante uma operação, arquivos auxiliares, falha/retry de lote e
  recebimento de novos pedidos sem reentrada durante a aplicação dos resultados.
- A abertura de um lote reconstrói a cena uma vez. O teste com um pedido
  adicional durante o recebimento dos resultados confirma uma montagem por
  lote e Desfazer/Refazer conjunto. A regressão de arrastar/soltar e Esc passou
  com liberação imediata da entrada ao fim de operações rápidas.
- A geometria e a ordem dos objetos continuam sob as validações anteriores.
  O nome fp-info-cache não elimina conteúdo Gerber válido com esse nome.
- Ruff, formatação, compilação e dependências passaram nas verificações.
- **Windows/OpenGL nativo aprovado:** splash visível por 4,003 s, todos os
  botões laterais acessíveis em 950 × 500, menus do 3D, exportações WRL/JPG e
  persistência da pasta de exportação exercitadas.
- Selecionados os 12 arquivos da pasta PCB Teste: **11 Gerbers abertos, 243.347
  objetos**, um fp-info-cache ignorado e nenhum erro. Preparação e montagem
  do lote concluídas em **135,821 s** neste ambiente. Cliques, Ctrl+N e fechar
  foram bloqueados durante o trabalho. Os SHA-256 dos 12 originais foram
  comparados antes/depois e permaneceram idênticos.
- A verificação nativa usa QEventLoop com polling por QTimer. O ciclo anterior
  de QTest.qWait repetido retardava workers Python e foi substituído no script
  para medir o comportamento normal do aplicativo.

[Guia 0.5.2](ENTREGA_0_5_2.md) · [Relatório nativo](output/v052/native_report.json).

## Registro da entrega 0.5.1

## Atividade, retorno ao 3D e estabilidade do gestor

- **114 testes passaram** em 60,97 s. Os 11 testes novos cobrem rotação/posição
  do indicador, operações aninhadas, atualização ao ativar o 3D, agrupamento de
  edições, câmera, revisão antiga, exportação em curso, edição em andamento,
  erro/retry do worker, fechamento de camadas, itens Qt estáveis e logs.
- **Windows/OpenGL nativo aprovado:** rotação no editor e no 3D, 30 ciclos de
  seleção/visibilidade por mouse, três edições agrupadas em uma atualização ao
  retornar ao 3D e conservação da câmera. O 3D já aberto permaneceu sem novos
  cálculos enquanto o editor tinha foco. Retorno sem edição não reconstrói.
- Importação assíncrona do `srlc` com 11.607 objetos e dez ciclos adicionais de
  visibilidade. SHA-256 antes/depois idêntico ao registro da revisão 0.5 abaixo.
- Registro APPCRASH do Windows localizado: Qt6Widgets.dll, 0xc0000005. Foi
  corrigida a invalidação de QTreeWidgetItems durante eventos da própria árvore,
  compatível com o intervalo do endereço da falha. Não há pilha original para
  afirmar causa definitiva. Novos logs registram Python/Qt/threads e falhas nativas.
- Ruff e formatação aprovados; nenhum Gerber externo foi gravado pelos testes.

[Guia 0.5.1](ENTREGA_0_5_1.md) · [Relatório nativo](output/v051/native_report.json).

## Registro da entrega 0.5.0

## Edição, roteamento, exportação e apoio ao criador

- **103 testes passaram** na suíte completa. Incluem backup ZIP por versão,
  filtros de arquivos, camada ativa à frente, opacidade inicial, comprimento/
  ângulo/coordenadas sincronizados, duplo clique, texto lembrado, novos pontos
  de snap, fiduciais F/B, Undo, regiões, recortes, rasgos e anéis.
- Nomeação F.Cu/B.Cu/Inner/Iner/In e relevo do cobre sob a máscara verificados.
  Ocultar a camada de recortes conserva a abertura física no modelo.
- **Teste nativo Windows/OpenGL aprovado**: oito partes materiais, 3.728
  triângulos, furo e rasgo visíveis, novo ícone e janela 3D sem proprietário
  Win32 (`GW_OWNER=0`). A animação de inversão e a exportação STEP pela
  interface, em segundo plano, foram exercitadas.
- O render JPG gerou **2560 × 1440 pixels** pelo framebuffer na resolução
  solicitada. STEP de aproximadamente 11,3 MB e WRL de 0,57 MB foram gerados
  com cores. O STEP é uma montagem CAD em mm; o WRL usa metros.
- STEP reaberto com OpenCascade, sólidos válidos e cores de materiais presentes.
  O caso de contorno tangente foi corrigido com tolerância CAD limitada e
  verificação de volume. WRL lido por importador VRML independente (VTK).
- QR Pix comparado com o CRC `1D3D` do exemplo oficial do Banco Central.
  **ZXing-C++** decodificou o PNG e encontrou exatamente o payload e a chave
  fornecida. Sem valor fixo; PayPal continua como link pendente informado.
- GPLv3 escolhida pelo criador, com texto oficial em LICENSE, identificação
  SOFTWARE LIVRE no Sobre/splash e copyright incluído.
- O `srlc` atual foi lido, sem gravação na origem, com **11.607 objetos** e
  malha de 32.315 triângulos. SHA-256 antes/depois da execução:
  `0e13e3bc082c85a7b0d52a6ec2b3c0dba020b14483622a9addb44c370c18a9c5`.
  Números das versões anteriores são registros históricos, não um bloqueio
  às edições feitas pelo usuário entre revisões.

[Guia dos pedidos](ENTREGA_0_5.md) · [Relatório](output/v05/report.json) ·
[Teste nativo](output/v05/native_report.json) ·
[Leitor QR independente](output/v05/qr_verification.json).

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_v05 --real "C:\Temp\Gerbers\PCB Teste\srlc"
.\.venv\Scripts\python.exe -m scripts.verify_v05 --native-3d
.\.venv\Scripts\python.exe -m scripts.backup_project
```

O ambiente com backend STEP está preparado; os pacotes instalados constam em
requirements-tested.txt. Para instalações novas, requirements-step.txt adiciona
OpenCascade e suas dependências. A prévia usa aproximação de curvas e alturas
de materiais padrão; não substitui um stackup de fabricação completo.

## Registro da entrega 0.4

## Edição pelo cursor e PCB 3D

- **81 testes passaram**: regressões anteriores, Ortho 45°/90°, ímã de pontos,
  Shift real no canvas, arraste/M/Esc/Undo, clipboard e recorte, espelhamento,
  matrizes retangular/polar com e sem rotação, apertures independentes,
  comprimento/raio/ângulo, textos de sessão e malha com recortes.
- Ruff e formatação aprovados. Dependências de execução continuam sendo
  PySide6-Essentials, NumPy e Shapely (mínimo 2.1 para triangulação restrita).
- **Teste nativo Windows/OpenGL 3.3 aprovado**, com 2.712 triângulos e cinco
  materiais. Framebuffer e janela foram capturados em vistas isométrica e
  inferior. Troca imediata para inglês e polegadas preservou a espessura
  física de 1,6 mm. Não se trata de um mockup do visualizador.
- O `srlc` encontrado nesta revisão contém **11.540 objetos**. Seu conteúdo foi
  lido para gerar uma malha de 31.464 triângulos, sem gravar na origem.
  Três objetos foram copiados/espelhados/girados em saídas de teste; os 11.540
  originais mantiveram geometria e ordem nos dois modos de exportação.
- Gerbonara confirmou por parser independente **11.543 objetos** nas duas
  saídas e igualdade das primitivas/polaridades dos 11.540 objetos originais.
  A adaptação lexical G1/G2/G3 já descrita abaixo continua explícita.
- O SHA-256 atual foi conferido antes e depois da execução:
  `529763d32f16b3ac1e06493c7924dd7d43d4c0630c865c299a6f72e25ffa53d7`.
  As quantidades/hash da seção anterior são registros históricos da versão 0.3,
  não uma expectativa de que o arquivo do usuário permaneça imutável entre revisões.

[Guia e capturas](ENTREGA_0_4.md) · [Relatório de dados](output/v04/report.json) ·
[Renderização 3D nativa](output/v04/native_3d_report.json) ·
[Comparação independente](output/v04/independent_report.json).

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_v04 --real "C:\Temp\Gerbers\PCB Teste\srlc"
.\.venv\Scripts\python.exe -m scripts.verify_v04 --native-3d
# Opcional, com Gerbonara em output/qa_backend:
.\.venv\Scripts\python.exe -m scripts.verify_v04_independent "C:\Temp\Gerbers\PCB Teste\srlc"
```

A primeira versão 3D usa o contorno funcional Edge.Cuts ou informa a estimativa
pelos limites. Componentes STEP, Excellon, metalização de furos e um editor de
stackup completo ainda não são implementados. Não há alegação de homologação CAM.

## Registro da entrega 0.3

## Revisão dos dezesseis pedidos

- **62 testes automatizados** cobrem regressões do parser/writer e as novas
  ações de salvar, zoom ancorado, inversão real de pixels da régua, medidas,
  formas, fontes com vazados, raster colorido, cotas, unidades, camadas,
  fechamento reversível, preferências, atalhos, idiomas e splashscreen.
- Capturas Qt revisadas em português e inglês; régua de 1 in exibida junto ao
  cursor, diálogos de fontes/cotas/atalhos e composição final da splashscreen.
- Inicialização nativa Windows `--demo --smoke-test --lang en`, com splashscreen,
  encerrou com código **0**. Isso verifica a criação da janela e seu event loop;
  não substitui uma inspeção interativa completa da janela nativa.
- A versão atualizada foi deixada aberta com `srlc`; o processo confirmou a
  janela **srlc — Editr Gerber 0.3.0**, respondendo, sem erros no log de inicialização.
- O script `verify_v03` cria 29 objetos de demonstração e testa exportação e
  reabertura nos dois modos. No arquivo real `srlc`, esses 29 objetos foram
  acrescentados em cópias, conservando os **12.132 objetos originais**.
- SHA-256 do original permanece
  `288b1ccd7a285f3195d931007f6b54f24f0b8b2bd5f1478ed66e10e1131d2f5a`.
- **Gerbonara 1.6.3**, instalado somente em `output/qa_backend`, leu as saídas
  Preservation e Normalized e confirmou igualdade das primitivas geométricas,
  tipos e polaridades dos 12.132 objetos originais, na mesma ordem. Não é uma
  dependência de execução do aplicativo.
- O mesmo backend renderizou fontes, cotas e formas dos arquivos de demonstração;
  o teste confirmou o vazado de “O” e sua transparência sobre geometria existente.

Adaptações explícitas do verificador independente: Gerbonara não aceita os
aliases legados G1/G2/G3 deste CAMMaster; apenas sua grafia foi completada
em memória para G01/G02/G03 nas entradas comparadas. Nenhuma coordenada foi
alterada. Seu exportador SVG direto pinta primitivas off de macros na cor de
fundo global. Por isso, o script renderiza cada objeto isoladamente com o
avaliador de macros/SVG do Gerbonara e aplica a polaridade na composição.
Não usa geometrias do editor. Essa evidência é uma conferência adicional,
sem alegar homologação de fabricação ou compatibilidade universal.

Também foi corrigida a união de contornos de regiões, conforme a especificação
Gerber: contornos separados em G36/G37 não criam furos por simples aninhamento.
Vazados de fontes usam exposições locais de macro; não apagam desenhos por baixo.

- [Checklist dos 16 pedidos e capturas](ENTREGA_0_3.md)
- [Relatório da revisão e srlc](output/v03/report.json)
- [Relatório independente](output/v03/independent_report.json)
- [Renderização independente da demonstração](output/v03/showcase_normalized_independent.png)
- [Splashscreen](output/v03/06_splashscreen.png)

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_v03 --real "C:\Temp\Gerbers\PCB Teste\srlc"
# Opcional: requer Gerbonara instalado em output/qa_backend.
.\.venv\Scripts\python.exe -m scripts.oracle_v03 --real "C:\Temp\Gerbers\PCB Teste\srlc"
```

As execuções usam preferências temporárias em `output/v03`. Somente cópias
de verificação são gravadas ali. As fontes do Windows são carregadas localmente
e não redistribuídas. Recursos CAM ainda recusados estão descritos no README.

## Registro da entrega 0.2

Ambiente: Windows, Python 3.13.12, PySide6-Essentials 6.12.0, Shapely 2.2.0,
pytest 9.2.0 e Ruff 0.17.4. As versões instaladas estão em
`requirements-tested.txt`; dependências compatíveis estão nos arquivos normais.

Resultados da entrega:

- `python -m pytest -q`: **46 testes passaram** (16,96 s).
- Ruff check e formatação: aprovados.
- Compileall de código, scripts e testes: aprovado.
- `pip check`: sem dependências quebradas.
- `python -m gerber_editor --demo --smoke-test`: inicialização e event loop,
  encerramento com código 0.
- Aplicação iniciada no Windows com o arquivo real `srlc`. A inspeção automatizada da
  janela nativa não pôde ser feita: o serviço Computer Use estava indisponível
  (`native pipe ... os error 2`), inclusive após reinicialização do cliente.
  A revisão visual foi feita nas imagens renderizadas pelo próprio Qt.

## Arquivos reais fornecidos

Pasta lida: `C:\Temp\Gerbers\PCB Teste`. Os originais não foram gravados ou
renomeados. O arquivo `fp-info-cache` foi identificado como auxiliar do KiCad,
sem cabeçalho Gerber; os outros dez passaram na verificação completa.

| Arquivo | Objetos | Apertures macro | Resultado |
|---|---:|---:|---|
| 100606-V1-4.mec | 12.432 | 0 | aprovado |
| cantoneiras | 512 | 0 | aprovado |
| fur | 1.161 | 0 | aprovado |
| mslc | 3.528 | 2 | aprovado |
| msls | 1.878 | 2 | aprovado |
| olc | 110.457 | 2 | aprovado |
| ols | 88.507 | 2 | aprovado |
| rasg-150mm | 324 | 0 | aprovado |
| splc | 1.401 | 0 | aprovado |
| srlc | 12.132 | 0 | aprovado |

Para cada arquivo: parsing, geração/composição das geometrias, renderização da
janela, seleção por área, Delete, Undo/Redo e ambos os modos de exportação.
Reabertura compara todas as geometrias e atributos dos objetos restantes.
Preservation sem edição é idêntico em bytes à origem, e SHA-256 confirma que
os originais permaneceram intactos. O teste de exclusão remove uma pequena
marcação geométrica; não afirma ter identificado automaticamente um logo.

No `srlc`, a área de teste selecionou dois objetos. Restaram 12.130 objetos com
os mesmos dados lógicos. A causa inicial era a recusa de `IPPOS`/`LN`, não a
falta de extensão. As macros outline presentes em `mslc/msls/olc/ols` também
passaram. Uma verificação adicional confirmou que a função detectada por `LN`
se conserva ao normalizar/reabrir com um nome de arquivo diferente.

- [srlc aberto na nova interface](output/real_verification/srlc_original.png)
- [Detalhe da seleção real](output/real_verification/srlc_selection_detail.png)
- [srlc após excluir a marcação de teste](output/real_verification/srlc_edited.png)
- [Relatório completo da pasta](output/real_verification/report.json)

Reprodução (saídas somente em `output/real_verification`):

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_folder "C:\Temp\Gerbers\PCB Teste" --capture
```

Desempenho observado na preparação de geometria: aproximadamente 9 s em `srlc`,
34 s em `ols` e 45 s em `olc`. A importação da interface usa worker; o teste
completo, que inclui várias exportações e recomposições, leva mais tempo.
As camadas de 100 mil objetos consomem bastante memória; tiles/LOD e workers
de edição/exportação continuam no roadmap.

## Caso de serigrafia

O teste Qt envia arraste real ao viewport, pressiona Delete e verifica Undo/Redo.
A janela em X=50–78 / Y=5–19 mm seleciona **84 primitivas** do logo/marcação.
A demonstração tem **340 objetos**; após excluir, restam **256**.
As identidades e a ordem dos objetos restantes são verificadas contra a lista
original. Exportação preservation e normalized são reabertas e comparadas
objeto a objeto, incluindo coordenadas Decimal, curvas, apertures, polaridade e
atributos X2. O arquivo original continua idêntico em bytes.

Reprodução e imagens:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_mvp
```

- [Original](output/verification/01_original.png)
- [Seleção](output/verification/02_selected.png)
- [Logo removido](output/verification/03_deleted.png)
- [Arquivo reaberto](output/verification/04_reopened.png)
- [Relatório JSON](output/verification/report.json)
- [Gerber preservado editado](output/verification/silkscreen_preservation_edited.gbr)
- [Gerber normalizado editado](output/verification/silkscreen_normalized_edited.gbr)

Os artefatos da demonstração são sintéticos; os da pasta real são cópias de
verificação. Todos ficam em `output/`, ignorada pelo Git. O script
carrega uma fonte instalada localmente para renderização offscreen no Windows;
não copia nem redistribui fontes do sistema.

## Limite da evidência da versão 0.2

Os testes demonstram o subconjunto implementado com fixtures e dez arquivos
reais. Na versão 0.2 não houve conferência em backend CAM independente. Primitivas macro
6/7, AB/SR, transformações Gerber e Excellon continuam recusados explicitamente.
Não se afirma compatibilidade universal ou homologação para fabricação.
