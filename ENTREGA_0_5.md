# Editor Gerber 0.5.0

## Pedidos atendidos

| Item | Resultado |
|---|---|
| 0.8 | Backup verificado da 0.4.0 antes das mudanças; ZIP por versão em Backup, excluída do Git; criação automática na inicialização do projeto e comando manual. |
| 0.9 | Camada selecionada à frente no canvas; importação com 100% de opacidade, mantendo os controles manuais. |
| 1 | Comprimento/ângulo e coordenadas inicial/final da linha se atualizam em tempo real. |
| 2 | Duplo clique abre edição. Último texto, fonte, dimensões, rotação e estilos são lembrados. Regiões também oferecem deslocamento/rotação. |
| 3 | Snap inclui meio das linhas, quadrantes e diagonais a cada 45°, respeitando os limites dos arcos. |
| 4 | Fiducial com ponto por clique/snap ou coordenadas; cobre, abertura de máscara, face e Undo/Redo conjunto. |
| 5 | 3D em janela de nível superior independente, sem janela proprietária nativa no Windows. |
| 6 | Ícone derivado do emblema da splashscreen, em PNG transparente e ICO com vários tamanhos. |
| 7 | Recortes e rasgos por objetos comuns, camada Route.Cuts, modos perfil/traço, círculos, regiões e visualização através da PCB. |
| 8 | Pan vertical acompanha o mouse, inclusive olhando o verso; horizontal mantido. |
| 9 | Trilhas F.Cu/B.Cu e internas; reconhecimento de Inner/Iner/In; relevo e cor de cobre sob máscara. |
| 10 | F e botão Inverter placa; animação de 550 ms em torno do eixo Y. |
| 11 | Opção Realista com iluminação, reflexos e acabamento diferentes para cobre, máscara, FR4 e serigrafia. |
| 12 | JPG em resolução escolhida; WRL e STEP/AP214 com cores. Exportação de modelo em worker; STEP reaberto e validado. |
| 13 | SOFTWARE LIVRE no Sobre/splash; GPLv3 escolhida pelo criador; tela de apoio com Pix, QR e Copia e Cola. PayPal preparado, aguardando URL. |

## Backups

- [Versão 0.4.0 preservada](Backup/Editor_Gerber_v0.4.0.zip)
- [Versão 0.5.0](Backup/Editor_Gerber_v0.5.0.zip)

Os ZIPs guardam fontes e recursos do programa. Não incluem ambientes virtuais,
dependências binárias instaladas, saídas de testes, outros backups ou Gerbers
externos à pasta do projeto. A restauração pode ser feita em outra pasta,
recriando o ambiente pelas dependências declaradas no README.

## Imagens e arte

- [Editor](output/v05/01_editor.png)
- [Editor de linha](output/v05/04_line_editor.png)
- [Fiducial](output/v05/05_fiducial.png)
- [Recortes](output/v05/06_cutouts.png)
- [3D com trilhas e rasgos](output/v05/08_native_3d.png)
- [Placa invertida](output/v05/09_native_flipped.png)
- [JPG 2560 × 1440](output/v05/PCB_2560x1440.jpg)
- [STEP com cores](output/v05/PCB_with_cutouts.step)
- [WRL com cores](output/v05/PCB_with_cutouts.wrl)
- [Sobre](output/v05/02_about.png) e [splashscreen](output/v05/07_splashscreen.png)
- [Suporte](output/v05/03_support.png) e [QR Pix](output/v05/Pix_Editor_Gerber.png)
- [Ícone PNG](gerber_editor/assets/app_icon.png), [ICO](gerber_editor/assets/app_icon.ico)
  e [prompt da ferramenta integrada de imagens](gerber_editor/assets/ICON_PROMPT.md)

## Precisão e limites

O Gerber de origem não é convertido em malha ao salvar. A prévia e os modelos
3D usam a discretização e o detalhe escolhidos: Fino 0,01 mm, Normal 0,025 mm,
Rápido 0,1 mm. O STEP emprega geometria poligonal extrudada em sólidos, com
coordenadas CAD ajustadas a 0,000001 mm; não recupera curvas CAD paramétricas.
Sólidos e volumes são verificados quando se aplica correção topológica de
tolerância. Um arquivo existente só é substituído após exportação validada.

Materiais são sólidos separados no STEP. Ainda não há componentes, Excellon,
metalização ou stackup completo. A renderização Realista é rasterização com
materiais e luzes, sem ray tracing. O backend STEP é opcional na instalação
nova e está disponível no ambiente entregue.

Texto editável mantém o limite da sessão: salvar não elimina sua edição em
memória, mas reabrir um Gerber não reconstrói texto/fonte a partir de vetores.

## Licença e apoio

Copyright (C) 2026 Eduardo Guilherme Brandt. Código sob [GPLv3](LICENSE),
conforme escolha do criador. Avisos: [COPYRIGHT.md](COPYRIGHT.md).

O QR Pix não fixa valor e contém a chave fornecida. Sua estrutura/CRC foi
comparada com o exemplo do [Banco Central](https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Regulamento_Pix/II_ManualdePadroesparaIniciacaodoPix.pdf)
e a imagem foi decodificada pelo ZXing-C++. PayPal aguarda o endereço fornecido
pelo criador; não foi criado um destino fictício.

Validação completa: [VALIDATION.md](VALIDATION.md).
