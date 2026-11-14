# Fixtures

- `basic.gbr`: linha, arco de meia volta, flash retangular, região, flash clear,
  aperture circular/retangular e atributos X2 de arquivo/aperture.
- `macro_unsupported.gbr`: macro com primitiva thermal 7, ainda não suportada.
  O editor deve recusar explicitamente
  esse arquivo, sem mostrar uma imagem incompleta nem permitir exportá-lo.
- `legacy_cam.gbr`: formato 3.3 com zeros à direita, IPPOS, LN, G54/D1 curtos,
  macro outline e arco com diferença de raios compatível com a grade original.
- `drill.gbr`: furação X2 Plated/PTH com furos de 1,2 e 0,2 mm e um rasgo
  passante por traço de 0,8 mm, usado para conferir vazios no 3D e no STEP.
- A demonstração de serigrafia é gerada por `gerber_editor.tools.demo`; o script
  `scripts.verify_mvp` grava a entrada/saídas em `output/verification`.

Outros casos pequenos são inline nos testes: círculo completo, G74, regiões com
furos, coordenadas modais, inch, supressão de zeros, atributos de objetos e erros.
