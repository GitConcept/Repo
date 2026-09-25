"""Robô de navegador que cria a aula na Área de Membros da Hotmart e envia o vídeo.

ATENÇÃO: a Hotmart não tem API para isso, então o robô imita cliques na tela.
Os textos/seletores abaixo foram escritos com base na interface padrão e
PRECISAM ser conferidos na primeira execução (veja README, "Calibração").
Se a Hotmart mudar a tela, ajuste apenas as constantes deste arquivo.
"""
import os
import re

from playwright.sync_api import Page, sync_playwright

LOGIN_URL = "https://sso.hotmart.com/login"
DEBUG_DIR = "debug"

# --- Textos da interface (ajuste aqui se a Hotmart mudar) -------------------
MODULE_NAME = os.environ.get("HOTMART_MODULE_NAME", "LIVES SEMANAIS")
TXT_MODULE_CARD = "Mostrar turmas"            # texto presente em cada cartão de módulo
TXT_MENU_AULA = "Aula"                        # opção do menu do botão "+"
TXT_TITLE_PLACEHOLDER = re.compile(r"Digite o t[íi]tulo", re.I)
TXT_SELECT_FILE = re.compile(r"Selecionar arquivo", re.I)
TXT_PUBLISH = "Publicar"
PAUSE_MINUTES = 30
TXT_DROPZONE = re.compile(r"Arraste ou solte sua m[íi]dia", re.I)
TXT_SEND_FROM_PC = re.compile(r"Enviar do computador", re.I)
TXT_ADD_MEDIA = re.compile(r"^\s*Adicionar m[íi]dia\s*$", re.I)
TXT_PLAYER_PROMO = re.compile(r"Player de v[íi]deo da Hotmart", re.I)
TXT_MEDIA_EMPTY = re.compile(r"^\s*0\s*/\s*3\s*$")
# Enquanto o vídeo sobe/processa, a aula mostra "Carregando" e depois "Otimizando".
TXT_PROGRESS = re.compile(r"\bCarregando\b|\bOtimizando\b|\bEnviando\b|\d{1,3}\s?%", re.I)
UPLOAD_TIMEOUT_MS = 3 * 60 * 60 * 1000  # até 3h para vídeos grandes
# ---------------------------------------------------------------------------


def _shot(page: Page, name: str):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    page.screenshot(path=f"{DEBUG_DIR}/{name}.png", full_page=True)


TXT_CAPTCHA = re.compile(r"confirmar que voc[êe] [ée] humano", re.I)
PROFILE_DIR = os.path.expanduser(os.environ.get("HOTMART_PROFILE_DIR", "~/.automacao-lives/perfil-hotmart"))
LOGIN_WAIT_MS = 60 * 60 * 1000  # espera até 1h por você entrar na Hotmart


def _dismiss_cookie_banner(page: Page):
    """Fecha o aviso "Este site utiliza cookies" (botão OK), que cobre os botões da página."""
    banner = page.locator("hotmart-cookie-policy, #hotmart-cookie-policy")
    ok = banner.get_by_role("button", name=re.compile(r"^\s*OK\s*$", re.I))
    try:
        ok.first.click(timeout=5000)
    except Exception:
        pass  # aviso já aceito antes (fica salvo no perfil)


def _needs_human(page: Page) -> bool:
    return "sso.hotmart.com" in page.url or bool(TXT_CAPTCHA.search(page.content()))


def _ensure_logged_in(page: Page, url: str):
    """Se a Hotmart pedir login ou verificação, espera você resolver na janela aberta.

    O robô não preenche login nem verificação: quem entra é você, uma vez. O perfil do
    navegador fica salvo no Mac, então nas próximas execuções a sessão já está aberta.
    """
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    if not _needs_human(page):
        return
    print("A Hotmart pediu login/verificação. Entre na Hotmart na janela do navegador aberta no Mac.")
    _shot(page, "01-precisa-login")
    page.bring_to_front()
    page.wait_for_function(
        """(pattern) => !location.hostname.startsWith('sso.') &&
                        !new RegExp(pattern, 'i').test(document.body.innerText)""",
        arg=TXT_CAPTCHA.pattern,
        timeout=LOGIN_WAIT_MS,
        polling=5000,
    )
    page.goto(url, wait_until="domcontentloaded")
    _shot(page, "01-logado")


