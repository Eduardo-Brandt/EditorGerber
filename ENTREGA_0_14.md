# Editor Gerber 0.14.0 — instaladores nativos

Entrega de 16/11/2026, incluindo a abertura por Drag & Drop implementada na
preparação 0.13.3. O backup anterior `Backup/Editor_Gerber_v0.13.3.zip` foi
preservado. O backup desta entrega é `Backup/Editor_Gerber_v0.14.0.zip`.

## Pacotes

O workflow `.github/workflows/portable.yml` gera instaladores Windows x64
(Inno Setup EXE), Ubuntu/Debian x64 (DEB), macOS Intel (PKG) e macOS Apple
Silicon (PKG). Os arquivos portáteis ZIP/TAR.GZ continuam disponíveis.
Cada arquivo recebe SHA-256, e o código-fonte correspondente acompanha a Release.

Os instaladores usam o executável portátil verificado. O teste nativo instala
o pacote em um runner descartável e executa o aplicativo instalado para
conferir Gerber, Drag & Drop, recursos, ajuda nos dois idiomas, QR Code,
furação 3D e exportação WRL/STEP. Windows/Linux também verificam a remoção.
Os testes de instalação não são executados no perfil do computador local.

O instalador Windows trabalha no perfil do usuário. O DEB instala em
`/opt/editorgerber`, com um comando e uma entrada no menu. O PKG instala em
`/Applications/EditorGerber.app`, incluindo licenças e instruções no bundle.
No macOS, o bundle recebe assinatura ad hoc; o PKG não tem certificado
Developer ID Installer nem notarização. O Windows não possui Authenticode.

## Publicação

Repositório: https://github.com/Eduardo-Brandt/EditorGerber

Downloads: https://github.com/Eduardo-Brandt/EditorGerber/releases/latest

A publicação é condicionada ao sucesso dos quatro builds e dos respectivos
testes de instalação. A tag aponta para o commit exato usado na compilação.
Versões já publicadas e tags existentes são preservadas.

Veja `DISTRIBUICAO.md` para instalação, remoção, requisitos e futuras compilações.
