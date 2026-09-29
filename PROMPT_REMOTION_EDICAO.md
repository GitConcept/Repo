# Prompt: edição horizontal "talking head + B-roll tela cheia + legenda posicionada" (Remotion)

Cole tudo abaixo no Claude Code, dentro de um projeto Remotion (`npx create-video@latest`, template blank, TypeScript).
Referência de estilo: `REFERENCIA_4.mp4` (colocar em `reference/` para consulta; **não** é o vídeo a ser editado).

---

## PAPEL
Você é um editor de vídeo sênior e engenheiro Remotion. Vou fornecer vídeos brutos horizontais que são **gravações de videochamada** (webcam, 1920x1080, 25 fps), com o apresentador falando e, em alguns trechos, um segundo participante (entrevistador) que aparece quando fala ou reage. Entregue uma composição Remotion que o transforma em um vídeo editado no estilo abaixo, de forma **automatizada e parametrizável**: transcrição → plano de edição (JSON) → render.

## FILOSOFIA DE EDIÇÃO (leia antes de tudo)
**Seco e direto. Tudo é corte.** Simula a troca de câmera e a montagem de um editor humano, não um template de motion graphics.
- **PROIBIDO**: bounce, overshoot, `spring` com sobra, scale-in/scale-out, pop, slide, whip, glitch, dissolve, wipe, zoom animado, Ken Burns, push-in/pull-out, shake. Nada disso, em nenhum elemento (vídeo, B-roll, texto).
- Toda entrada e saída de elemento visual é **corte de 0 frames** (aparece no frame exato, some no frame exato).
- Única exceção de movimento permitida: **fade de opacidade de no máximo 3 frames** na saída de textos do tipo "cartão preto" (ver 4). Se em dúvida, corte.
- Nenhum elemento usa `spring()`. Use `interpolate` somente para o fade citado e para o revelar de palavra descrito em 3.

## ESPECIFICAÇÕES TÉCNICAS
- Composição **horizontal 1920x1080, no fps do bruto** (os brutos enviados são 25 fps; **não converter para 30**). Use `calculateMetadata` para ler resolução/fps/duração do arquivo.
- Vídeo bruto em `public/input.mp4` via `<OffthreadVideo>`. Áudio original sempre mantido.
- Stack: Remotion 4.x, TS, `@remotion/captions`, `@remotion/google-fonts`, `@remotion/install-whisper-cpp`.
- Toda a edição é dirigida por **`edit-plan.json`**. Componentes só renderizam o plano; nenhum tempo hard-coded.