def module_urls():
    """URLs da página de conteúdo de cada curso (lista de módulos), uma por linha."""
    raw = os.environ["HOTMART_MODULE_URL"]
    return [u.strip() for u in re.split(r"[\n,]+", raw) if u.strip()]


def _open_new_lesson(page: Page):
    """Clica no "+" do cartão do módulo e escolhe "Aula"."""
    name = page.get_by_text(re.compile(rf"^\s*{re.escape(MODULE_NAME)}\s*$", re.I)).first
    name.scroll_into_view_if_needed()
    # O cartão é o maior bloco em volta do nome que contém um único "Mostrar turmas".
    card = name.locator(
        f"xpath=ancestor::*[count(.//text()[contains(., '{TXT_MODULE_CARD}')]) = 1][last()]"
    )
    # Cada cartão tem o próprio menu escondido com "Aula": usa só o que estiver visível.
    aula = page.locator(f'text="{TXT_MENU_AULA}" >> visible=true')
    # Botões visíveis do cartão (+, ⋮, ...): testa até abrir o menu com "Aula".
    buttons = [b for b in card.get_by_role("button").filter(has_not_text=TXT_MODULE_CARD).all() if b.is_visible()]
    for button in buttons:
        button.click()
        try:
            aula.first.wait_for(state="visible", timeout=3000)
            aula.first.click()
            return
        except Exception:
            page.keyboard.press("Escape")
    raise RuntimeError(f"Não achei o botão '+' do módulo {MODULE_NAME}")


def _close_player_promo(page: Page) -> bool:
    """Fecha (sem ativar) o aviso "Player de vídeo da Hotmart", se estiver aberto."""
    promo = page.get_by_text(TXT_PLAYER_PROMO).first
    if not promo.is_visible():
        return False
    page.keyboard.press("Escape")
    try:
        promo.wait_for(state="hidden", timeout=3000)  # o aviso fecha com animação
    except Exception:
        # Não fechou com Esc: clica no botão de fechar (×) do aviso, nunca no "Ativar".
        page.locator("[data-slot='dialog-close']").first.click(force=True)
        promo.wait_for(state="hidden", timeout=10_000)
    return True


def _choose_file(page: Page, video_path: str):
    """Envia o vídeo pela janela "Selecionar mídia" (Hotmart Player) e adiciona à aula.

    Caminho: Selecionar arquivo → (fecha o aviso do Player, sem ativar) → Enviar do computador
    → escolhe o arquivo → espera o envio → Adicionar mídia.
    """
    page.get_by_role("button", name=TXT_SELECT_FILE).click()
    send = page.get_by_text(TXT_SEND_FROM_PC).first
    for _ in range(2):
        try:
            send.wait_for(state="visible", timeout=10_000)
            break
        except Exception:
            if not _close_player_promo(page):
                raise
            page.get_by_role("button", name=TXT_SELECT_FILE).click()
    _shot(page, "04a-biblioteca")
    send.click()
    # Abre uma área "Arraste ou solte sua mídia" com outro "Selecionar arquivo".
    page.get_by_text(TXT_DROPZONE).first.wait_for(timeout=15_000)
    _shot(page, "04b-area-envio")
    if os.environ.get("PAUSE_AT_UPLOAD", "false").lower() == "true":
        # Modo de observação: para aqui e deixa você fazer o envio à mão na janela aberta.
        print("PAUSADO na área de envio. Faça o envio manualmente na janela do navegador.")
        for i in range(PAUSE_MINUTES * 2):
            page.wait_for_timeout(30_000)
            _shot(page, f"05-manual-{i:03d}")
        raise RuntimeError("Fim do modo de observação (nada foi publicado pelo robô).")
    # Usa o campo de arquivo da área de envio (o último da página; ignora o de imagem).
    inputs = [i for i in page.locator("input[type=file]").all()
              if "image" not in (i.get_attribute("accept") or "") or "video" in (i.get_attribute("accept") or "")]
    if inputs:
        inputs[-1].set_input_files(video_path)
    else:
        with page.expect_file_chooser(timeout=30_000) as fc:
            page.get_by_role("button", name=TXT_SELECT_FILE).last.click()
        fc.value.set_files(video_path)
    # Ao escolher o arquivo, a janela fecha sozinha e o vídeo aparece na aula ("Carregando").
    # Se a janela continuar aberta com "Adicionar mídia", clica nele.
    page.wait_for_timeout(5000)
    add = page.get_by_role("button", name=TXT_ADD_MEDIA)
    if add.count() and add.first.is_visible():
        add.first.wait_for(state="visible")
        page.wait_for_function(
            "(re) => [...document.querySelectorAll('button')].some(b => new RegExp(re,'i').test(b.innerText) && !b.disabled)",
            arg=TXT_ADD_MEDIA.pattern, timeout=UPLOAD_TIMEOUT_MS, polling=5000,
        )
        add.first.click()
    _shot(page, "04c-enviando")


