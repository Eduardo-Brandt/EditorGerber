# Editor Gerber 0.6.0 — otimização do módulo 2D

Retomada em 13/11/2026 após o reinício do computador. O código da aplicação
ainda correspondia à versão 0.5.2 arquivada; a análise anterior e a cópia de
referência em `output/v06/baseline_052` foram recuperadas e verificadas.

## Alterações

- Cor, opacidade e visibilidade atualizam a cena existente sem reconstruir
  geometrias ou recriar os objetos de seleção.
- Edições adicionam, removem ou atualizam os itens alterados. Itens e caches
  de camadas sem alterações são conservados.
- Objetos sem seleção mantêm suas formas de clique e snap, mas dispensam
  chamadas Python de pintura. O destaque acompanha as mudanças de seleção.
- Camadas opacas reutilizam o desenho durante deslocamentos pelo cache de
  dispositivo do Qt. Mudanças de escala, cor e geometria invalidam esse cache.
- Camadas transparentes usam pintura direta, evitando diferenças de
  arredondamento de alpha observadas na comparação de imagens.
- Grupos gráficos por camada tornam a ativação e a visibilidade operações
  sobre o grupo; o enquadramento reutiliza os limites já preparados.

A implementação continua em Python/PySide6, sem novas dependências.
Os dados Decimal, as operações dark/clear e o salvamento Gerber conservam
a implementação anterior.

## Medições na camada de cobre `olc`

Arquivo real com **110.457 objetos**, comparado com o código da 0.5.2 em
processos separados e usando as mesmas bibliotecas. Qt raster offscreen em
1200 × 800, medianas de sete amostras por ação, sem profiler no cronômetro.
Os tempos incluem a captura do quadro; não são uma medição de FPS da janela.

| Ação | 0.5.2 | 0.6.0 | Velocidade relativa | Redução de tempo |
|---|---:|---:|---:|---:|
| Deslocar a vista | 1,180 s | 0,032 s | 36,6× | 97,3% |
| Sequência de zoom | 2,101 s | 0,905 s | 2,32× | 56,9% |
| Trocar cor e apresentar o quadro | 3,473 s | 0,794 s | 4,37× | 77,1% |

Não há um percentual universal para todo o módulo. Para retomar a referência
da análise anterior, foi calculado um ciclo de uma abertura, 20 quadros de
deslocamento, dez de zoom e cinco trocas de cor. Mantendo a mesma abertura
de 53,61 s para as duas versões, o ciclo passa de **115,59 para 67,27 s**:
**71,8% mais velocidade**, ou **41,8% menos tempo**. É um ciclo calculado a
partir das ações medidas, não uma sessão interativa medida de ponta a ponta.

A abertura observada passou de 53,61 para 46,83 s, mas parser e composição
geométrica não foram otimizados nesta etapa. Essa diferença inclui variação
de execução e não foi creditada como ganho de abertura no ciclo acima.
A montagem inicial da cena foi praticamente igual: 2,61 e 2,62 s.

A memória residente do processo após apresentar a cena foi de **858 para
709 MiB**, aproximadamente **17,4% menor neste ensaio**. São fotografias do
processo, sujeitas ao alocador e ao Windows; não representam um limite de RAM
nem um percentual garantido para todos os projetos. O modelo ainda mantém
geometrias e um item de seleção por objeto. O cache gráfico é administrado
pelo limite compartilhado do Qt.

Uma segunda comparação usou a serigrafia `srlc`, com **11.607 objetos**:
deslocamento de 0,146 para 0,009 s (**16,1×**), troca de cor de 0,358 para
0,146 s (**2,46×**). O zoom ficou próximo, de 0,153 para 0,161 s, sem ganho
nesse arquivo. Com a mesma abertura de 9,26 s para as duas versões, o ciclo
calculado passou de 15,49 para 11,78 s: **31,5% mais velocidade**. A memória
residente após apresentar a cena foi de 232 para 214 MiB, **7,8% menor**.
Esses resultados reforçam que arquivo, operação e uso de transparência
determinam o ganho, e que os percentuais não devem ser somados.

## Conferência e reprodução

As imagens das duas versões ficaram **idênticas pixel a pixel** nos quatro
casos comparados: vista inicial, troca de cor, destaque selecionado e objetos
negativos em fantasma. O desenho com cache também coincidiu com a pintura
direta na vista final. Os Gerbers de entrada permaneceram idênticos em bytes.

Foram aprovados **134 testes**, incluindo regressões de clique, janela de
seleção, snap, arraste, undo/redo, edição, exportação e reabertura, além dos
recursos anteriores do 3D. Os oito novos testes cobrem a sincronização
incremental e a equivalência visual em diferentes escalas e transparências.
O Ruff não encontrou problemas em `gerber_editor`, `tests` ou `scripts`.

A janela **Windows nativa** também foi exercitada com a `srlc`: importação
assíncrona, clique de seleção, cor, opacidade, visibilidade, desfazer, excluir,
exportar e reabrir, com restauração da geometria original ao final. O timer
da GUI recebeu 163 pulsações durante o carregamento e não houve erros.
O [relatório nativo](output/v06/native/report.json) e as capturas estão em
`output/v06/native`; as preferências reais do usuário não foram usadas.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check gerber_editor tests scripts
.\.venv\Scripts\python.exe -m scripts.benchmark_2d "C:\Temp\Gerbers\PCB Teste\olc" --implementation output/v06/baseline_052 --output output/v06/baseline_olc
.\.venv\Scripts\python.exe -m scripts.benchmark_2d "C:\Temp\Gerbers\PCB Teste\olc" --output output/v06/optimized_olc
.\.venv\Scripts\python.exe -m scripts.summarize_benchmark_2d output/v06/baseline_olc output/v06/optimized_olc --output output/v06/performance_olc.json
.\.venv\Scripts\python.exe -m scripts.verify_v06 --file "C:\Temp\Gerbers\PCB Teste\srlc"
```

Relatórios locais: [comparação de desempenho](output/v06/performance_olc.json),
[execução otimizada](output/v06/optimized_olc/report.json) e
[comparação na serigrafia](output/v06/performance_srlc.json), além da
[integridade da referência](output/v06/archive_integrity.json).
As imagens e os diagnósticos ficam em `output/v06`, excluída dos ZIPs de fonte.

## Limites e próxima etapa

Carregar um arquivo grande pela primeira vez ainda exige gerar geometrias e
compor a camada inteira. Uma edição geométrica também recompõe a camada
afetada, embora conserve seus itens não alterados e as demais camadas.
Zoom precisa regenerar o cache e continua mais caro que deslocamento.
Transparência não recebe o ganho de deslocamento do cache de dispositivo.

A próxima melhoria estrutural é compor e invalidar regiões espaciais,
seguida de uma representação mais compacta de seleção e de um cache
persistente para reabrir arquivos inalterados. Compilar o Python por si só
não elimina as uniões geométricas do GEOS nem o custo de desenhar os paths Qt.

O backup anterior [0.5.2 datado](Backup/Editor_Gerber_v0.5.2_2026-11-13.zip)
foi preservado e teve seu SHA-256 conferido. A versão otimizada é entregue em
[Editor_Gerber_v0.6.0.zip](Backup/Editor_Gerber_v0.6.0.zip).
