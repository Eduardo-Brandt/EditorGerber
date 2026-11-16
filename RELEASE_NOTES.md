Editor Gerber 0.14.0: instaladores nativos e abertura por Drag & Drop.

- Windows x64: instalador `setup-windows-x64.exe`, com menu Iniciar,
  atalho opcional na área de trabalho e desinstalador. Instala para o usuário atual.
- Ubuntu 22.04+ / Debian 12+ x64: pacote `setup-linux-x64.deb`, com comando
  `editorgerber` e entrada no menu de aplicativos.
- macOS 14+ Intel e Apple Silicon: pacotes `.pkg` separados, que instalam
  `EditorGerber.app` em Aplicativos.
- As versões portáteis continuam disponíveis. Todos os pacotes incluem Python,
  Qt e exportação STEP; não é necessário instalar Python separadamente.

Os instaladores são testados nos respectivos sistemas: instalação, execução
do aplicativo compilado e, em Windows/Linux, desinstalação. A execução verifica
Gerber, Drag & Drop, ajuda, QR Code, furação 3D e exportações WRL/STEP.

Arraste um ou vários arquivos do explorador para a janela do editor,
incluindo a área de desenho e o gestor de camadas. Os arquivos são adicionados
às camadas abertas, com progresso no rodapé. Gerbers sem extensão também
são aceitos. A ajuda local foi atualizada nos dois idiomas.

- Editor 2D de Gerber e Excellon, agrupamento e edição múltipla.
- Formas preenchidas, cópias retangulares/polares e posicionamento pelo canto no cursor.
- Visualizador de PCB 3D, progresso e exportação JPG, WRL e STEP.
- Ajuda local em português e inglês.

Baixe o pacote do seu sistema e extraia-o por inteiro. No Windows, abra
`EditorGerber.exe`; no Linux, execute `EditorGerber`; no macOS, abra
`EditorGerber.app`.

Sistemas: Windows 10/11 x64; Linux x64 com glibc 2.35+ e ambiente gráfico;
macOS 14+ em Intel ou Apple Silicon. Os pacotes ainda não possuem certificado
de distribuição Windows ou notarização Apple. Veja `DISTRIBUICAO.md` para
detalhes e localização das preferências.

Os anexos incluem SHA-256 e o código-fonte correspondente. Software livre
GPL-3.0-only. Copyright 2026 Eduardo Guilherme Brandt.
