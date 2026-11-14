# Entrega 0.3.0 — 12/11/2026

Os dezesseis pedidos desta revisão estão implementados.

| Pedido | Comportamento disponível |
|---|---|
| 1. Salvar | Menu e ícone próprios, Ctrl+S no arquivo atual; Salvar como em Ctrl+Shift+S. |
| 2. Zoom no cursor | Scroll mantém o ponto do desenho sob o cursor. |
| 3. Régua em tempo real | Etiqueta junto ao cursor, distância, deltas e ângulo; pontilhado com inversão das cores atravessadas. |
| 4. Unidades | mm/in/mil nos campos dimensionais, propriedades, coordenadas e medidas; sem mudar o tamanho físico. |
| 5. Fonte de texto | Fontes instaladas, negrito, itálico, altura e rotação; alternativa PCB simples. |
| 6. Formas e gráfico | Arco, círculo, quadrado, retângulo e importação raster P&B com conversão de cores, limiar e preview. |
| 7. Cotas e polar | Cota por três cliques, setas/fonte personalizadas, precisão e unidade independentes; ângulo polar e coordenadas polares na visualização. |
| 8. Camadas e atividade | Nova camada no topo e à frente; dois cliques para cor/opacidade/função; ampulheta vetorial e progresso durante processamento ou ferramenta pendente. |
| 9. Grade | Valor editável, lista configurável e persistência entre sessões. |
| 10. Atalhos | Preferências com editor, conflitos e restauração; padrões de ações comuns do KiCad e régua Shift+A. Idioma não altera atalhos. |
| 11. Fechar arquivos | Menu Fechar todos e x por camada; confirmação de alterações e Undo/Redo do fechamento. |
| 12. Cursor | Opção entre cruz pequena e cruz de tela inteira. |
| 13. Negativos | Visualização opcional em cinza fantasma, respeitando visibilidade/opacidade da camada. |
| 14. Autoria | Ajuda → Sobre: Eduardo Guilherme Brandt, Indaial-Brasil, criação 11/11/2026, versão e link do site. |
| 15. Idiomas | Português e inglês, troca imediata; catálogos JSON extensíveis e traduções Qt para diálogos padrão. |
| 16. Splashscreen | Logo criativo Editor Gerber, marca EBRANDT em 3D no canto inferior direito, versão, autoria e link clicável. |

## Capturas

- [Interface em português](output/v03/01_portugues.png)
- [Régua em inglês, medindo 1 in em tempo real](output/v03/02_english_live_measure.png)
- [Escolha de fonte](output/v03/03_font_dialog.png)
- [Personalização da cota](output/v03/04_dimension_dialog.png)
- [Editor de atalhos](output/v03/05_shortcuts.png)
- [Splashscreen com dados de autoria](output/v03/06_splashscreen.png)

## Precisão e salvamento

Texto, gráficos e cotas viram geometria Gerber permanente. Não há um objeto
tipográfico/de cota paramétrico no arquivo Gerber; para alterar o resultado
posteriormente, selecione suas primitivas ou desfaça e insira novamente.
Fontes instaladas são convertidas em contornos vetoriais numa macro isolada,
com vazados transparentes que preservam objetos por baixo. Nenhuma fonte do
Windows é copiada ou distribuída junto com o programa.

O arquivo real `srlc` recebeu 29 objetos novos nas cópias de teste. Os 12.132
objetos originais permaneceram iguais em Preservation e Normalized, inclusive
na comparação geométrica por parser independente. O original permaneceu
intacto em disco. Relatórios e limites da verificação: [VALIDATION.md](VALIDATION.md).

## Arte da abertura

Criada com a ferramenta integrada de geração de imagens, usando o logo 2D
fornecido como referência. A composição final é feita pelo Qt com textos nítidos
de versão, data e autoria e um link clicável.

[Imagem incluída no pacote](gerber_editor/assets/splash.png) ·
[Prompt e procedência](gerber_editor/assets/IMAGE_PROMPT.md).