def _publish_in_module(page: Page, module_url: str, video_path: str, lesson_title: str, dry_run: bool, tag: str):
    page.goto(module_url, wait_until="domcontentloaded")
    _dismiss_cookie_banner(page)
    page.get_by_text(re.compile(rf"^\s*{re.escape(MODULE_NAME)}\s*$", re.I)).first.wait_for(timeout=60_000)
    _shot(page, f"{tag}-02-curso")

    _open_new_lesson(page)
    page.get_by_placeholder(TXT_TITLE_PLACEHOLDER).fill(lesson_title)
    _shot(page, f"{tag}-03-titulo")

    # O formulário tem dois campos de arquivo (miniatura e mídia): usa o que aceita vídeo.
    video_input = page.locator("input[type=file][accept*='video'], input[type=file][accept*='mp4'], input[type=file][accept*='.mov']")
    if video_input.count():
        video_input.first.set_input_files(video_path)
    else:
        _choose_file(page, video_path)
    # Confirma que o envio começou: o contador de mídias sai de "0/3".
    page.get_by_text(TXT_MEDIA_EMPTY).wait_for(state="hidden", timeout=120_000)
    page.wait_for_timeout(5000)
    _shot(page, f"{tag}-04-enviando")

    # Espera o envio terminar: botão Publicar habilitado e sem indicador de progresso.
    publish = page.get_by_role("button", name=TXT_PUBLISH, exact=True)
    page.wait_for_function(
        """([label, pattern]) => {
            const re = new RegExp(pattern, 'i');
            const btn = [...document.querySelectorAll('button')].find(b => b.innerText.trim() === label);
            return btn && !btn.disabled && !re.test(document.body.innerText);
        }""",
        arg=[TXT_PUBLISH, TXT_PROGRESS.pattern],
        timeout=UPLOAD_TIMEOUT_MS,
        polling=5000,
    )
    _shot(page, f"{tag}-05-pronto")

    if dry_run:
        print(f"DRY_RUN ({tag}): parei antes de publicar.")
        return
    publish.click()
    page.wait_for_timeout(10_000)
    _shot(page, f"{tag}-06-publicado")


def publish_lesson(video_path: str, lesson_title: str, targets, dry_run: bool = False, on_done=None):
    """Publica a aula em cada módulo de `targets` [(chave, url)], chamando on_done(chave) após cada sucesso."""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    with sync_playwright() as p:
        # Navegador visível com perfil próprio salvo no Mac (como um Chrome separado só do robô).
        ctx = p.chromium.launch_persistent_context(
            PROFILE_DIR, headless=False, locale="pt-BR", viewport={"width": 1440, "height": 900}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            _ensure_logged_in(page, targets[0][1])
            for i, (key, url) in enumerate(targets, start=1):
                _publish_in_module(page, url, video_path, lesson_title, dry_run, tag=f"curso{i}")
                if on_done and not dry_run:
                    on_done(key)
        except Exception:
            _shot(page, "99-erro")
            raise
        finally:
            ctx.close()
