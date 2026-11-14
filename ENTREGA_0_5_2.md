# Editor Gerber 0.5.2 — 12/11/2026

| Pedido | Implementação |
|---|---|
| 1 | Splash de inicialização visível por no mínimo quatro segundos. Clique fora, Esc e fechar não a encerram antes disso. |
| 2 | Preferências → Mostrar todas as ferramentas à esquerda. A paleta usa mais colunas quando falta altura, mantendo os botões disponíveis. Opção ativada inicialmente e persistida. |
| 3 | Menus Visualizar, Preferências e Ajuda no 3D. Ajuda tem Como usar, Sobre, Tela de apresentação e Suporte / doar ao criador. |
| 4 | Abrir/Salvar como/Salvar conservam a última pasta de arquivos. JPG/STEP/WRL compartilham uma última pasta de exportação própria. Ambas persistem após reiniciar. |
| 5 | Links da interface centralizados em https://brandttecnologia.com.br/EditorGerber. |
| 6 | Convite clicável ao apoio no Sobre e na splash, abrindo os dados de doação. Na inicialização, um clique aguarda o tempo mínimo da splash antes de abrir a tela. |
| 7 | fp-info-cache é identificado como auxiliar e ignorado com aviso discreto. Gerbers inválidos continuam recebendo diagnóstico. |
| 8 | Iniciar.bat na raiz, pronto para duplo clique; também aceita caminhos como argumentos. |
| 9 | Entrada bloqueada durante processamento; preparação sequencial e montagem da cena uma única vez ao terminar o lote. Erros do lote são apresentados juntos ao final. |

## Executar

Clique em [Iniciar.bat](Iniciar.bat), ou use o terminal do VS Code:

```powershell
.\.venv\Scripts\python.exe -m gerber_editor
```

## Sobre o fp-info-cache

O arquivo é um cache de bibliotecas de footprints do KiCad, separado dos
arquivos Gerber de fabricação. Isso consta na [documentação oficial do KiCad](https://docs.kicad.org/10.0/en/kicad/kicad.html#_board_editor_files_and_folders).
O arquivo de três bytes dessa pasta não contém comandos Gerber; a mensagem
anterior vinha da tentativa de interpretá-lo como desenho. Ele não precisa ser
corrigido para visualizar a PCB, nem é alterado pelo editor.

O nome sozinho não elimina um arquivo: se um arquivo chamado fp-info-cache
contiver cabeçalhos Gerber válidos, ele continua sendo interpretado.

## Processamento e estabilidade

Cliques, teclas, atalhos, arrastes e pedidos de fechamento ficam bloqueados
enquanto qualquer janela do processo estiver trabalhando. O bloqueio termina
quando a última operação acaba. Ferramentas esperando um clique não bloqueiam.
Diálogos modais de erro/confirmação continuam utilizáveis.

O bloqueio evita ações concorrentes, mas não garante ausência de qualquer
travamento. A correção da fila também elimina a possibilidade de receber outro
resultado de importação dentro da aplicação do anterior. A cena é reconstruída
uma única vez ao final, e Desfazer/Refazer trata o lote como uma ação.
A pintura da ampulheta durante lotes de itens da GUI não processa novos eventos
do documento nem repinta a PCB sob a área opaca da animação.

## Evidências

**126 testes passaram.** No Windows/OpenGL nativo, a splash ficou aberta por
4,003 s e a paleta manteve todos os botões visíveis em 950 × 500. O teste
selecionou os 12 arquivos da pasta: 11 Gerbers abertos, 243.347 objetos e um
cache auxiliar ignorado, sem erro. O lote levou 135,821 s neste ambiente;
os hashes de todos os originais permaneceram idênticos antes/depois.
Exportações WRL/JPG e os novos menus do 3D também foram exercitados.

- [Splashscreen](output/v052/01_splash.png)
- [Paleta em 950 × 500](output/v052/03_palette_small.png)
- [Menus do 3D](output/v052/04_3d_menus.png)
- [Sobre com convite e URL](output/v052/05_about.png)
- [Suporte com novo endereço](output/v052/06_support.png)
- [Processamento do lote](output/v052/07_batch_processing.png)
- [Lote aberto](output/v052/08_batch_complete.png)
- [Relatório nativo](output/v052/native_report.json)

Comando da verificação nativa, que apenas lê os originais:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_v052 --folder "C:\Temp\Gerbers\PCB Teste"
```

## Backup

[ZIP da versão 0.5.2](Backup/Editor_Gerber_v0.5.2.zip).
O [ZIP da versão 0.5.1](Backup/Editor_Gerber_v0.5.1.zip) e os anteriores são
preservados. A pasta Backup continua excluída do Git e dos próprios ZIPs.