## O BRUTO REAL (analisado nos 4 cortes enviados: 55 s, 65 s, 82 s e 79 s)
Isto muda partes do que vem depois. Trate como regras, não como sugestão:
1. **É videochamada, não câmera de estúdio.** Luz chapada, sala clara e branca. A referência é escura, quente, com contraste. Portanto o look exige um **grade geral forte, com curva que afunda os brancos da parede e foco de luz no rosto** (ver 1). Sem recorte de fundo. Sem grade o resultado não parece a referência, mesmo com o resto perfeito.
2. **Há uma etiqueta com o nome do participante no canto inferior esquerdo** (ex.: "Gabriel Magela", "cabine branca") e uma leve faixa escura embaixo. **Precisa sumir em todo o vídeo.** O enquadramento "aberto" não pode ser 1.00: use no mínimo **scale 1.10 ancorado no canto superior direito** (`transform-origin: top right`), que corta a etiqueta. Depois do corte, confirmar em imagem que a etiqueta não aparece em nenhum frame de nenhum enquadramento.
3. **Dois participantes.** O apresentador é o "principal" (quase todo o tempo). O segundo aparece em trechos curtos (em um dos cortes, ~9 s dispersos), em sala escura com outra câmera. Tratar como **outra câmera**: detectar a troca de pessoa (mudança brusca de brilho/cena), rastrear o rosto de cada um separadamente, aplicar os mesmos 3 enquadramentos de forma independente, legendar a fala dele também e **não** aplicar o grade do apresentador em cima do dele sem ajustar (a sala dele já é escura: grade mais leve, casando o look). Trocas de pessoa contam como troca de plano; não empilhar troca de enquadramento no mesmo frame da troca de pessoa.
4. **O rosto se move bastante dentro do quadro** (centro horizontal do rosto varia de ~740 a ~1300 px em 1920; vertical de ~410 a ~670). **Uma caixa de rosto fixa por enquadramento NÃO serve.** Rastrear o rosto **frame a frame**, com suavização (média móvel ~5 frames, sem tremor), e usar a posição real no frame corrente para: (a) centralizar os enquadramentos médio e fechado (transform estático por trecho, calculado pela posição média do rosto naquele trecho, para o rosto nunca sair do quadro nem ficar cortado); (b) calcular a zona proibida das legendas naquele instante.
5. **Detecção**: o detector simples que testei (Haar) achou o rosto em ~95–100% dos frames, mas falha com a cabeça baixa/virada e o retângulo cobre só olhos-boca-queixo, **sem testa e cabelo**. Use detector melhor (MediaPipe Face Detection/Face Mesh) e **expanda a zona proibida** ~35% para cima (testa/cabelo) e ~15% nas laterais e embaixo. Nos frames sem detecção, interpolar entre os vizinhos.
6. **Mãos ocupam o espaço lateral** (ele gesticula muito com as duas mãos abertas). A legenda lateral deve fugir das mãos: se possível detectar mãos (MediaPipe Hands) e tratá-las como zona de baixa prioridade; se não, preferir o lado oposto ao da mão em movimento.
7. **Qualidade**: 1080p de webcam, um pouco suave. O enquadramento **fechado não passa de scale 1.4** (acima disso vira imagem mole). Aplicar um leve sharpen (unsharp 0.3) e grão fino no final para disfarçar.
8. **Dimensões do rosto**: o rosto do apresentador ocupa ~28–31% da altura do quadro no aberto. No fechado (1.4x) chega a ~42%; cuidado para o topo da cabeça não sair do quadro (ancorar o corte para manter ≥ 6% de folga acima do cabelo).

## PIPELINE (scripts npm)
1. `npm run transcribe` — extrai áudio (ffmpeg), transcreve com timestamps **por palavra** (Whisper, `pt`, modelo `medium` ou maior) → `public/captions.json`. Revisar a transcrição (nomes próprios, marcas) antes do passo 2.
2. `npm run framing` — **rastreia o rosto frame a frame** (MediaPipe) para cada participante, detecta trocas de pessoa, e grava `framing.json` com, por frame: bbox do rosto suavizada, `faceZone` (bbox expandida como em "O BRUTO REAL" item 5), espaço livre à esquerda/direita, e, por trecho de enquadramento, o transform (scale + translate) que mantém o rosto bem enquadrado.
2b. **Verificação do rosto (obrigatória, o usuário não é técnico)** — depois do `framing`, gere `verify/framing-wide.png`, `framing-medium.png` e `framing-close.png`: um frame real do bruto em cada enquadramento com um **retângulo vermelho desenhado sobre o rosto** e a `faceZone` (com margem) em amarelo. Mostre as 3 imagens e pergunte só: "O retângulo vermelho está cobrindo o rosto inteiro (testa ao queixo) nos 3 enquadramentos? Sim/Não". Só siga para o passo 3 com "Sim". Se "Não", corrija as coordenadas e gere de novo. Explique tudo em português simples, sem jargão.
   Além disso, teste automático: para o vídeo inteiro, verificar em **todos os frames** (não só amostras) que nenhum texto (legenda ou destaque) intersecta a `faceZone` do enquadramento ativo naquele frame. Se houver colisão, corrigir a posição e repetir. Ao final do render, gerar `verify/legendas-amostra.png`: 12 frames aleatórios do vídeo final em grade, para eu olhar e aprovar visualmente.
3. `npm run plan` — gera `edit-plan.json` a partir da transcrição (ver "Como decidir a edição").
4. `npm run assets` — resolve os B-rolls (ver "Assets").
5. `npm start` (Studio) e `npm run render` (H.264, CRF 18).

