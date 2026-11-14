# Editor Gerber 0.5.1 — 12/11/2026

## Iniciar pelo VS Code

Abra **Terminal → Novo terminal**, confirme que está na pasta do projeto e rode:

```powershell
.\.venv\Scripts\python.exe -m gerber_editor
```

Para carregar seu arquivo diretamente:

```powershell
.\.venv\Scripts\python.exe -m gerber_editor "C:\Temp\Gerbers\PCB Teste\srlc"
```

O ambiente virtual já está instalado; esses comandos não exigem ativá-lo.
O atalho `Iniciar.ps1` continua funcionando sem abrir um console Python.

## Alterações

- **Processamento:** ampulheta vetorial girando em um cartão no centro do desenho,
  com o nome da operação, no editor e no visualizador 3D. Várias operações
  simultâneas mantêm o indicador até a última terminar. Ferramentas esperando
  o próximo clique não cobrem o desenho com esse cartão.
- **3D ao retornar:** edições marcam a PCB como pendente. A reconstrução começa
  ao ativar novamente a janela 3D, mesmo se ela já estava aberta. Várias edições
  resultam em uma única reconstrução. Sem mudanças, retornar não recalcula.
  Câmera e materiais ocultos são conservados. O botão Atualizar PCB permanece.
- **Cálculos em andamento:** um resultado de uma revisão anterior não substitui
  uma PCB que já foi editada. O estado atual é calculado na janela ativa. Se
  houver exportação em curso, a atualização aguarda sua conclusão. Fechar todas
  as camadas limpa a prévia ao retornar ao visualizador.
- **Gestor de camadas:** itens são reaproveitados durante seleção/visibilidade;
  mudanças solicitadas pela árvore são aplicadas após o evento Qt terminar.
  Alternar rapidamente uma caixa conserva o último valor solicitado.
- **Diagnóstico:** logs persistentes de Python, Qt e threads, além de um arquivo
  para falhas nativas. Funcionam também quando iniciado sem terminal.

## Investigação do fechamento

O Windows registrou APPCRASH no processo da versão anterior, módulo
`Qt6Widgets.dll` 6.12.0, exceção `0xc0000005`, deslocamento `0x351800`.
Nesse DLL, o endereço fica no intervalo iniciado pelo símbolo exportado
`QTreeWidgetItem::setData`. A versão anterior podia limpar a árvore de camadas
durante seus próprios eventos de seleção/alteração, invalidando o item em uso.
Esse caminho foi corrigido. É uma causa provável compatível com o registro;
sem uma pilha da falha original, não se afirma diagnóstico definitivo.

O erro ao tentar importar `fp-info-cache` foi tratado pelo parser e é um evento
separado: esse arquivo auxiliar do KiCad não é Gerber.

Neste projeto, os novos registros ficam em `output/logs/editor_<PID>.log` e
`output/logs/fault_<PID>.log`. O segundo normalmente fica vazio. Eles ajudam a
investigar uma eventual nova ocorrência, sem recuperar edições não salvas.

## Validação

- **114 testes passaram** na suíte completa; Ruff e formatação aprovados.
- Windows/OpenGL nativo: ampulhetas girando nos dois ambientes, cartão centrado,
  30 ciclos de seleção/visibilidade por cliques reais no gestor, sem fechamento.
- Três edições enquanto o 3D permanecia aberto e inativo não iniciaram cálculo;
  voltar à janela produziu uma reconstrução, preservando a câmera.
- `srlc`: importação assíncrona de 11.607 objetos e dez ciclos de visibilidade.
  Arquivo original lido apenas, com SHA-256 idêntico antes/depois:
  `0e13e3bc082c85a7b0d52a6ec2b3c0dba020b14483622a9addb44c370c18a9c5`.

[Relatório nativo](output/v051/native_report.json) ·
[Ampulheta no editor](output/v051/01_processing.png) ·
[Outro quadro da rotação](output/v051/02_processing_rotated.png) ·
[Ampulheta no 3D](output/v051/03_3d_processing.png) ·
[PCB após retornar](output/v051/05_after_return.png) ·
[Gerber real](output/v051/06_real_gerber.png).

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.verify_v051 --real "C:\Temp\Gerbers\PCB Teste\srlc"
```

## Backup

[Fonte da 0.5.1](Backup/Editor_Gerber_v0.5.1.zip).
Os ZIPs [0.5.0](Backup/Editor_Gerber_v0.5.0.zip) e
[0.4.0](Backup/Editor_Gerber_v0.4.0.zip) foram preservados.
Os backups continuam excluindo ambientes, logs, saídas de testes e Gerbers
externos ao projeto. As duas mudanças não alteram a geometria ao salvar Gerber.
