# Instalação e distribuição do Editor Gerber

Os pacotes incluem Python, Qt, as bibliotecas geométricas e o backend STEP.
Não é necessário instalar Python nem executar pip para usar o programa.

## Abrir

### Instaladores

- **Windows 10/11 x64:** execute `EditorGerber-v0.14.0-setup-windows-x64.exe`.
  O assistente instala para o usuário atual em `%LOCALAPPDATA%\Programs\EditorGerber`,
  cria uma entrada no menu Iniciar e oferece um atalho na área de trabalho.
  Remova pelo menu de aplicativos instalados do Windows.
- **Ubuntu 22.04+ / Debian 12+ x64:** instale o `.deb` pela loja de aplicativos
  ou execute `sudo apt install ./EditorGerber-v0.14.0-setup-linux-x64.deb`.
  Abra pelo menu ou pelo comando `editorgerber`. O aplicativo fica em
  `/opt/editorgerber`; remova com `sudo apt remove editorgerber`.
  Outras distribuições Linux podem usar o pacote portátil com glibc 2.35+.
- **macOS 14+:** abra o `.pkg` correspondente ao processador e siga o assistente.
  Ele instala `EditorGerber.app` em `/Applications` (Aplicativos).
  Para remover, mova o aplicativo para a Lixeira pelo Finder.

### Portáteis

- **Windows x64:** extraia o ZIP inteiro e abra `EditorGerber.exe`. Mantenha
  a pasta `_internal` junto ao executável.
- **Linux x64:** extraia o `.tar.gz` e execute `./EditorGerber` dentro da pasta.
  Requer ambiente gráfico com OpenGL 3.3 e glibc 2.35 ou superior, como Ubuntu
  22.04 ou mais recente. Não é um pacote para Alpine/musl.
- **macOS 14 ou superior:** extraia o ZIP e abra `EditorGerber.app`. Escolha
  arm64 para Apple Silicon (M1 ou posterior) e x64 para Intel.

O pacote macOS usa assinatura ad hoc, sem notarização Apple. Na primeira
abertura de um download, o sistema pode exigir autorização em Privacidade e
Segurança. A edição Windows também não tem certificado Authenticode.

“Portátil” significa executar sem instalador. As preferências e os logs ficam
no perfil do usuário, conforme os diretórios padrão de cada sistema. Os
Gerbers são abertos e salvos nos locais escolhidos pelo usuário.

## Compilar

Use Python 3.13 no próprio sistema de destino. O PyInstaller não compila
binários Linux ou macOS a partir do Windows.

```text
python -m pip install -r requirements-build.txt
python -m scripts.build_portable
python -m scripts.build_installer
```

O resultado fica em `dist/`, com executável, arquivo compactado, código-fonte
correspondente e SHA-256. Antes de compactar, o programa compilado verifica
seus próprios recursos, abertura/salvamento Gerber, ajuda em dois idiomas,
QR Code, furação 3D e exportações WRL/STEP. O relatório é `VERIFICATION.json`.
Os arquivos de licença de terceiros acompanham o pacote.

O instalador utiliza o resultado portátil já verificado da mesma versão.
No Windows, a compilação exige Inno Setup 6. No Linux, exige `dpkg-deb` e
`desktop-file-validate` (pacote `desktop-file-utils`). No macOS, usa `pkgbuild`
e `codesign`. A instalação é verificada automaticamente em runners descartáveis
do GitHub, incluindo uma segunda execução do aplicativo instalado. Os testes
de Windows/Linux também conferem a desinstalação. A instalação de teste não
é executada no perfil do computador de desenvolvimento.

No Linux, instale também as bibliotecas gráficas indicadas no workflow
`.github/workflows/portable.yml`. Para compilar sem monitor:

```text
xvfb-run -a python -m scripts.build_portable
```

## GitHub Releases

O workflow compila Windows, Linux, macOS Intel e macOS Apple Silicon nos
respectivos runners. Ao enviar uma tag igual à versão, por exemplo
`v0.14.0`, ele verifica os quatro conjuntos de pacotes e publica em Releases.
Se algum build falhar, a publicação aguarda a correção.

```text
git tag v0.14.0
git push origin v0.14.0
```

Também é possível iniciar pelo botão **Run workflow** em Actions. Marque
**Publish this version after all package checks pass** para criar a tag e
publicar a Release após todas as verificações. Sem essa opção, os pacotes
ficam apenas como artefatos do workflow. Tags e Releases existentes são
preservadas; a rotina não substitui uma versão pública.

Se os quatro builds passaram e somente a publicação falhou, use o workflow
**Publish verified portable packages**, informando a tag e o ID da execução
de compilação. Ele confere a origem, os quatro resultados e os SHA-256 antes
de publicar os mesmos arquivos, sem recompilar. Releases públicas existentes
são preservadas.

Os arquivos maiores ficam anexados à Release; não são enviados como arquivos
normais do repositório. `dist/`, `build/`, `.venv/`, resultados de ensaio e
backups estão excluídos do Git. As notas pessoais `Descricao projeto` também
permanecem locais.

O site pode apontar para a página `releases/latest` do repositório público,
onde cada visitante escolhe seu sistema. Links de uma versão específica usam
`releases/download/vVERSAO/NOME-DO-ARQUIVO`.

Página de downloads deste projeto:
https://github.com/Eduardo-Brandt/EditorGerber/releases/latest