---

## O ESTILO

### 1. Talking head: 3 enquadramentos, troca por corte seco
O bruto é UM plano. Simule 3 "câmeras" recortando/escalando o mesmo vídeo com **transform estático** (`scale` + `translate` constantes durante o trecho, sem interpolar):
- **Aberto** — scale **1.10** ancorado no canto superior direito (esconde a etiqueta de nome; ver "O BRUTO REAL" item 2), com o rosto ainda pequeno e espaço vazio nas laterais. Padrão.
- **Médio** — scale ~1.15–1.2, centrado no rosto.
- **Fechado** — scale ~1.35–1.4 (máx. 1.4 pela qualidade da webcam), rosto no terço superior/centro, olhos numa linha estável.
Regras:
- **Nunca há zoom animado.** O scale muda de um valor para outro num único frame (corte).
- Troca de enquadramento a cada **3–8 s**, sempre em pausa de respiração, fim de frase ou palavra de ênfase. Nunca repetir o mesmo enquadramento em dois cortes seguidos; nunca pular de aberto para aberto.
- Manter o enquadramento pelo menos 2 s antes de trocar de novo (exceto dentro de trecho P&B, ver 5).
- Corte de jump (remover pausas > 0.4 s e vícios "é…", "né") deve ser combinado com troca de enquadramento sempre que possível, para o jump cut parecer troca de câmera e não erro. Crossfade de áudio de 2 frames nos cortes.
- **Look cinematográfico obrigatório: UM ÚNICO grade geral aplicado ao quadro inteiro. PROIBIDO recortar/segmentar a pessoa, usar máscara, matte ou tratar fundo e pessoa separadamente** (testei e gera halo no cabelo, mão "fantasma" e piscadas). Implementar como um só filtro por vídeo (CSS/SVG filter ou canvas/WebGL por frame), na ordem:
  1. **Balanço de branco**: a parede é azulada. Multiplicar os canais RGB por ≈ `R×1.12, G×0.96, B×0.84` antes de qualquer outra coisa.
  2. **Escurecer com curva**: `gamma ≈ 2.0` (puxa os brancos da parede para cinza-escuro e afunda as sombras), `gain 1.0`, depois contraste em S ≈ +15% em torno de 0.5.
  3. **Dessaturar** ~45% (saturação 0.55) para o visual sóbrio da referência.
  4. **Tom levemente quente** multiplicando RGB por ≈ `R×1.05, G×0.99, B×0.94`. Não passar disso: acima vira laranja/amarelo e o rosto fica avermelhado.
  5. **Foco de luz suave no rosto (gradiente radial, não é recorte)**: elipse gaussiana centrada no rosto atual (posição vinda de `framing.json`, suavizada), largura ~40% do quadro, altura ~62%, luz mínima nas bordas = 0.30; a luz cai de forma contínua, sem borda definida. Isso mantém o rosto legível mesmo com o fundo escuro.
  6. **Vinheta** ~45% nos cantos, **grão fino** (ruído gaussiano σ≈0.006), leve sharpen (unsharp 0.3).
  7. **INTENSIDADE FINAL = 0.20 (obrigatório, padrão)**: o passo 1 a 6 descrevem o grade "cheio", que o usuário achou pesado demais. O resultado final é a **mistura linear do frame original com o frame gradeado**: `saida = original + (gradeado − original) × intensity`, com `config.grade.intensity = 0.20`. Ou seja, o look é sutil: parede só um pouco mais neutra e escura, rosto mais bem iluminado, vinheta leve. **Não é para ficar próximo da referência escura**; é aceito que fique bem mais claro que ela. Opções que só uso se eu pedir: `0.30` e `0.40`. Nunca acima de 0.40.
  - Parametrizar tudo em `config.grade` (`intensity`, `gamma`, `gain`, `saturation`, `tint`, `spot`, `vignette`, `grain`) para eu ajustar olhando o Studio. Presets (todos usam `intensity 0.20`): `"neutro"` (tint `[1,1,1]`, saturation 0.50), `"quente-suave"` (padrão, valores acima) e `"escuro"` (gamma 2.3, spot 0.22, vignette 0.55; **cuidado: o rosto fica alaranjado, usar só se eu pedir**).
  - **Riscos a checar em imagem**: rosto subexposto (se o rosto ficar mais escuro que a parede, subir `spot` ou baixar `gamma`), bandas/degraus no fundo escuro (o grão resolve; se persistir, dithering), pele alaranjada (reduzir o tom quente).
  - Para o **segundo participante** (sala já escura), aplicar o mesmo grade com `gamma ≈ 1.2`, sem foco radial, casando o brilho médio com o do apresentador.

