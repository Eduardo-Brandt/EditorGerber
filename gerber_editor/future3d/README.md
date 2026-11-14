# Contrato do futuro visualizador 3D

O visualizador inicial está implementado em `gerber_editor/viewer3d` desde a 0.4.
Esta pasta conserva o contrato de evolução e as alternativas avaliadas.
Entrada: `Board`, `BoardStackup`, camadas funcionais, outline validado e objetos
exatos em mm. Uma camada de adaptação deverá gerar geometrias booleanas e depois
meshes, sem modificar os objetos originais. Furos e slots serão canais no sólido
FR4. Z e espessuras virão do stackup, não da ordem visual da lista 2D.

| Tecnologia | Vantagens | Custos / limites a avaliar |
|---|---|---|
| PyVista | Prototipagem de meshes e interação pronta | Depende de VTK, distribuição volumosa |
| VTK | Pipelines sólidos de visualização científica | Tamanho e integração UI; não é kernel CAD |
| OpenGL direto | Controle fino, ampla disponibilidade | Muito trabalho de câmera, picking e recursos GPU |
| moderngl | API OpenGL mais simples em Python | Integração Qt/contexto, picking e materiais próprios |
| Qt3D | Integração com Qt e scene graph | Verificar disponibilidade/manutenção na versão alvo |
| OpenCascade | B-rep, booleanas CAD e STEP | Distribuição grande e integração de renderização |

O backend escolhido foi Qt/OpenGL 3.3, já incluído em PySide6-Essentials, com
triangulação restrita Shapely >=2.1. O protótipo foi validado em janela nativa
Windows e gera substrato com recortes e superfícies Cu/Mask/Silk/Paste.
Há câmera orbital, perspectiva/ortográfica, vistas, materiais e espessura.
Stackup completo, Excellon/metalização e componentes STEP são etapas futuras.
Desde a 0.5, há recortes/rasgos, relevo das trilhas, iluminação por materiais,
janela independente, inversão animada e exportação JPG/WRL/STEP com cores.
O backend opcional OpenCascade converte os polígonos da prévia em sólidos CAD,
sem alterar os Gerbers de origem.

Referências primárias:
[QOpenGLShaderProgram](https://doc.qt.io/qtforpython-6.11/PySide6/QtOpenGL/QOpenGLShaderProgram.html) e
[triangulação restrita Shapely](https://shapely.readthedocs.io/en/2.1.2/reference/shapely.constrained_delaunay_triangles.html).
