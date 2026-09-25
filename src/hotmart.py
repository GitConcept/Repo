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
TXT_ADD_CONTENT = re.compile(r"(Adicionar|Nova) (aula|conteúdo|página)", re.I)
TXT_TITLE_LABEL = re.compile(r"(Título|Nome)", re.I)
TXT_UPLOAD_VIDEO = re.compile(r"(Enviar|Adicionar|Upload).*(vídeo|video|mídia)", re.I)
TXT_UPLOAD_DONE = re.compile(r"(processando|enviado|concluído|100%)", re.I)
TXT_PUBLISH = re.compile(r"^(Publicar|Salvar)", re.I)
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
    """URLs de edição dos módulos de destino, uma por linha (um módulo por curso)."""
    raw = os.environ["HOTMART_MODULE_URL"]
    return [u.strip() for u in re.split(r"[\n,]+", raw) if u.strip()]


def _publish_in_module(page: Page, module_url: str, video_path: str, lesson_title: str, dry_run: bool, tag: str):
    page.goto(module_url)
    page.wait_for_load_state("networkidle")
    _shot(page, f"{tag}-02-modulo")

    page.get_by_role("button", name=TXT_ADD_CONTENT).first.click()
    page.get_by_label(TXT_TITLE_LABEL).first.fill(lesson_title)
    _shot(page, f"{tag}-03-titulo")

    with page.expect_file_chooser() as fc:
        page.get_by_text(TXT_UPLOAD_VIDEO).first.click()
    fc.value.set_files(video_path)
    page.get_by_text(TXT_UPLOAD_DONE).first.wait_for(timeout=UPLOAD_TIMEOUT_MS)
    _shot(page, f"{tag}-04-upload")

    if dry_run:
        print(f"DRY_RUN ({tag}): parei antes de publicar.")
        return
    page.get_by_role("button", name=TXT_PUBLISH).first.click()
    page.wait_for_load_state("networkidle")
    _shot(page, f"{tag}-05-publicado")


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