### 2. B-roll: SEMPRE tela cheia, corte seco
- **Não existe tela dividida, card, picture-in-picture, moldura ou cantos arredondados.** O asset ocupa 100% do quadro (`object-fit: cover`, 1920x1080), substituindo a imagem da pessoa; **o áudio dela continua**.
- Entra e sai por corte, sem animação. Asset estático (foto) fica parado; clipe de vídeo toca normalmente (`OffthreadVideo`, `muted`).
- Duração de cada B-roll: **0.8–3 s**. Cobertura total: ~25–40% do vídeo (ajustável em `plan.config.brollTarget`). Máx. 2 B-rolls seguidos sem voltar ao rosto por ≥ 1.5 s.
- Dispara quando o narrador cita algo concreto e visualizável (pessoa, marca, produto, lugar, ano, objeto, cena, número em tela). Abstrações só ganham B-roll se houver metáfora visual clara. Melhor menos e certeiro do que muito e genérico.
- Legenda **continua visível por cima do B-roll** (mesmo estilo, centralizada, sem depender de posição do rosto), com sombra suave para leitura.
- Fotos históricas: opcionalmente P&B com grão leve. Sem outros efeitos.
- Ao voltar da imagem para o rosto, retorna ao **mesmo enquadramento** de antes do B-roll, ou a outro enquadramento diferente (por corte). Nunca ao mesmo enquadramento duas vezes seguidas com B-roll no meio sem motivo.

### 3. Legendas: palavra a palavra, posicionadas com intenção
Referência: a legenda **não fica travada embaixo**. Ela é posicionada no quadro a cada bloco.
- Blocos de **1–4 palavras** (frase curta), alinhados ao ritmo da fala. Nunca linha longa. Uma linha só.
- **Fonte**: sans neutra/grotesca em negrito (Inter ou similar), ~40–46 px em 1080p, branca, **tracking bem apertado (-0.03em)**, sombra suave `0 2px 10px rgba(0,0,0,.5)`. Caixa normal.
- **Posição por bloco: dinâmica, irregular e NUNCA cíclica.** A legenda não usa "slots" fixos nem alterna entre 3 lugares. Cada bloco recebe uma **posição contínua** `(x, y)` sorteada dentro da **área livre** do enquadramento atual (quadro inteiro menos `faceZone` com margem de ~40 px, menos as bordas de segurança de 6%). Regras:
  - **Sorteio com semente** (`plan.config.seed`, para o render ser reproduzível), com distribuição **ponderada, não uniforme**: ~35% região do peito/abaixo do queixo, ~45% espaço lateral (esquerda/direita, altura do rosto ao ombro, com lado escolhido ao acaso), ~20% posições "soltas" (canto superior lateral, meio da lateral, perto do ombro, um pouco acima da cabeça se houver espaço). Pesos ajustáveis em `config.captionWeights`.
  - **Variação contínua**: além da região, aplique jitter de ±3–6% em x e y, para nunca haver duas posições idênticas. Alinhamento do texto (esquerda/centro/direita) acompanha o lado: texto lateral fica encostado no lado do rosto, não centralizado num ponto qualquer.
  - **Ritmo irregular de repetição**: o tamanho da sequência na mesma região varia (1, 2, 4, 1, 3…): 30% das vezes muda a cada bloco, 40% mantém 2 blocos, 20% mantém 3–4, 10% mantém mais tempo se a fala estiver rápida ou se for uma frase contínua. **Proibido** padrões periódicos (A-B-C-A-B-C ou A-B-A-B). Proibido alternar esquerda/direita em zigue-zague por mais de 2 blocos.
  - **Quando muda, muda de verdade**: a nova posição deve ficar a pelo menos ~15% da largura ou ~15% da altura da anterior. Quando fica na mesma região, pode deslocar poucos pixels (jitter), como um editor que nudged a legenda.
  - **Gatilhos que sobrepõem o sorteio** (dão intenção): (a) palavra-chave/número forte → posição mais próxima ao rosto, no lado para onde ele gesticula ou olha; (b) frase que começa após pausa longa ou troca de enquadramento → forçar mudança de região; (c) mão/gesto grande em um lado → texto vai para o lado oposto; (d) mudança de enquadramento → a legenda reposiciona no mesmo frame do corte (é a hora natural de mudar).
  - **Nunca cobrir olhos e boca**; usar as zonas de `framing.json`, que mudam a cada enquadramento (o rosto se move quando escala). Em `close`, a área lateral é menor: aumentar o peso do peito/abaixo do queixo automaticamente.
  - Sobre B-roll a legenda também usa posições variadas (terço inferior, centro, laterais), só respeitando margens de segurança.
  - Sem animação de deslocamento entre posições: o bloco novo simplesmente aparece no novo lugar (corte).
