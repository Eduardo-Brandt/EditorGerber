# Roadmap

## Fase 1 — MVP de serigrafia (concluída)

- Modelo Decimal, tokenizer preservando origem e parser básico estrito.
- Writer preservation / normalized com reabertura e comparação semântica.
- PySide6: camadas sobrepostas, propriedades, zoom, pan e grade.
- Seleção individual, Ctrl, janela/crossing; Delete e Undo/Redo.
- Linhas e texto stroke vetorial; demonstração com logo removível.
- Testes de parsing, round-trip, preservação, histórico e interação Qt.

Critério atendido com fixture e com seleção/exclusão em dez Gerbers reais.
Os objetos restantes mantêm a geometria, e os originais permanecem intactos.

## Entrega 0.2 — compatibilidade real e interface GerbView

- IPPOS/LN/IN e nomes de arquivos sem extensão, CAMMaster com resolução 3.3.
- Macros 1/4/5/20/21/22, variáveis, expressões seguras e writer de primitivas.
- Normalização conserva a grade necessária à validade dos arcos legados.
- Canvas preto, gerenciador à direita, ferramentas verticais e menus em português.
- Importação em worker, caches de apertures e seleção espacial.
- Move/Copy por Delta X/Y com Undo/Redo; medição de distância.
- Teste de dez arquivos reais (até 110.457 objetos); relatório e capturas.

## Entrega 0.3 — produtividade, desenho e apresentação (concluída)

- Salvar atual/Salvar como, fechamento individual/todos e proteção de alterações.
- Zoom no cursor, régua em tempo real invertida e mm/in/mil em todos os campos dimensionais.
- Arcos, círculos, quadrados, retângulos, fontes instaladas, raster P&B e cotas.
- Camada nova à frente, menu por duplo clique e indicador de atividade.
- Grade/atalhos/idioma persistentes; português e inglês com IDs de ações estáveis.
- Coordenadas polares, cursor de tela inteira e negativos em cinza fantasma.
- Autoria/versão/site, marca Editor Gerber e splashscreen com EBRANDT em 3D.
- Conferência opcional pelo Gerbonara, incluindo preservação do srlc real.

## Entrega 0.4 — edição pelo cursor e 3D inicial (concluída)

- Nome Editor Gerber em toda a interface e apresentação acessível pela Ajuda.
- Ortho com Shift, snap de extremidades/vértices/centros e marcador visual.
- Clipboard, recorte, colagem e movimento pelo cursor; seleção e arraste.
- Cópias espelhadas e matrizes retangulares/polares com histórico.
- Dimensões geométricas editáveis e textos agrupados durante a sessão.
- PCB 3D por Alt+3, contorno/recortes, materiais, câmera e detalhes de malha.
- OpenGL 3.3 validado no Windows e comparação independente do srlc atual.

## Entrega 0.5 — roteamento, exportações e software livre (concluída)

- Backups ZIP por versão, camada ativa em primeiro plano e opacidade padrão 100%.
- Duplo clique, medidas sincronizadas, texto lembrado e snap de meios/quadrantes.
- Fiduciais em cobre/máscara, rasgos por largura e recortes por perfis/regiões.
- Janela 3D independente, pan corrigido, F animado e novo ícone.
- Trilhas sob máscara, camadas internas e iluminação por material.
- JPG em resolução escolhida, WRL e STEP com cores e validação CAD.
- GPLv3, SOFTWARE LIVRE e painel de apoio Pix/PayPal pendente.

## Fase 2 — Compatibilidade de fabricação

- Completar primitivas AM 6/7 e ampliar corpus de testes oficiais Ucamco.
- AB, SR, transformações e formatos legados por adaptador isolado.
- Excellon: ferramentas, PTH/NPTH, hits e slots roteados; writer e testes.
- Corpus de fabricantes/CADs e testes diferenciais com backend independente.
- Worker de exportação/edição, redução de memória, tiles e LOD.

## Fase 3 — Edição CAM

