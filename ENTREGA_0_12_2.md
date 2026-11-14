# Editor Gerber 0.12.2 — canto do conjunto no cursor

Entrega de 14/11/2026. O backup anterior permanece em
`Backup/Editor_Gerber_v0.12.1.zip`, SHA-256
`df1d5f6fb12864e05fd5d0f391647c2b3336797260ba3c9cae42c907389922d4`.

## Correção

Colar usava o ponto do mouse registrado durante a cópia como referência.
O espelhamento também reutilizava uma referência que podia ficar afastada
do limite da geometria. Isso deslocava a prévia em relação à ponta do cursor.

Colar, duplicar, recortar/colar, cópia espelhada e o comando Mover agora
calculam a referência pelo canto inferior esquerdo do conjunto a posicionar.
O limite é extraído dos caminhos efetivamente exibidos, incluindo espessuras
e imagens das apertures. Isso evita o deslocamento que limites conservadores
de macros poderiam introduzir. No espelhamento, o cálculo ocorre após a
reflexão, valendo para X, Y e X/Y.

A posição atual do mouse é consultada ao iniciar essas operações, quando
ele está sobre o canvas. A prévia e a gravação no clique compartilham a
mesma referência. O snap e a resolução de fabricação da camada continuam
sendo respeitados. Conteúdos antigos do clipboard também usam o novo canto.

Ao arrastar uma seleção diretamente, a referência explícita continua sendo
o ponto onde ela foi pega. A importação de imagens conserva a inserção pelo
centro, e cancelamento, grupos e desfazer/refazer foram preservados.

## Verificação

Passaram os **40 testes** existentes de edição interativa, grupos e imagens,
além de **13 testes novos**. Os novos casos verificam posições de cópia
afastadas, coordenadas negativas, recortar/colar, duplicar, mover, reflexões
nos três eixos, traços com espessura, macros com limites conservadores,
clipboard antigo, snap, arraste por ponto explícito, cancelamento, histórico
e atualização inicial pela posição real do mouse.

Na conferência nativa do Windows, Ctrl+C/Ctrl+V e Ctrl+D foram acionados
pelo teclado, com a cópia feita longe da seleção. A prévia manteve o canto
no cursor, e a geometria confirmada coincidiu com a posição mostrada. Também
foram conferidos espelhamento, Mover e cancelamento. Capturas e relatório
estão em `output/v0122/`. Ruff verifica código, testes e scripts.

## Backup

Backup desta entrega: `Backup/Editor_Gerber_v0.12.2.zip`, com a versão 0.12.1
preservada separadamente. Os ensaios usam apenas geometria demonstrativa.
