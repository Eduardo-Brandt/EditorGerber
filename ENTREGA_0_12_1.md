# Editor Gerber 0.12.1 — ícones de edição e campos cinza

Entrega de 14/11/2026. O backup anterior foi preservado em
`Backup/Editor_Gerber_v0.12.0.zip`, SHA-256
`3180db2c55ed45485928895bf26a5cec834e0bb47537223a020bb70a20e4c934`.

## Barra superior

Os quinze comandos do menu Editar aparecem juntos na seção de edição da
barra superior: desfazer, refazer, excluir, mover pelo cursor, copiar,
recortar, colar, duplicar, espelhar, matriz, agrupar, desagrupar, deslocamento,
selecionar todos e limpar seleção.

Os ícones são vetoriais e usam as mesmas ações do menu. Atalhos, dicas,
habilitação, histórico e clipboard permanecem sincronizados. Em janelas
estreitas, a extensão da barra permite acessar itens que não couberem.

## Campos sem edição

O tema global aplica fundo cinza aos campos desabilitados e de somente
leitura. O texto também fica cinza, mantendo contraste. A aparência acompanha
automaticamente as mudanças de modo nos diálogos de matriz, imagem e texto.
Campos habilitados usam a aparência normal.

A tabela de consulta de propriedades também usa fundo cinza. O botão de
edição e o duplo clique continuam abrindo as propriedades. A chave Pix de
somente leitura permite selecionar e copiar normalmente. A ajuda HTML
conserva sua apresentação de documento.

## Verificação e backup

Passaram os **69 testes** relacionados à interface, arquivos, agrupamento e
edição. Ruff também passou. Na conferência nativa do Windows, os quinze ícones
ficaram visíveis na janela maximizada. Foram exercitados agrupar, desfazer,
copiar e limpar seleção pelos botões da barra.

Foram conferidas as cores nas matrizes retangular/polar, na importação de
imagem com X/Y habilitados/desabilitados, nas opções de fonte, na chave Pix
e na tabela de propriedades. Também foram conferidos o layout com janela
menor e a ajuda HTML. Capturas e relatório estão em `output/v0121/`.

Backup desta entrega: `Backup/Editor_Gerber_v0.12.1.zip`. Os backups anteriores
permanecem preservados.