- **Revelar palavra**: as palavras do bloco aparecem **no frame exato em que são faladas** (corte, sem fade, sem movimento). Opcional: as palavras ainda não faladas do bloco ficam visíveis em cinza (~35% de opacidade) e acendem em branco quando ditas (como "as pessoas amam **comprar**" na referência). Configurável (`captionReveal: "cut" | "dim-ahead"`).
- **Variante espaçada** (rara, ≤ 1 a cada ~20 s, só em frases de efeito): as palavras do bloco ficam **distantes umas das outras** ("O ······ SEU ······ PRODUTO"), distribuídas na largura, ainda aparecendo no tempo da fala.
- **Variante serifa** (rara, ≤ 3 por vídeo, frase de impacto curta): serifa condensada em **caixa alta** (Playfair Display / Bodoni Moda / Cormorant), branca, ~48–64 px, tracking apertado. Corte seco.
- Sincronia: cada palavra em `startMs` do Whisper com adiantamento de 1–2 frames. Nada atrasado.

### 3b. Palavra de destaque sobre o vídeo (rara)
Referência: "SEU PRODUTO" grande, serifa condensada laranja-avermelhada com glow, sobre a imagem da pessoa.
- Serve para a **1 ou 2 palavras mais importantes de uma frase forte**. Máx. **3 por vídeo**, espaçadas por ≥ 15 s. Não coincide com o cartão preto, B-roll ou trecho P&B; se coincidir, descartar.
- **Tipografia**: serifa condensada em **caixa alta** (Bodoni Moda / Playfair Display Condensed / Abril Fatface ou similar), muito maior que a legenda (~150–220 px em 1080p), tracking apertado, cor `#FF4A1C` com glow (`text-shadow: 0 0 18px rgba(255,74,28,.55)`), opacidade 100%.
- **Posição**: no espaço livre lateral ou sobre o peito/ombro, com o mesmo cálculo de posição livre da legenda (nunca cobre olhos e boca; pode sobrepor parcialmente o corpo, como na referência, mas não o rosto). Sorteada com a mesma semente e a mesma regra anti-padrão (varia de lado).
- **Tempo**: aparece **no frame em que a palavra é falada** e sai no fim da palavra (ou até 1.2 s depois, no máximo). Corte seco, sem animação. Enquanto está visível, a legenda normal **não repete** essa palavra (mostra só o restante do bloco, ou fica oculta se o bloco inteiro for a palavra).
- Mesma frase pode ter a legenda normal continuando em branco e a palavra de destaque em laranja ao mesmo tempo.

