# Editor Gerber 0.4.0 — edição e visualizador 3D

| Pedido | Implementação |
|---|---|
| Nome e apresentação | **Editor Gerber** em título, Sobre, splashscreen, ajuda e cabeçalho das novas exportações. Ajuda → Tela de apresentação reabre a splashscreen. Configurações antigas continuam legíveis. |
| Ortho com Shift | Passos de 45° ou 90° em Ferramentas → Ortho com Shift, para construções, régua e posicionamento. O sentido dos arcos tem opção própria. |
| Snap a pontos | Atração por distância visual a extremidades, vértices, centros e pontos de inserção; marcador verde. Objetos em movimento não atraem a si próprios. Independente da grade. |
| Manipulação pelo cursor | Ctrl+C/X/V, M e Ctrl+D; prévia antes do clique, Esc cancela; clicar e arrastar também move. Espelhamento X/Y/ambos e matriz retangular/polar, com centro por clique e orientação opcional. |
| Propriedades editáveis | Botão na aba e duplo clique na tabela. Linhas: início/fim, espessura, comprimento a partir do início e direção; arcos/círculos: centro, raio, ângulo inicial, abertura e sentido; flashes: posição e dimensões básicas. Textos da sessão: conteúdo, fonte, altura, rotação e estilo. |
| 3D inicial | Alt+3, menu e cubo na barra. Substrato, cobre, máscara, serigrafia e pasta, recortes de Edge.Cuts, órbita/pan/zoom, vistas padrão, perspectiva/ortográfica, espessura, detalhe e materiais. |

## Edição pelo cursor

- **M:** selecione, acione M, leve a prévia ao destino e clique.
- **Arrastar:** clique no objeto/seleção e arraste com o botão esquerdo. Soltar aplica.
- **Ctrl+C:** captura a seleção, com referência no ponto atual do cursor.
- **Ctrl+V:** leva uma cópia ao cursor; clique confirma. Cola entre janelas
  do Editor Gerber; o destino é a camada ativa.
- **Ctrl+X:** copia e remove; Ctrl+Z restaura o recorte.
- **Ctrl+D:** duplica e inicia posicionamento.
- **Cópia espelhada:** escolhe os eixos e posiciona a prévia.
- **Matriz:** quantidades incluem o original; passo negativo inverte avanço.
  Em 360° não há repetição da posição inicial. A matriz tem Undo/Redo único.
- **Editar propriedades:** mantém histórico. Alterar a espessura de um objeto
  cria uma aperture própria, sem afetar seus vizinhos.

A ordem dark/clear é conservada. D-codes conflitantes são realocados e novas
coordenadas respeitam a resolução da camada. Inserções são validadas antes de
entrar no histórico; exportações são reabertas e comparadas antes de gravar.
Rotações oblíquas de linhas com aperture retangular geram regiões equivalentes.
Draws oblíquos com aperture oval e arcos com aperture não circular que exigiriam
draw de macro continuam sujeitos à rejeição explícita desse recurso.

## Texto na sessão

Traços da fonte PCB são selecionados como grupo. Fontes instaladas mantêm seus
parâmetros. Mover, copiar, espelhar e criar matrizes conservam essa associação;
cópias recebem grupos independentes. Salvar mantém o texto editável em memória.

O Gerber contém apenas geometria fabricável. Ao fechar/reabrir, o programa não
reconstrói fonte e texto a partir de traços. Persistência tipográfica em projeto
próprio continua prevista para `.gproj`.

## Prévia 3D

Edge.Cuts fechado fornece contorno e recortes. Sem contorno válido, a janela
identifica a estimativa pelos limites. As alturas seguem a função da camada,
independentemente da ordem da lista 2D. A máscara cobre o que não é abertura.

Espessura inicial de 1,6 mm, ajustável. Fino/Normal/Rápido afeta somente a malha.
A janela tem lista de materiais e **Atualizar PCB**. Não grava nos Gerbers.
Componentes STEP, Excellon, metalização de furos e stackup completo são futuros.

## Capturas e validação

- [Editor 2D](output/v04/01_editor.png)
- [Aba de propriedades](output/v04/02_properties.png)
- [Parâmetros geométricos](output/v04/06_geometry_properties.png)
- [Texto editável](output/v04/07_editable_text.png)
- [Matriz](output/v04/08_array.png)
- [Janela 3D renderizada no Windows](output/v04/04_native_3d_window.png)
- [Vista inferior](output/v04/05_native_3d_bottom.png)
- [Splashscreen atual](output/v04/09_splashscreen.png)

Testes, comparação independente e limites: [VALIDATION.md](VALIDATION.md).
Execute **Iniciar.ps1** para usar a versão atual; janelas já abertas continuam
com o código carregado da versão anterior.