- Rotate/Mirror/Scale e propriedades geométricas por comandos.
- Polígonos e flashes por ferramentas dedicadas; snap a objetos/interseções.
- Persistência de texto/cotas paramétricos no projeto; SVG seguro para logos.
- Offset, align, array; seleção por tipo/similaridade e cotas paramétricas no projeto.
- Outline: fechado, duplicatas, auto-interseções e drills fora da placa.

## Revisão 0.5.1 — atividade e atualização do 3D (concluída)

- Ampulheta central animada no editor e no visualizador.
- Atualização ao retornar à janela 3D, agrupando edições e conservando a câmera.
- Descarte de resultados de revisões antigas; limpeza após fechar as camadas.
- Gestor de camadas com itens estáveis e callbacks adiados para evitar falha Qt.
- Logs de erros Python/Qt/threads e diagnóstico de falhas nativas.
- Instruções para iniciar pelo terminal do VS Code; novo backup por versão.

## Revisão 0.5.2 — navegação e abertura em lote (concluída)

- Splash com mínimo de quatro segundos e convite clicável ao apoio; Sobre idem.
- Paleta esquerda em colunas, com opção persistente para manter todos os botões.
- Visualizar, Preferências e Ajuda no 3D; últimas pastas persistentes.
- Website atualizado para brandttecnologia.com.br/EditorGerber e Iniciar.bat.
- Cache auxiliar KiCad ignorado sem erro de parser; falhas reais agrupadas.
- Fila de importação sem reentrada na GUI e bloqueio de entrada durante trabalho.

## Revisão 0.6 — resposta do módulo 2D (concluída)

- Atualização incremental da cena, conservando objetos e camadas sem alterações.
- Cor, opacidade e visibilidade sem recriar geometrias ou itens de seleção.
- Objetos sem seleção dispensam pintura; destaque reativado ao selecionar.
- Cache de dispositivo do Qt para camadas opacas, invalidado por escala/conteúdo.
- Grupos de seleção por camada e limites preparados para ativação/enquadramento.
- Comparação reproduzível com o código arquivado da 0.5.2 e testes de regressão.
- Próximos passos: composição espacial para reduzir primeira abertura/edições,
  índice de seleção mais compacto e cache persistente com orçamento de memória.

## Revisão 0.7 — blocos para navegação e edição 2D (concluída)

- Composição espacial com STRtree, preservando a ordem dark/clear por célula.
- Reutilização dos blocos não afetados por edição, exclusão, inclusão ou undo.
- Pintura dos blocos visíveis com margem e clip, sem diminuir detalhe das curvas.
- Snap reutilizado entre quadros estacionários; buscas dispensadas durante pan.
- Camadas de apresentação fora das consultas de hit testing dos objetos.
- Cache de imagens de 64 MiB sob demanda para múltiplas camadas.
- Comparação reproduzível com a 0.6.0, incluindo atualização de objetos reais.
- Próximos passos: composição paralela controlada e seleção mais compacta.

## Revisão 0.8 — ícone, furação e organização (concluída)

- Ícone com PCB ampliada e ICO em sete tamanhos para Windows.
- Inicialização maximizada do editor e abertura maximizada do 3D.
- Furação passante Gerber (`fur`, Drill, Plated/NonPlated) no substrato e materiais.
- Rasgos e furos pequenos preservados no preview e nas exportações.
- Distinção entre dados físicos e Drillmap; blind/buried recusados explicitamente.
- Setas para ordenar camadas com undo/redo; lista define a sobreposição visual.
- Ordem automática por função e cobre interno ao abrir lote com editor vazio.
- Excellon, metalização e stackup completo permanecem como evolução separada.

## Fase 4 — Projeto e preparação 3D

- `.gproj` versionado, persistência de visualização, stackup e materiais.
- Ampliar o 3D atual com stackup completo, furos Excellon e metalização.
- Picking 3D e otimização de placas muito grandes.
- Modelos STEP de componentes em fase posterior.
