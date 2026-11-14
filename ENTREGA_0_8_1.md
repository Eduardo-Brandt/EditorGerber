# Editor Gerber 0.8.1 — splash, detalhe 3D, camada ativa e ícone

Revisão de 13/11/2026. A versão anterior permanece em
`Backup/Editor_Gerber_v0.8.0.zip`.

## Splash por quatro segundos

A janela principal fica oculta até completar o tempo mínimo da splash.
Isso impede que a maximização do editor encubra a apresentação no Windows.
O temporizador confere novamente o relógio antes de mostrar o editor;
o convite de apoio também verifica o prazo antes de ocultar a splash.
`--no-splash` continua abrindo diretamente, e a apresentação pelo menu Ajuda
continua dispensável. Arquivos da linha de comando só abrem após a apresentação.

O ensaio com o ponto de entrada real, em Windows, mediu **4,002 s** até
mostrar o editor e **4,030 s** até ocultar a splash. Aos 3,494 s, a splash
estava visível e o editor permanecia oculto.
[Relatório](output/v081/startup/report.json) ·
[Splash](output/v081/startup/01_splash.png).

## Detalhe 3D sem recompor todos os Gerbers

O cálculo foi dividido em preparação da geometria e geração de malha.
Contorno, recortes, furação e composição das camadas ficam preparados uma vez
por revisão da PCB. Um detalhe novo reutiliza esses dados e recalcula a malha
na tolerância escolhida. A interface informa “Atualizando visualização 3D…”.

Voltar a um detalhe já calculado reutiliza a malha pronta. O cache conserva
até três combinações de espessura/detalhe, limitado a 128 MiB de vértices.
Editar a PCB ou usar **Atualizar PCB** invalida os dados. Câmera, zoom,
deslocamento e materiais ocultos são conservados. Resultados de configurações
antigas não substituem o detalhe atual quando há trocas durante um cálculo.
A exportação fica indisponível até a configuração atual estar pronta.

O ensaio nativo Windows/OpenGL confirmou a reutilização das geometrias e a
igualdade exata do framebuffer ao voltar ao detalhe Normal em cache. A placa
de demonstração gerou 1.538 triângulos em Fino, 1.123 em Normal e 771 em Rápido.
[Relatório](output/v081/native3d/report.json) ·
[Normal em cache](output/v081/native3d/normal_cached.png).

## Camada selecionada à frente

Clicar em uma camada no gestor traz seu desenho e sua prioridade de seleção
para a frente das camadas inativas. Ao escolher outra, a anterior retorna à
posição definida pela pilha. As setas continuam controlando a ordem das camadas
inativas, com desfazer/refazer. A seleção não reorganiza a lista, não recompõe
a geometria e não altera dados dos Gerbers.

## Ícone central ampliado

A ferramenta integrada `image_gen`, pela skill `imagegen`, usou o exemplo
anexado e o ícone anterior para gerar o enquadramento central. Pads e trilhas
ocupam o quadro, e a placa ciano inferior deixa de aparecer. O PNG gerado foi
preservado; o ICO foi convertido para os tamanhos pequenos do Windows.

[PNG](gerber_editor/assets/app_icon.png) · [ICO](gerber_editor/assets/app_icon.ico) ·
[Prompt final](gerber_editor/assets/ICON_PROMPT.md) ·
[Prévia 16–128 px](output/v081/startup/03_icon_sizes.png).

## Verificação

**165 testes passaram em 80,70 s.** Ruff e a conferência de formatação dos
126 arquivos Python passaram. Os ensaios nativos de inicialização e OpenGL
também passaram. O código final está em
[Backup/Editor_Gerber_v0.8.1.zip](Backup/Editor_Gerber_v0.8.1.zip).

Os testes de regressão cobrem a reutilização de geometrias, o cache de malhas,
mudanças de espessura, edição da PCB, atualização forçada, trocas de detalhe
com um worker em execução, conservação de furos e prioridade visual/seleção
de camadas sobrepostas. A suíte existente verifica também exportação e reabertura
de STEP, WRL, undo/redo, leitura e preservação dos arquivos.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check gerber_editor tests scripts
.\.venv\Scripts\python.exe -m ruff format --check gerber_editor tests scripts
.\.venv\Scripts\python.exe -m scripts.verify_v081_startup
.\.venv\Scripts\python.exe -m scripts.verify_v081_3d
```

Salve o trabalho aberto e reinicie pelo **Iniciar.bat** para carregar as mudanças
e o novo ícone.
