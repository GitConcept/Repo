# Live semanal → Hotmart

Toda sexta de madrugada (depois da live de quinta, que termina às 22h), o GitHub Actions:

1. procura a gravação nova do Google Meet na pasta do Google Drive;
2. baixa o vídeo;
3. entra na Hotmart (com o código do autenticador) e, em **cada curso configurado**, abre o
   módulo **Lives Semanais**, cria a aula **"Live DD/MM/AAAA"**, envia o vídeo e publica;
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
| Secret | `HOTMART_EMAIL` | e-mail de login da Hotmart |
| Secret | `HOTMART_PASSWORD` | senha da Hotmart |
| Secret | `HOTMART_TOTP_SECRET` | chave secreta do autenticador |
| Secret | `HOTMART_MODULE_URL` | URL da tela de edição do módulo Lives Semanais (copie do navegador). Para publicar em mais de um curso, cole uma URL por linha |
| Variable | `MEET_NAME_FILTER` | parte do nome da reunião (ex.: `Live Semanal`). Opcional, mas recomendado |

### 4. Calibração (primeiro teste)
A Hotmart não tem API para criar aulas, então o robô usa a interface web. Os textos dos
botões em `src/hotmart.py` precisam ser conferidos na sua conta:

1. *Actions → Live semanal → Hotmart → Run workflow* com **dry_run** marcado
   (o robô para antes de publicar).
2. Veja as capturas de tela. Se parou em alguma etapa, ajuste a constante
   correspondente no topo de `src/hotmart.py` e rode de novo.
3. Quando passar inteiro, rode sem dry_run (ou espere a próxima sexta).

## Limitações
- Se a Hotmart mudar o layout, o robô pode quebrar. Você recebe e-mail de falha;
  basta ajustar os textos em `src/hotmart.py`.
- A Hotmart pode pedir captcha para logins vindos de servidores. Se acontecer,
  a alternativa é rodar num computador seu (runner self-hosted).
- O disco do GitHub Actions comporta vídeos de até ~14 GB.
