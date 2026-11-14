# Editor Gerber 0.13.2 — distribuição portátil

Preparação de 14/11/2026. O backup estável anterior permanece em
`Backup/Editor_Gerber_v0.12.2.zip`, SHA-256
`09512f3747a0da2fcce25b2cfdebacd369b6f1c45a4c86901a9d79578cd18b42`.

## Pacote Windows verificado

Foi gerado `EditorGerber-v0.13.2-windows-x64.zip`.
O ZIP contém o executável, bibliotecas nativas, recursos, licenças de
terceiros e relatório de verificação. Após extrair a pasta inteira,
`EditorGerber.exe` abre sem instalar Python. A pasta `_internal` acompanha
o executável.

O programa compilado passou na verificação de abertura/salvamento Gerber,
recursos gráficos, ajuda nos dois idiomas, QR Code, furação 3D e exportação
WRL/STEP. O relatório `VERIFICATION.json` registra `frozen: true` e
`success: true`. Uma segunda execução pela interface normal, em diretório
separado e sem PYTHONPATH/PYTHONHOME, abriu a demonstração e encerrou com
código zero. O ZIP foi conferido e recebeu arquivo SHA-256.

## Linux e macOS

O workflow `.github/workflows/portable.yml` gerou quatro builds nativos:
Windows x64, Linux x64, macOS Intel e macOS Apple Silicon. As dependências
de compilação e execução estão fixadas em `requirements-build.txt`.

O Linux usa Ubuntu 22.04, e os pacotes macOS exigem macOS 14 ou superior.
O macOS tem assinatura ad hoc, sem notarização Apple; o Windows não possui
certificado Authenticode. `DISTRIBUICAO.md` explica abertura, requisitos,
localização das preferências e compilação.

Os quatro executáveis compilados passaram na verificação nativa da tag
`v0.13.2`, incluindo abertura/salvamento Gerber, recursos gráficos, ajuda
nos dois idiomas, QR Code, furação 3D e exportações WRL/STEP. A execução
também conferiu a centralização da indicação de processamento em dois
tamanhos de janela. O relatório `VERIFICATION.json` acompanha cada pacote.

Resultado da compilação:
https://github.com/Eduardo-Brandt/EditorGerber/actions/runs/43644562154

## Publicação

As tags `vVERSAO`, iguais à versão do código, iniciam os builds. A publicação
em Releases ocorre depois de os quatro executáveis passarem na verificação.
São anexados os pacotes, os SHA-256 e o código-fonte correspondente. Uma
release já publicada é preservada; a rotina só completa releases em rascunho.

O código foi enviado ao repositório público solicitado:
https://github.com/Eduardo-Brandt/EditorGerber

Página de downloads para o site:
https://github.com/Eduardo-Brandt/EditorGerber/releases/latest

Executáveis, ambientes virtuais, backups, resultados de ensaios e notas
pessoais ficam fora do Git. Os binários são anexos da Release. Para futuras
versões, atualize a versão do projeto e envie a tag correspondente, conforme
`DISTRIBUICAO.md`.

## Validação e ajuste de layout

Passaram **261 testes em 110,00 segundos**. Durante a verificação completa,
foi corrigida a posição da indicação de processamento ao redimensionar uma
janela cuja barra de ferramentas muda de layout. A indicação agora acompanha
também movimentos e alterações da área central. Ruff também passou.

O backup final desta entrega é `Backup/Editor_Gerber_v0.13.2.zip`. Os backups
0.13.0, 0.12.2 e os demais anteriores permanecem preservados.
