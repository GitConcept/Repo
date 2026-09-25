"""Robô de navegador que cria a aula na Área de Membros da Hotmart e envia o vídeo.

ATENÇÃO: a Hotmart não tem API para isso, então o robô imita cliques na tela.
Os textos/seletores abaixo foram escritos com base na interface padrão e
PRECISAM ser conferidos na primeira execução (veja README, "Calibração").
Se a Hotmart mudar a tela, ajuste apenas as constantes deste arquivo.
"""
import os
import re

import pyotp
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
TXT_PROGRESS = re.compile(r"\d{1,3}\s?%|Enviando|Carregando", re.I)
UPLOAD_TIMEOUT_MS = 3 * 60 * 60 * 1000  # até 3h para vídeos grandes
# ---------------------------------------------------------------------------


def _shot(page: Page, name: str):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    page.screenshot(path=f"{DEBUG_DIR}/{name}.png", full_page=True)


def _login(page: Page, email: str, password: str, totp_secret: str):
    page.goto(LOGIN_URL)
    page.get_by_label(re.compile("e-?mail", re.I)).fill(email)
    page.get_by_label(re.compile("senha|password", re.I)).fill(password)
    page.get_by_role("button", name=re.compile("entrar|login", re.I)).click()

    code_input = page.locator("input[autocomplete='one-time-code'], input[name*='code' i], input[name*='token' i]").first
    code_input.wait_for(timeout=30_000)
    code_input.fill(pyotp.TOTP(totp_secret).now())
    page.get_by_role("button", name=re.compile("verificar|confirmar|entrar|continuar", re.I)).click()
    page.wait_for_url(lambda url: "sso.hotmart.com" not in url, timeout=60_000)
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
    aula = page.get_by_text(TXT_MENU_AULA, exact=True).first
    # O cartão tem alguns botões sem texto (+, ⋮); testa até abrir o menu com "Aula".
    buttons = card.get_by_role("button").filter(has_not_text=TXT_MODULE_CARD)
    for i in range(buttons.count()):
        buttons.nth(i).click()
        try:
            aula.wait_for(timeout=3000)
            aula.click()
            return
        except Exception:
            page.keyboard.press("Escape")
    raise RuntimeError(f"Não achei o botão '+' do módulo {MODULE_NAME}")


def _publish_in_module(page: Page, module_url: str, video_path: str, lesson_title: str, dry_run: bool, tag: str):
    page.goto(module_url)
    page.wait_for_load_state("networkidle")
    _shot(page, f"{tag}-02-curso")

    _open_new_lesson(page)
    page.get_by_placeholder(TXT_TITLE_PLACEHOLDER).fill(lesson_title)
    _shot(page, f"{tag}-03-titulo")

    file_input = page.locator("input[type=file]")
    if file_input.count():
        file_input.first.set_input_files(video_path)
    else:
        with page.expect_file_chooser() as fc:
            page.get_by_role("button", name=TXT_SELECT_FILE).click()
        fc.value.set_files(video_path)
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
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(5000)
    _shot(page, f"{tag}-06-publicado")


def publish_lesson(video_path: str, lesson_title: str, targets, dry_run: bool = False, on_done=None):
    """Publica a aula em cada módulo de `targets` [(chave, url)], chamando on_done(chave) após cada sucesso."""
    email = os.environ["HOTMART_EMAIL"]
    password = os.environ["HOTMART_PASSWORD"]
    totp_secret = os.environ["HOTMART_TOTP_SECRET"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="pt-BR", viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        try:
            _login(page, email, password, totp_secret)
            for i, (key, url) in enumerate(targets, start=1):
                _publish_in_module(page, url, video_path, lesson_title, dry_run, tag=f"curso{i}")
                if on_done and not dry_run:
                    on_done(key)
        except Exception:
            _shot(page, "99-erro")
            raise
        finally:
            browser.close()
