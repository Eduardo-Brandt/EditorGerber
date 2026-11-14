# Splashscreen — Editor Gerber

- Asset final: `splash.png` (neste diretório).
- Modo: ferramenta integrada `image_gen`, sem CLI/API externa.
- Referência: logo 2D EBRANDT Tecnologia anexado pelo usuário.
- Dados de autoria, versão, criação e link são sobrepostos pelo Qt em `ui/splash.py`.
- A imagem original gerada permanece no diretório de imagens do Codex; esta cópia é incluída no pacote do aplicativo.

## Correção da grafia

A arte atual substitui “Editr Gerber” por **Editor Gerber**, mantendo o estilo,
a composição e a marca EBRANDT. Edição pela ferramenta integrada `image_gen`;
salva em `gerber_editor/assets/splash.png` e já aplicada à abertura do aplicativo.

### Prompt final da edição

Use case: text-localization. Asset type: existing Windows application splashscreen artwork. Input image 1 is the EDIT TARGET. Correct only the large main wordmark from 'Editr Gerber' to exactly 'Editor Gerber'. The first word must contain six letters: E-d-i-t-o-r; add the missing lowercase o between t and r. Retain the same italic brushed-silver 3D typography for 'Editor' and cyan 3D typography for 'Gerber', balancing the text within the existing main wordmark area. Preserve the PCB milling icon, background circuit board, copper traces, navy/cyan palette, lighting, composition, empty lower-left footer area, and small lower-right EBRANDT TECNOLOGIA brand logo unchanged. Keep the same landscape proportions. No additional text, no version, no name, no URL. Primary exact text: 'Editor Gerber'.

## Prompt original (antes da correção)

Use case: logo-brand / stylized-concept. Asset type: final landscape splashscreen artwork for a Windows PCB Gerber editor. Reference image 1 is the user's EBRANDT TECNOLOGIA brand logo; use it as the strict identity reference for a small 3D embossed brand in the lower right. Create a polished, creative engineering software splash artwork, wide 16:9, with a deep navy/graphite background, subtle PCB copper traces, tiny vias and an elegant dimensional circuit-board monogram, brushed silver plus blue/cyan accents. Main exact program wordmark: 'Editr Gerber', large, crisp, sophisticated at upper left/center-left, integrated with a distinctive creative PCB/CAM logo; spell Editr exactly E-d-i-t-r (without o). Main artwork on upper two thirds. Keep lower-left quarter dark and quiet with generous empty space for runtime creator/version labels that the application will draw. Small lower-right 3D EBRANDT TECNOLOGIA logo: preserve the reference's italic angular letterforms and blue stylized E, black BRANDT made dimensional with readable charcoal and metallic edge highlights, TECNOLOGIA below, subtle extrusion and perspective, brand occupying roughly one quarter of width. Leave a slim blank area below this small logo for an application-rendered web link. Text only 'Editr Gerber', 'EBRANDT', 'TECNOLOGIA'. Do not render version, personal name, date or URL into this image. No other slogans, no watermark, no UI frame. Clean professional composition with excellent legibility and accurate reference branding.
