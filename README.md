# Live semanal → Hotmart

A cada 4 horas, no Mac (runner self-hosted do GitHub Actions), o robô procura lives dos últimos
14 dias que ainda não subiram. Se o Mac estiver desligado, a execução espera na fila e roda
quando ele ligar. Para cada live nova, o robô:

1. procura a gravação nova do Google Meet na pasta do Google Drive;
2. baixa o vídeo;
3. abre a Hotmart num navegador visível no Mac (com perfil próprio, que guarda o login) e, em **cada curso configurado**, abre o
   módulo **Lives Semanais**, cria a aula **"LIVE | DIA DD/MM/AAAA"**, envia o vídeo e publica;
4. registra a gravação em `processed.json` para nunca enviar a mesma live duas vezes.

Se algo falhar, o GitHub envia um e-mail avisando, e as capturas de tela de cada etapa
ficam em **Actions → execução → Artifacts → capturas-hotmart**.

## Configuração (uma vez só)

### 1. Google Drive (conta de serviço)
1. Em <https://console.cloud.google.com>, crie um projeto e ative a **Google Drive API**.
2. Em *IAM e administrador → Contas de serviço*, crie uma conta e gere uma **chave JSON**.
3. No Drive, compartilhe a pasta **Meet Recordings** com o e-mail da conta de serviço
   (`...@...iam.gserviceaccount.com`) como **Leitor**.
4. Copie o ID da pasta: é o trecho da URL depois de `/folders/`.

### 2. Autenticador da Hotmart
Na Hotmart, reconfigure a verificação em duas etapas e, na tela do QR code, clique em
**"não consigo ler o código"** para ver a **chave secreta** (texto tipo `JBSWY3DP...`).
Cadastre essa chave no seu app autenticador **e** guarde-a no secret abaixo. Assim o
seu celular e o robô geram o mesmo código.

### 3. Secrets do GitHub
Em *Settings → Secrets and variables → Actions*:

| Tipo | Nome | Valor |
|---|---|---|
| Secret | `GOOGLE_SERVICE_ACCOUNT_JSON` | conteúdo inteiro do arquivo JSON da chave |
| Secret | `DRIVE_FOLDER_ID` | ID da pasta Meet Recordings |
| Secret | `HOTMART_MODULE_URL` | URL da página do curso na Área de Membros que lista os módulos (Produtos → curso → conteúdo). Para publicar em mais de um curso, cole uma URL por linha |
| Variable | `HOTMART_MODULE_NAME` | Nome do módulo, igual aparece na tela. Opcional; padrão `LIVES SEMANAIS` |
| Variable | `START_DATE` | Data (AAAA-MM-DD) da primeira live a publicar; anteriores são ignoradas. Padrão `2026-09-24` |
| Variable | `MEET_NAME_FILTER` | parte do nome da reunião (ex.: `Live Semanal`). Opcional, mas recomendado |

### Login na Hotmart
O robô **não** faz login sozinho nem resolve verificações. Na primeira execução (e quando a
sessão expirar), abre uma janela do navegador no Mac na tela de login e espera até 1 hora
você entrar na Hotmart por ela. O login fica salvo no perfil do robô
(`~/.automacao-lives/perfil-hotmart`) para as próximas execuções.

### 4. Calibração (primeiro teste)
A Hotmart não tem API para criar aulas, então o robô usa a interface web. Os textos dos
botões em `src/hotmart.py` precisam ser conferidos na sua conta:

1. *Actions → Live semanal → Hotmart → Run workflow* com **dry_run** marcado
   (o robô para antes de publicar).
2. Veja as capturas de tela. Se parou em alguma etapa, ajuste a constante
   correspondente no topo de `src/hotmart.py` e rode de novo.
3. Quando passar inteiro, rode sem dry_run (ou espere a próxima sexta).

### Instalar o runner no Mac
1. No Terminal, rode `xcode-select --install` (instala o git; pule se já tiver) e confira que
   `python3 --version` funciona.
2. No GitHub: **Settings → Actions → Runners → New self-hosted runner → macOS** e rode, no
   Terminal, os comandos das seções *Download* e *Configure* (aceite os padrões com Enter).
3. Para iniciar sozinho com o Mac: `./svc.sh install` e depois `./svc.sh start`, na pasta
   `actions-runner`.
4. Em **Ajustes do Sistema → Bateria/Energia**, evite que o Mac entre em repouso quando
   ligado na tomada.

## Limitações
- Se a Hotmart mudar o layout, o robô pode quebrar. Você recebe e-mail de falha;
  basta ajustar os textos em `src/hotmart.py`.
- A Hotmart pode pedir captcha para logins vindos de servidores. Se acontecer,
  a alternativa é rodar num computador seu (runner self-hosted).
- O disco do GitHub Actions comporta vídeos de até ~14 GB.
