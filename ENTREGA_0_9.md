# Editor Gerber 0.9.0 — geração e atualização 3D mais rápidas

Entrega de 13/11/2026. A referência é o backup estável
`Backup/Editor_Gerber_v0.8.1-estavel.2026.11.13.221634.zip`, preservado.
A configuração da splash continua em **8 segundos**.

## Resultados com os Gerbers reais

O ensaio usou `olc`, `srlc` e `fur` da pasta de teste, totalizando 123.268
objetos. As duas implementações receberam os mesmos objetos e geometrias
primitivas, no mesmo processo, sem profiler. O cache geométrico do 2D foi
preparado antes das fases medidas de 3D, como ocorre no editor.

| Operação 3D | 0.8.1 estável | 0.9.0 | Ganho no ensaio |
|---|---:|---:|---:|
| Preparar a PCB | 37,24 s | 4,79 s | 7,8× |
| Gerar a malha Normal | 16,52 s | 7,79 s | 2,1× |
| Geração inicial completa | 53,76 s | 12,58 s | **4,3×** |
| Atualizar após mover um objeto da serigrafia | 46,69 s | 4,12 s | **11,3×** |

A preparação e a montagem sem alterações reaproveitaram todas as partes,
gastando juntas cerca de 4 ms no cálculo, sem incluir apresentação na GPU.
Na edição, substrato e cobre conservaram os mesmos objetos de malha.
O trabalho comum de atualizar os blocos do 2D levou 0,45 s nesse ensaio.
Os tempos variam com a placa e o computador; o conjunto foi visualizado com
contorno estimado pelos limites, pois esses três arquivos não incluem Edge.Cuts.

[Relatório completo](output/v09/performance/report.json) ·
[Ensaio reproduzível](scripts/benchmark_3d.py).

## O que mudou

- O 3D recebe snapshots GEOS da composição já pronta do 2D. As células mantêm
  a ordem dark/clear; o worker combina suas imagens sem repetir todas as
  operações dos objetos Gerber. Snapshots são usados somente quando a assinatura
  corresponde aos objetos atuais da camada.
- Preparação, contorno, recortes, furação e limites possuem cache por dependência.
  Uma edição da serigrafia conserva a geometria do cobre e a placa física.
- A malha reaproveita substrato e superfícies cujas dependências não mudaram.
  Alterar o cobre atualiza também as máscaras correspondentes; alterar furos ou
  contorno recalcula a placa e os materiais afetados. **Atualizar PCB** também
  reaproveita resultados que continuam válidos.
- Cor, opacidade, ordem das camadas no 2D, idioma e marca de arquivo salvo não
  invalidam a geometria física. Mudanças de função, visibilidade e objetos são
  verificadas antes de gerar uma nova revisão.
- As coordenadas dos triângulos são extraídas em lote com
  [get_coordinates](https://shapely.readthedocs.io/en/2.1.1/reference/shapely.get_coordinates.html),
  e as paredes são montadas com NumPy. As duas faces do substrato compartilham
  uma triangulação, com altura e normais próprias.
- Cada worker produz seu próprio cache. Um resultado de uma revisão antiga não
  publica geometria, partes ou caches sobre uma PCB mais recente.

## Geometria e visualização

A composição do cobre real apresentou diferença de área zero contra a referência;
a serigrafia, aproximadamente 5,7 × 10⁻¹³ mm². O substrato furado também apresentou
diferença de área zero. Os três arquivos foram conferidos por SHA-256 antes e
depois, sem alterações.

A tolerância Normal permanece em 0,025 mm. A junção de blocos pode inserir
vértices colineares nas bordas e mudar os pontos escolhidos pela simplificação
da visualização: a malha real passou de 378.179 para 378.260 triângulos.
Os dados de fabricação, coordenadas Decimal e exportação Gerber são preservados.
Furos continuam sendo subtraídos após simplificar o contorno.

No ensaio Windows/OpenGL com contorno, cobre, serigrafia e furos/rasgo, o
framebuffer inicial ficou **idêntico** ao da implementação estável. Uma edição
local conservou as malhas de cobre e substrato; restaurar o objeto devolveu a
mesma imagem. Trocas de detalhe, cor/opacidade, movimentação de furo e exportações
STEP/WRL também foram verificadas.

[Relatório nativo](output/v09/native/report.json) ·
[Imagem comparada à versão estável](output/v09/native/01_render_matches_stable.png) ·
[Atualização local](output/v09/native/02_incremental_silk_edit.png) ·
[Atualização da furação](output/v09/native/03_drill_edit.png).

## Verificação e uso

**180 testes passaram em 80,76 s.** Ruff e a conferência de formatação dos 130
arquivos Python passaram. A verificação nativa Windows/OpenGL, a comparação
contra a referência estável e as exportações STEP/WRL também passaram.

Os testes incluem equivalência com montagem escalar de vértices, orientação
das paredes de furos, polaridades em limites dos blocos, rejeição de snapshot
antigo, edição de cobre/máscara/serigrafia/contorno/furação, invalidação correta,
troca entre composição simples e espacial, e resultados de workers desatualizados.
O teste de temporização da splash usa uma duração própria de quatro segundos,
sem alterar a configuração de oito segundos do programa.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check gerber_editor tests scripts
.\.venv\Scripts\python.exe -m ruff format --check gerber_editor tests scripts
.\.venv\Scripts\python.exe -m scripts.verify_v09
.\.venv\Scripts\python.exe -m scripts.benchmark_3d "C:\Temp\Gerbers\PCB Teste\olc" "C:\Temp\Gerbers\PCB Teste\srlc" "C:\Temp\Gerbers\PCB Teste\fur" --baseline "Backup/Editor_Gerber_v0.8.1-estavel.2026.11.13.221634.zip" --output output/v09/performance
```

Salve o trabalho aberto e reinicie pelo **Iniciar.bat** para carregar a versão
0.9.0. [Backup final verificado](Backup/Editor_Gerber_v0.9.0.zip).
