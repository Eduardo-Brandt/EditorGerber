# Editor Gerber 0.10.0 — imagens agrupadas, agrupamento e ajuda HTML

Entrega de 14/11/2026. O backup anterior permanece em
`Backup/Editor_Gerber_v0.9.1.zip`. A splash continua configurada em oito segundos.

## Imagens no cursor e agrupamento da sessão

A importação conserva o posicionamento interativo da 0.9.1: depois de confirmar
o diálogo, a imagem segue o mouse até clicar no local desejado, com o centro
como referência. Esc ou botão direito cancela sem inserir objetos.

As regiões da imagem agora recebem um grupo automático. Clicar em qualquer
parte seleciona o conjunto para mover, copiar ou excluir como unidade. A imagem
continua sendo inserida em uma única operação de histórico.

O menu Editar oferece:

- **Agrupar objetos — Ctrl+G:** agrupa a seleção de dois ou mais objetos da
  mesma camada. Se a seleção já é um grupo único, a ação fica desabilitada.
- **Desagrupar objetos — Ctrl+Shift+G:** libera os componentes dos grupos
  selecionados. Clicar em um componente depois de desagrupar seleciona apenas ele.
- **Ctrl+Z/Ctrl+Y:** desfaz/refaz o agrupamento, o desagrupamento e as edições.

A janela de seleção da esquerda para a direita exige que o grupo inteiro caiba
na janela. A janela de cruzamento seleciona todo o grupo quando toca uma parte.
Ctrl+clique adiciona/remove o grupo da seleção. O painel Propriedades informa
quando a seleção corresponde a um grupo.

Colar, duplicar, espelhar e criar matrizes preservam a estrutura do grupo, com
novos identificadores para cada cópia. Textos vetoriais mantêm seu diálogo de
edição mesmo quando também pertencem a um grupo de seleção.

Os grupos são planos: agrupar uma seleção que contenha grupos forma um grupo
único; desagrupar libera os componentes, e desfazer restaura as associações
anteriores. A organização vale durante a sessão. Salvar conserva os grupos
na sessão aberta; reabrir o arquivo Gerber traz somente a geometria.

## Preservação de dados e desempenho

O identificador de grupo é metadado da sessão, excluído da comparação de dados
de fabricação. O agrupamento não reordena objetos, não muda polaridades,
coordenadas ou apertures e não adiciona atributos de grupo ao Gerber.

As alterações de grupo possuem revisão própria para atualizar a seleção sem
recompor os caminhos 2D ou invalidar a PCB 3D. A seleção usa um índice de
membros por camada e atualiza a interface em lote. Um teste com mil membros
confirma uma única atualização de seleção, evitando trabalho repetido por região.

## Ajuda HTML

**Ajuda → Como usar** abre uma janela de consulta com HTML local. Ela contém
índice navegável, busca com Ctrl+F/Enter e botões Anterior/Próximo, além de um
atalho para voltar ao índice. Não exige acesso à internet e pode permanecer
aberta enquanto o usuário trabalha no editor.

O guia cobre arquivos e salvamento, funções das camadas, navegação e seleção,
grupos, mover/copiar/editar, importação de imagens, desenho/texto/cotas,
fiduciais e recortes, 3D/exportação, preferências e atalhos. A tabela de atalhos
é gerada a partir das configurações atuais. Na janela 3D, Como usar abre o tópico
de 3D no mesmo guia.

Português e inglês acompanham o idioma da interface. Os arquivos de conteúdo
estão em `gerber_editor/assets/help_pt_BR.html` e `help_en.html`; os tokens
`{{edit.group}}`, `{{version}}` e semelhantes são preenchidos pelo programa.
Os HTMLs também foram incluídos nos dados de empacotamento do projeto.

## Verificação

**202 testes passaram em 86,07 s.** Ruff e a conferência de formatação dos
135 arquivos Python passaram. Os testes novos verificam seleção por grupo,
movimento/exclusão da imagem inteira, cancelamento, undo/redo, grupos
independentes em cópias/matrizes, seleção por janela, membros ocultos, textos
editáveis, byte a byte dos Gerbers, caches 2D/3D, validação do clipboard,
tópicos/atalhos HTML, busca, tradução e acesso à ajuda a partir do 3D.

O ensaio nativo Windows confirmou os atalhos Ctrl+G/Ctrl+Shift+G, seleção da
imagem inteira, seleção individual após desagrupar, cópias independentes,
undo/redo e preservação da saída Gerber. A ajuda foi conferida visualmente
em português/inglês e no tópico 3D.

[Relatório nativo](output/v010/native/report.json) ·
[Imagem agrupada](output/v010/native/01_select_whole_image.png) ·
[Parte desagrupada](output/v010/native/02_select_ungrouped_part.png) ·
[Índice da ajuda](output/v010/native/03_html_help_index.png) ·
[Ajuda de agrupamento](output/v010/native/04_html_help_groups.png) ·
[Ajuda de 3D](output/v010/native/06_html_help_3d.png).

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check gerber_editor tests scripts
.\.venv\Scripts\python.exe -m ruff format --check gerber_editor tests scripts
.\.venv\Scripts\python.exe -m scripts.verify_v010
```

[Backup final 0.10.0](Backup/Editor_Gerber_v0.10.0.zip). Salve o trabalho e
reinicie pelo **Iniciar.bat** para carregar esta versão.
