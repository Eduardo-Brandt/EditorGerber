# Editor Gerber 0.9.1 — imagem importada seguindo o mouse

Revisão de 13/11/2026. A versão anterior permanece preservada em
`Backup/Editor_Gerber_v0.9.0.zip`.

## Posicionamento interativo

**Importar gráfico P&B** abre com **Posicionar pelo mouse** marcado. Depois
de ajustar largura, resolução, limiar e inversão e confirmar o diálogo, a
geometria convertida fica em prévia seguindo o cursor no editor 2D.

- O clique esquerdo fixa o **centro da imagem** no ponto indicado, respeitando
  as opções de snap e a resolução de coordenadas da camada.
- **Esc** ou botão direito descarta a prévia. A camada e o histórico são
  alterados somente ao confirmar o posicionamento.
- A importação é uma única operação **Importar gráfico**, com Ctrl+Z/Ctrl+Y.
- Para inserir por coordenadas, desmarque **Posicionar pelo mouse** e informe
  X/Y do canto inferior esquerdo. Os campos ficam desabilitados no modo mouse.

O ponto central considera toda a imagem, incluindo margens brancas. A largura,
a proporção, a orientação vertical e a polaridade Dark/Clear são conservadas.
O fluxo utiliza a mesma prévia de posicionamento já usada para mover e colar
objetos. O arquivo de imagem de origem permanece intacto.

## Verificação

**186 testes passaram em 82,28 s.** Ruff e a conferência de formatação dos
132 arquivos Python passaram. Os seis casos novos cobrem prévia em movimento,
posição central no clique, tamanho e exportação/reabertura Gerber, undo/redo,
cancelamento por Esc e botão direito, coordenadas manuais, margens/orientação,
polaridade Clear e imagem sem pixels pretos.

O ensaio Windows nativo usou os widgets reais: a prévia foi conferida em
(14,20) e (28,10) mm, e a imagem foi fixada com centro em (28,10) mm. A
conferência também cobriu cancelamento, undo/redo e gravação Gerber normalizada.

[Relatório nativo](output/v091/native/report.json) ·
[Diálogo](output/v091/native/01_import_dialog.png) ·
[Prévia no primeiro ponto](output/v091/native/02_following_mouse.png) ·
[Prévia no segundo ponto](output/v091/native/03_following_mouse.png) ·
[Imagem posicionada](output/v091/native/04_placed_at_click.png).

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check gerber_editor tests scripts
.\.venv\Scripts\python.exe -m ruff format --check gerber_editor tests scripts
.\.venv\Scripts\python.exe -m scripts.verify_v091
```

[Backup 0.9.1](Backup/Editor_Gerber_v0.9.1.zip). Salve o trabalho aberto e
reinicie pelo **Iniciar.bat** para carregar o novo comportamento.
