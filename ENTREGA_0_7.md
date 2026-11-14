# Editor Gerber 0.7.0 — zoom, pan e atualização de objetos

Entrega de 13/11/2026. Esta revisão atende às pausas que continuavam presentes
na versão 0.6 durante navegação e edição de objetos em camadas grandes.

## O que mudou

O renderer divide camadas com pelo menos 512 objetos em blocos de 16 mm,
ampliados automaticamente se necessário para limitar a grade a 1.024 células.
Um índice espacial recupera os objetos de cada bloco, mantendo a ordem de
polaridades do Gerber. Uma alteração recompõe os blocos tocados pelos limites
antigos e novos do objeto e conserva os demais. Inclusões, exclusões, undo e
mudanças de visibilidade seguem a mesma regra; reordenar objetos recompõe a
camada para manter a sequência de fabricação correta.

Na tela, são pintados apenas os blocos expostos. Cada um inclui uma margem
geométrica, desenhada sob clip retangular, para evitar linhas de junção e
acúmulo de transparência. A aproximação das curvas continua em **0,001 mm**:
esta versão não diminui o detalhe da geometria para ganhar velocidade.
Em zoom extremamente afastado, quando a margem ficaria menor que um pixel,
o renderer usa o desenho completo para preservar o antialiasing.

O pan dispensa a busca de pontos magnéticos enquanto a vista se desloca.
O resultado do snap é reaproveitado quando cursor, escala, âncora e desenho
permanecem iguais. A apresentação das camadas deixou de participar de consultas
de hit testing; os objetos continuam com suas formas individuais de seleção.

O cache de imagens do Qt passou a ter orçamento de **64 MiB sob demanda**,
permitindo conservar os pixmaps de várias camadas simultaneamente. Isso evita
que desenhar a camada seguinte expulse imediatamente o cache da anterior.
Os caches de geometrias e paths ficam fora desse orçamento e dependem do projeto.

## Comparação com a versão 0.6.0

Ensaios nos mesmos Gerbers, em processos separados, usando o código arquivado
da 0.6.0 e as mesmas bibliotecas. Raster Qt offscreen em 1200 × 800. As medianas
usam sete quadros para navegação/cor e três atualizações para edição. O tempo
inclui apresentar/capturar o quadro; não se trata de FPS medido na janela nativa.

Valores aproximados, arredondados; os relatórios JSON conservam todas as amostras.

| Camada de cobre `olc` — 110.457 objetos | 0.6.0 | 0.7.0 | Velocidade relativa |
|---|---:|---:|---:|
| Zoom | 0,922 s | 0,127 s | 7,3× |
| Pan | 0,035 s | 0,018 s | 2,0× |
| Troca de cor | 0,934 s | 0,121 s | 7,7× |
| Atualizar um objeto pequeno | 27,02 s | 1,41 s | 19,1× |

Na atualização medida, apenas **2 dos 216 blocos** precisaram de recomposição.
A edição moveu uma linha pequena, quantizada à resolução do arquivo, e também
foi medida ao desfazer e reaplicar a mesma alteração.

| Serigrafia `srlc` — 11.607 objetos | 0.6.0 | 0.7.0 | Velocidade relativa |
|---|---:|---:|---:|
| Zoom | 0,133 s | 0,044 s | 3,0× |
| Troca de cor | 0,130 s | 0,035 s | 3,7× |
| Atualizar um objeto pequeno | 3,85 s | 0,182 s | 21,1× |

O pan da serigrafia já estava na ordem de poucos milissegundos. O ensaio com
cursor sobre a placa variou de 5,0 para 7,3 ms, sem ganho nessa situação.
Os ganhos mais importantes
desta etapa são o zoom e a recomposição local dos objetos. Nenhum desses
fatores representa um multiplicador universal para todo o aplicativo.

## Validação

- **146 testes passaram**, incluindo 12 novos casos de composição por células,
  ordem dark/clear, movimento/exclusão/undo, visibilidade, camada vazia,
  pintura em várias escalas e transparências, invalidação do snap e cache
  simultâneo de oito camadas. Ruff e formatação foram aprovados.
