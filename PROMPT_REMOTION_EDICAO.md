# Prompt: edição horizontal "talking head + B-roll tela cheia + legenda posicionada" (Remotion)

Cole tudo abaixo no Claude Code, dentro de um projeto Remotion (`npx create-video@latest`, template blank, TypeScript).
Referência de estilo: `REFERENCIA_4.mp4` (colocar em `reference/` para consulta; **não** é o vídeo a ser editado).

---

## PAPEL
Você é um editor de vídeo sênior e engenheiro Remotion. Vou fornecer um vídeo bruto horizontal de uma pessoa falando para a câmera. Entregue uma composição Remotion que o transforma em um vídeo editado no estilo abaixo, de forma **automatizada e parametrizável**: transcrição → plano de edição (JSON) → render.

## FILOSOFIA DE EDIÇÃO (leia antes de tudo)
**Seco e direto. Tudo é corte.** Simula a troca de câmera e a montagem de um editor humano, não um template de motion graphics.
- **PROIBIDO**: bounce, overshoot, `spring` com sobra, scale-in/scale-out, pop, slide, whip, glitch, dissolve, wipe, zoom animado, Ken Burns, push-in/pull-out, shake. Nada disso, em nenhum elemento (vídeo, B-roll, texto).
- Toda entrada e saída de elemento visual é **corte de 0 frames** (aparece no frame exato, some no frame exato).
- Única exceção de movimento permitida: **fade de opacidade de no máximo 3 frames** na saída de textos do tipo "cartão preto" (ver 4). Se em dúvida, corte.
- Nenhum elemento usa `spring()`. Use `interpolate` somente para o fade citado e para o revelar de palavra descrito em 3.

## ESPECIFICAÇÕES TÉCNICAS
- Composição **horizontal 1920x1080, 30 fps** (a referência é 1276x718 a ~24 fps; o bruto pode variar: use `calculateMetadata` para ler resolução/fps/duração do arquivo e ajustar; se o bruto for 4K, renderizar em 1920x1080).
- Vídeo bruto em `public/input.mp4` via `<OffthreadVideo>`. Áudio original sempre mantido.
- Stack: Remotion 4.x, TS, `@remotion/captions`, `@remotion/google-fonts`, `@remotion/install-whisper-cpp`.
- Toda a edição é dirigida por **`edit-plan.json`**. Componentes só renderizam o plano; nenhum tempo hard-coded.

## PIPELINE (scripts npm)
1. `npm run transcribe` — extrai áudio (ffmpeg), transcreve com timestamps **por palavra** (Whisper, `pt`, modelo `medium` ou maior) → `public/captions.json`. Revisar a transcrição (nomes próprios, marcas) antes do passo 2.
2. `npm run framing` — detecta o rosto num frame do bruto (MediaPipe/face-api ou me peça as coordenadas) e grava `framing.json`: bbox do rosto, e as **zonas seguras** de texto (`faceZone`, `leftSpace`, `rightSpace`, `chestZone`) para cada enquadramento (ver 1).
3. `npm run plan` — gera `edit-plan.json` a partir da transcrição (ver "Como decidir a edição").
4. `npm run assets` — resolve os B-rolls (ver "Assets").
5. `npm start` (Studio) e `npm run render` (H.264, CRF 18).

---

## O ESTILO

### 1. Talking head: 3 enquadramentos, troca por corte seco
O bruto é UM plano. Simule 3 "câmeras" recortando/escalando o mesmo vídeo com **transform estático** (`scale` + `translate` constantes durante o trecho, sem interpolar):
- **Aberto** — scale 1.00 (enquadramento original, com espaço vazio nas laterais). Padrão.
- **Médio** — scale ~1.15–1.2, centrado no rosto.
- **Fechado** — scale ~1.4–1.5, rosto no terço superior/centro, olhos numa linha estável.
Regras:
- **Nunca há zoom animado.** O scale muda de um valor para outro num único frame (corte).
- Troca de enquadramento a cada **3–8 s**, sempre em pausa de respiração, fim de frase ou palavra de ênfase. Nunca repetir o mesmo enquadramento em dois cortes seguidos; nunca pular de aberto para aberto.
- Manter o enquadramento pelo menos 2 s antes de trocar de novo (exceto dentro de trecho P&B, ver 5).
- Corte de jump (remover pausas > 0.4 s e vícios "é…", "né") deve ser combinado com troca de enquadramento sempre que possível, para o jump cut parecer troca de câmera e não erro. Crossfade de áudio de 2 frames nos cortes.
- Grade de cor leve no bruto (contraste +6–8%, vinheta 8–10%), sem alterar o look que já existe.

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
Validações automáticas (falhar o `plan` se quebrar): `blackCard` ≤ 1; `emphasis` ≤ 3, espaçados ≥ 15 s, nunca dentro de `bw`, `broll` ou `blackCard`; nenhum `framings` consecutivo igual; todo `bw` começa/termina em fronteira de `framings`; enquadramento pós-`bw` = enquadramento pré-`bw`; nenhum B-roll < 0.8 s; nenhuma legenda invade `faceZone`; **anti-padrão de posição**: rejeitar e re-sortear se as últimas 6 regiões tiverem período 2 ou 3, se a mesma região aparecer > 4 vezes seguidas, ou se a distribuição final de regiões ficar fora de ±15 pontos dos pesos.

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
- [ ] Nenhum `spring`, nenhum scale/translate/opacity animado, exceto o fade ≤3 frames do cartão preto e o blur-reveal opcional.
- [ ] Trocas de enquadramento são cortes de 1 frame; nunca zoom animado.
- [ ] B-rolls todos em tela cheia; nenhum split.
- [ ] No máximo 1 cartão preto (pode ser 0) e no máximo 3 palavras de destaque laranja sobre o vídeo, sem cobrir o rosto.
- [ ] Todo trecho P&B: entra e sai em corte de enquadramento, volta ao enquadramento anterior, legenda vermelha.
- [ ] Posição das legendas irregular: sem ciclo perceptível, sem zigue-zague, corridas de tamanho variado, reposiciona em trocas de enquadramento; nunca cobre olhos/boca; sincronia ±2 frames. Reportar no relatório o histograma de regiões e as corridas.
- [ ] `npx remotion still` de 8 frames espalhados: mostra aberto/médio/fechado, B-roll, P&B com legenda vermelha, e cartão preto (se houver).
- [ ] Relatório final: lista de B-rolls (tempo, query, fonte, licença), placeholders pendentes, decisão sobre o cartão preto (qual frase e por quê, ou por que nenhuma).

## PRIMEIRO PASSO
Não faça tudo de uma vez. Ordem: (1) scaffold + `TalkingHead` com 3 enquadramentos por corte, (2) `Captions` com posicionamento sorteado + validador anti-padrão, (3) transcrição real, (4) `BRoll` tela cheia, (5) P&B + legenda vermelha, (6) palavra de destaque sobre o vídeo e cartão preto, (7) `plan` automático, (8) polimento. Após cada etapa, renderize 10 s e me mostre. Comece confirmando que `public/input.mp4` existe.
