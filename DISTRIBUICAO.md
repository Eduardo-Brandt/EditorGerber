# Editor Gerber portátil

Os pacotes incluem Python, Qt, as bibliotecas geométricas e o backend STEP.
Não é necessário instalar Python nem executar pip para usar o programa.

## Abrir

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
```

O resultado fica em `dist/`, com executável, arquivo compactado, código-fonte
correspondente e SHA-256. Antes de compactar, o programa compilado verifica
seus próprios recursos, abertura/salvamento Gerber, ajuda em dois idiomas,
QR Code, furação 3D e exportações WRL/STEP. O relatório é `VERIFICATION.json`.
Os arquivos de licença de terceiros acompanham o pacote.

No Linux, instale também as bibliotecas gráficas indicadas no workflow
`.github/workflows/portable.yml`. Para compilar sem monitor:

```text
xvfb-run -a python -m scripts.build_portable
```

## GitHub Releases

O workflow compila Windows, Linux, macOS Intel e macOS Apple Silicon nos
respectivos runners. Ao enviar uma tag igual à versão, por exemplo
`v0.13.2`, ele verifica os quatro pacotes e publica os arquivos em Releases.
Se algum build falhar, a publicação aguarda a correção.

```text
git tag v0.13.2
git push origin v0.13.2
```

Também é possível iniciar pelo botão **Run workflow** em Actions. Nesse modo,
os pacotes ficam como artefatos do workflow, sem publicar uma release.

Os arquivos maiores ficam anexados à Release; não são enviados como arquivos
normais do repositório. `dist/`, `build/`, `.venv/`, resultados de ensaio e
backups estão excluídos do Git. As notas pessoais `Descricao projeto` também
permanecem locais.

O site pode apontar para a página `releases/latest` do repositório público,
onde cada visitante escolhe seu sistema. Links de uma versão específica usam
`releases/download/vVERSAO/NOME-DO-ARQUIVO`.

Página de downloads deste projeto:
https://github.com/Eduardo-Brandt/EditorGerber/releases/latest