- A composição das células foi comparada com a composição integral: diferença
  de área inferior a 1e-8 mm² nos casos de teste, sem alterar objetos lógicos.
- Nas duas camadas reais, as vistas inicial, recolorida, selecionada, com
  negativos e após edição foram comparadas com a 0.6. A divisão altera pequenos
  arredondamentos do antialiasing: diferença máxima de **3 níveis em 255 por
  canal**, com erro médio inferior a **0,0003 nível por canal** nesses ensaios.
  Não se afirma igualdade pixel a pixel entre as duas arquiteturas.
- A imagem com cache e a pintura direta coincidiram na vista de referência.
  Os testes de diferentes escalas também verificam o cache nas camadas opacas.
- **Windows nativo aprovado** com a serigrafia: importação assíncrona,
  seleção por mouse, cor/opacidade/visibilidade, movimento de objeto, undo,
  zoom ancorado no cursor, pan pelo botão central, exclusão, exportação e
  reabertura. A movimentação seguida de captura levou cerca de **0,28 s**
  nessa verificação, incluindo o controlador e a interface.
- Os SHA-256 dos Gerbers de entrada permaneceram iguais. O parser, o modelo
  Decimal, as regras de edição e o writer mantêm a implementação anterior.
  Os dados de saída passaram pelas comparações de reabertura existentes.

## Memória e limites

Esta etapa troca algum espaço de cache por menos espera. No ensaio inicial,
a memória residente após apresentar a cena cresceu de aproximadamente
**708 para 764 MiB** na `olc` e de **214 para 233 MiB** na `srlc`. São
fotografias do processo, sujeitas ao alocador e ao Windows, sem equivaler a
limites de RAM. Não se apresenta esta revisão como redução universal de memória.

Editar uma região grande, uma linha muito longa ou muitos objetos ainda pode
invalidar vários blocos. As células afetadas são recompostas em sequência;
não houve introdução de paralelismo nesta revisão. O índice espacial também
é reconstruído para o novo snapshot. Abertura, seleções enormes e o 3D mantêm
seus custos próprios. A primeira abertura não recebeu garantia de aceleração:
os ensaios mostraram melhora na camada grande e variação na serigrafia.

## Artefatos e reprodução

[Relatório olc](output/v07/performance_olc.json) ·
[Relatório srlc](output/v07/performance_srlc.json) ·
[Windows nativo](output/v07/native/report.json) ·
[Referência da 0.6.0](output/v07/baseline_manifest.json).

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check gerber_editor tests scripts
.\.venv\Scripts\python.exe -m scripts.benchmark_2d "C:\Temp\Gerbers\PCB Teste\olc" --implementation output/v07/baseline_060 --output output/v07/baseline_olc --edits
.\.venv\Scripts\python.exe -m scripts.benchmark_2d "C:\Temp\Gerbers\PCB Teste\olc" --output output/v07/optimized_olc --edits
.\.venv\Scripts\python.exe -m scripts.summarize_benchmark_2d output/v07/baseline_olc output/v07/optimized_olc --output output/v07/performance_olc.json --max-channel-error 4 --max-mean-error 0.005
.\.venv\Scripts\python.exe -m scripts.verify_v06 --file "C:\Temp\Gerbers\PCB Teste\srlc" --output output/v07/native --exercise-edits
```

O script de verificação nativa da revisão anterior foi ampliado com parâmetros
de saída e edição para ser reutilizado sem sobrescrever seus registros históricos.
Os diagnósticos ficam em `output/v07`, excluída do ZIP de fontes. O backup
da versão 0.6.0 foi preservado e conferido contra a referência usada nos ensaios.

[ZIP da versão 0.7.0](Backup/Editor_Gerber_v0.7.0.zip).
Para carregar o código atualizado, salve os trabalhos abertos, feche o editor
e abra novamente pelo `Iniciar.bat`.