### 4. Frase de destaque em fundo preto (MÁX. 1 POR VÍDEO)
Só usar se houver uma frase realmente impactante/central (tese, virada, gancho, o "print" do vídeo). Se nada merecer, **não use nenhuma**. Nunca mais de uma.
- Corte seco para **fundo preto** (#0B0809 levemente quente, não #000 puro), ocupando 100% do quadro por **1.5–4 s**, **sem imagem da pessoa** (o áudio segue).
- Texto centralizado, **sans negrito minúscula ou serifa condensada**, tamanho grande (~72–110 px), com **glow suave** branco/laranja-quente (`text-shadow: 0 0 6px #fff, 0 0 22px rgba(255,120,60,.7)`), tracking apertado.
- As palavras entram **uma a uma no tempo da fala** (corte, sem movimento). Palavras ainda não ditas podem aparecer borradas/cinza-escuras e nítidas ao serem ditas (blur 8px→0 em 3 frames no máximo; sem escala, sem deslocamento). Se ficar animado demais, use só corte.
- Uma palavra-chave da frase pode ir em **serifa condensada caixa alta na cor laranja-avermelhada (#FF4A1C)** com glow, maior que o resto (como "MEU" / "SEU PRODUTO" na referência), aparecendo em corte.
- Volta ao vídeo por corte, em enquadramento diferente do anterior ao cartão.

### 5. Trechos em preto e branco (dramatização de um trecho da fala)
Usados para dar peso a uma afirmação, virada ou tom de brincadeira/ironia. Frequência: 1–3 por vídeo, 2–6 s cada.
- **Entra junto com um corte de enquadramento**: o P&B começa no mesmo frame em que o enquadramento muda para um mais **fechado OU mais aberto** que o anterior (sempre diferente do que vinha antes).
- **Termina com corte de volta ao enquadramento anterior** ao trecho P&B (o mesmo scale/translate de antes), reforçando a divisão entre o trecho P&B e o resto.
- Dentro do P&B pode haver, no máximo, mais uma troca de enquadramento.
- Tratamento: dessaturação 100%, contraste +12–15%, grão leve, vinheta um pouco mais forte. Sem transição (é corte).
- **Legenda em VERMELHO** durante todo o trecho P&B (`#E5171B`, mantém sombra escura fina para leitura), mesma tipografia e posicionamento do resto. Volta ao branco no corte de saída.
- Nunca combinar P&B com B-roll ou cartão preto no mesmo trecho.

### 6. Outros
- Sem logotipos, barras, emojis, stickers, molduras, ícones animados. Limpo, escuro, cinematográfico.
- SFX e música: só se eu fornecer `public/music.mp3` / `public/sfx/`. Música a -28 dB com ducking sob a voz; SFX só em cartão preto e P&B, muito discretos, opcionais.
- Áudio: normalizar para -14 LUFS.

### 7. CTA final (entra no fim de TODOS os vídeos)
Asset pronto: `public/cta.mp4` (arquivo `PDV_CTA_Comunidade_16x9.mp4`). Características medidas: **1920x1080, 30 fps, 8,0 s, fundo creme claro, texto "COMENTE COMUNIDADE PRA RECEBER O LINK ↓" em preto e verde, áudio totalmente mudo** (−91 dB), com animação de digitação própria no primeiro segundo.
- **É um asset fechado: não editar, não recolorir, não aplicar grade, vinheta, grão, máscara, legenda nem zoom por cima.** A "animação" dele é parte do arquivo e é a única exceção à regra "tudo é corte".
- **Entrada por corte seco**, em tela cheia (`object-fit: cover` já é 16:9 idêntico), no frame seguinte ao fim do vídeo editado. A duração final do vídeo = duração editada + duração do CTA (`calculateMetadata` deve somar as duas).
- **Antes do corte**: a última fala do apresentador termina inteira (nunca cortar a última palavra); depois dela, segurar **0,3–0,5 s** de rosto. Os últimos 3 s antes do CTA sem trecho P&B, sem cartão preto e sem palavra de destaque laranja (rosto limpo, enquadramento fixo). Fade de áudio de 6 frames no fim da fala para não cortar seco na cauda.
- **Áudio durante o CTA**: silêncio (o arquivo é mudo). Se houver `music.mp3`, ela continua e faz fade-out de 1 s dentro do CTA.
- **fps**: a composição roda no fps do bruto (25). O CTA é 30 fps: deixar o Remotion reamostrar via `<OffthreadVideo>` sem alterar o arquivo; verificar visualmente que não há tranco na digitação do texto.
- **Cor**: o arquivo é `yuvj420p` (faixa completa). Renderizar um frame do CTA no vídeo final e compará-lo com o frame original do `cta.mp4` (cor do creme e do verde); se houver diferença visível (creme mais claro/escuro, verde deslavado), corrigir com a conversão de faixa de cor (`-vf scale=in_range=pc:out_range=tv` no pré-processamento) e refazer.
- **Legendas e overlays**: nenhum elemento do vídeo editado aparece durante o CTA (o próprio CTA já contém o texto).
- Configurável em `plan.cta`: `{ path: "cta.mp4", durationMs: 8000 }`. Padrão: o arquivo inteiro. Não encurtar a menos que eu peça.

---

## COMO DECIDIR A EDIÇÃO (etapa `plan`)
Leia a transcrição inteira e, para cada frase, classifique:
1. **Entidade visualizável** → `broll` com `query` específica em inglês (ex.: "Rimowa aluminum suitcase", "Walt Disney 1950s portrait").
2. **Frase-tese / gancho / virada** → candidata a destaque preto (escolha **uma no máximo**, a melhor) ou a troca de enquadramento para fechado.
3. **Afirmação forte, ironia, "plot twist"** → candidata a trecho P&B (com troca de enquadramento).
4. **Mudança de assunto / respiração** → troca de enquadramento (aberto ↔ médio ↔ fechado).
5. **Pausas e vícios** → `cuts`.
Ritmo: alguma mudança visual (enquadramento, B-roll, cartão, P&B) a cada **3–6 s**. Primeiros 3 s: já com um enquadramento definido e legenda; um B-roll ou destaque no início só se for natural (gancho).

### Schema `edit-plan.json`
```ts
type Plan = {
  config: { seed: number; captionWeights?: { chest: number; side: number; loose: number }; captionReveal: "cut" | "dim-ahead"; brollTarget: [number, number] };
  cuts: { fromMs: number; toMs: number }[];
  cta: { path: string; durationMs: number };              // sempre presente, ao final
  framings: { fromMs: number; toMs: number; shot: "wide" | "medium" | "close" }[]; // troca = corte seco
  broll: { startMs: number; endMs: number; source: { type: "image" | "video"; query?: string; path?: string }; treatment?: "none" | "bw"; reason: string }[];
  bw: { fromMs: number; toMs: number }[];                 // legenda vermelha nesses trechos
  blackCard: null | {                                     // máx. 1
    startMs: number; endMs: number; text: string;
    keyword?: { word: string; style: "serif-orange" };
    reveal: "word-by-word" | "cut";
  };
  emphasis: { startMs: number; endMs: number; text: string; pos: { x: number; y: number; align: "left" | "center" | "right" } }[]; // máx. 3
  captions: { startMs: number; endMs: number; words: { text: string; startMs: number }[];
              pos: { x: number; y: number; align: "left" | "center" | "right"; region: "chest" | "side-l" | "side-r" | "loose" }; variant?: "default" | "spaced" | "serif" }[];
};
```
Validações automáticas (falhar o `plan` se quebrar): `cta` existe e é o último item da timeline; nenhum elemento (legenda, destaque, P&B, cartão preto) cruza o início do `cta`; a última palavra da transcrição fica inteira antes do `cta`; `blackCard` ≤ 1; `emphasis` ≤ 3, espaçados ≥ 15 s, nunca dentro de `bw`, `broll` ou `blackCard`; nenhum `framings` consecutivo igual; todo `bw` começa/termina em fronteira de `framings`; enquadramento pós-`bw` = enquadramento pré-`bw`; nenhum B-roll < 0.8 s; nenhuma legenda invade `faceZone`; **anti-padrão de posição**: rejeitar e re-sortear se as últimas 6 regiões tiverem período 2 ou 3, se a mesma região aparecer > 4 vezes seguidas, ou se a distribuição final de regiões ficar fora de ±15 pontos dos pesos.

## ASSETS
- Ordem: (1) `public/assets-library/` (meus arquivos), (2) Pexels/Pixabay/Unsplash (chaves em `.env`), (3) Wikimedia Commons para fotos históricas/pessoas públicas.
- Baixar ≥ 1920 px no lado maior; converter clipes para H.264 30 fps.
- Registrar origem e licença em `assets/credits.json`. **Não invente** asset: se não achar, deixe placeholder com a `query` na tela e liste no relatório. Sinalizar imagens sem licença clara (fotos de arquivo de terceiros, cenas de filmes/séries, marcas).

## ESTRUTURA
```
src/
  Root.tsx  Edit.tsx
  layers/ TalkingHead.tsx  BRoll.tsx  Captions.tsx  BlackCard.tsx  BwGrade.tsx
  lib/ shots.ts (wide/medium/close → scale/translate estáticos)  timing.ts (ms→frames, cuts)  safeZones.ts
scripts/ transcribe.ts  framing.ts  plan.ts  fetch-assets.ts
edit-plan.example.json
```
`<Sequence premountFor={30}>` em todo B-roll. Cada mudança visual é uma `Sequence` própria (corte), nunca uma interpolação.

## CRITÉRIOS DE ACEITE
- [ ] CTA de 8 s presente ao final, sem alteração, entrando por corte, com cor idêntica ao original e sem tranco; nenhuma legenda/overlay sobre ele; duração total = editado + 8 s.
- [ ] Etiqueta de nome da videochamada invisível em todos os frames; grade de cor aplicado; sem tremor de rosto; troca de participante tratada como troca de câmera.
- [ ] Nenhum `spring`, nenhum scale/translate/opacity animado, exceto o fade ≤3 frames do cartão preto e o blur-reveal opcional.
- [ ] Trocas de enquadramento são cortes de 1 frame; nunca zoom animado.
- [ ] B-rolls todos em tela cheia; nenhum split.
- [ ] No máximo 1 cartão preto (pode ser 0) e no máximo 3 palavras de destaque laranja sobre o vídeo, sem cobrir o rosto.
- [ ] Todo trecho P&B: entra e sai em corte de enquadramento, volta ao enquadramento anterior, legenda vermelha.
- [ ] Posição das legendas irregular: sem ciclo perceptível, sem zigue-zague, corridas de tamanho variado, reposiciona em trocas de enquadramento; nunca cobre olhos/boca; sincronia ±2 frames. Reportar no relatório o histograma de regiões e as corridas.
- [ ] Verificação do rosto aprovada por mim (imagens em `verify/`) e teste de colisão texto×rosto passando em todos os frames.
- [ ] `npx remotion still` de 8 frames espalhados: mostra aberto/médio/fechado, B-roll, P&B com legenda vermelha, e cartão preto (se houver).
- [ ] Relatório final: lista de B-rolls (tempo, query, fonte, licença), placeholders pendentes, decisão sobre o cartão preto (qual frase e por quê, ou por que nenhuma).

## PRIMEIRO PASSO
Não faça tudo de uma vez. Ordem: (1) scaffold + `TalkingHead` com 3 enquadramentos por corte, (2) `Captions` com posicionamento sorteado + validador anti-padrão, (3) transcrição real, (4) `BRoll` tela cheia, (5) P&B + legenda vermelha, (6) palavra de destaque sobre o vídeo e cartão preto, (7) `plan` automático, (8) polimento. Após cada etapa, renderize 10 s e me mostre. Comece confirmando que `public/input.mp4` existe.
