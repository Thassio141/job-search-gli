# indeed_scraper.py
# -*- coding: utf-8 -*-
import json
import re
import time
import random
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

try:
    # opcional: ajuda a achar o driver automaticamente
    from webdriver_manager.chrome import ChromeDriverManager
    _USE_WDM = True
except Exception:
    _USE_WDM = False


@dataclass
class JobInfo:
    nome: str
    empresa: Optional[str]
    local: Optional[str]
    url: Optional[str]
    resumo: Optional[str]


class IndeedScraper:
    def __init__(
        self,
        chromedriver_path: str = r'C:\\Users\\thass\\Downloads\\chromedriver-win64\\chromedriver.exe',
        headless: bool = True,
        location: str = "Home Office",
        site: str = "https://br.indeed.com",
        days: Optional[int] = 1,  # fromAge em dias; None para não enviar
        page_timeout: int = 15,
    ):
        self.chromedriver_path = chromedriver_path
        self.headless = headless
        self.location = location
        self.site = site.rstrip("/")
        self.days = days
        self.page_timeout = page_timeout
        self.driver: Optional[webdriver.Chrome] = None

    # -------------------------
    # Setup & helpers
    # -------------------------
    def _setup_driver(self) -> webdriver.Chrome:
        opts = ChromeOptions()
        # Estratégia: não esperar recursos pesados
        opts.page_load_strategy = "eager"

        if self.headless:
            opts.add_argument("--headless=new")

        # user-agent "realista"
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        # reduzir fingerprint
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1366,768")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        service = ChromeService(self.chromedriver_path)
        driver = webdriver.Chrome(service=service, options=opts)

        # Pequeno ajuste na flag de automação
        try:
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                      get: () => undefined
                    });
                    """
                },
            )
        except Exception:
            pass

        return driver

    def _maybe_accept_cookies(self):
        """Tenta aceitar o banner de cookies (se existir) para liberar a página."""
        try:
            WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(
                    (
                        By.CSS_SELECTOR,
                        "#onetrust-accept-btn-handler, button#onetrust-accept-btn-handler, button[aria-label*='Aceitar'], button[aria-label*='Accept']",
                    )
                )
            ).click()
            time.sleep(0.3)
        except Exception:
            pass

    def _build_url(self, query: str, start: int) -> str:
        # exemplo base: https://br.indeed.com/jobs?q=java&l=Home%20Office&fromage=1&start=10&sort=date
        q = query.strip().replace(" ", "+")
        l = self.location.strip().replace(" ", "+")
        params = [f"q={q}", f"l={l}", "sc=0kf%3Aattr%28DSQF7%29%3B", "sort=date"]  # DSQF7 = remoto (pode variar)
        if self.days is not None:
            params.append(f"fromage={int(self.days)}")
        params.append(f"start={int(start)}")
        return f"{self.site}/jobs?{'&'.join(params)}"

    # -------------------------
    # Parsing
    # -------------------------
    def _extract_job_info(self, card_html: str) -> Optional[Dict]:
        """
        Extrai informações principais do card:
        - nome (título)
        - empresa
        - local
        - url (absoluta)
        - resumo (trecho)
        """
        try:
            soup = BeautifulSoup(card_html, "html.parser")

            # título & link
            a_title = soup.select_one("a.jcs-JobTitle")
            nome = (a_title.get_text(strip=True) if a_title else None) or ""
            href = a_title.get("href") if a_title else None
            if href and href.startswith("/"):
                url = f"{self.site}{href}"
            else:
                url = href

            # empresa
            empresa_el = soup.select_one('[data-testid="company-name"]')
            empresa = empresa_el.get_text(strip=True) if empresa_el else None

            # local
            local_el = soup.select_one('[data-testid="text-location"]')
            local = local_el.get_text(strip=True) if local_el else None

            # resumo / snippet
            resumo_el = soup.select_one('[data-testid="belowJobSnippet"]')
            if not resumo_el:
                # algumas páginas usam listas <ul> dentro do "sub_item"
                resumo_el = soup.select_one("div.slider_sub_item ul, div.slider_sub_item")
            resumo = resumo_el.get_text(" ", strip=True) if resumo_el else None

            if not nome:
                return None

            return asdict(JobInfo(nome=nome, empresa=empresa, local=local, url=url, resumo=resumo))
        except Exception:
            return None

    # -------------------------
    # Scraping principal
    # -------------------------
    def scrape_jobs(
        self,
        term: str,
        max_pages: int = 5,
        senior_filter: bool = True,
        sleep_between_pages: Optional[tuple] = (0.6, 1.4),
    ) -> List[Dict]:
        self.driver = self._setup_driver()
        wait = WebDriverWait(self.driver, self.page_timeout)
        all_jobs: List[Dict] = []

        try:
            for page in range(max_pages):
                start = page * 10  # indeed pagina em múltiplos de 10
                url = self._build_url(term, start=start)
                print(f"➡️  Carregando página {page+1}/{max_pages}: {url}")
                self.driver.get(url)

                # cookies (se aparecer)
                self._maybe_accept_cookies()

                # aguarde por um seletor estável
                try:
                    wait.until(
                        EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, "a.jcs-JobTitle")
                        )
                    )
                except TimeoutException:
                    print("⏳ Timeout esperando títulos de vagas; seguindo para próxima página…")
                    # Tenta continuar pra próxima página
                    continue

                # aguarde um pouco para o DOM estabilizar
                time.sleep(0.8)

                # colete cards de maneira robusta
                cards = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div.cardOutline.tapItem, div.cardOutline.tapItem.result",
                )

                if not cards:
                    print("🛑 Nenhuma vaga encontrada; encerrando a paginação.")
                    break

                print(f"🔎 Encontrados {len(cards)} cards na página {page+1}.")

                page_jobs: List[Dict] = []
                for idx, card in enumerate(cards, start=1):
                    try:
                        outer_html = card.get_attribute("outerHTML")
                        info = self._extract_job_info(outer_html)
                        if not info:
                            continue

                        # filtro de senioridade usando a chave correta "nome"
                        if senior_filter:
                            nome_lower = (info.get("nome") or "").lower()
                            if re.search(r"\b(senior|sênior|sr)\b", nome_lower):
                                print(f"🚫 (Filtro SR) Ignorando vaga: {info.get('nome', 'N/A')}")
                                continue

                        page_jobs.append(info)
                    except Exception:
                        continue

                print(f"✅ Vagas válidas nesta página: {len(page_jobs)}")
                all_jobs.extend(page_jobs)

                # pausa randômica entre páginas (reduz bloqueios)
                if sleep_between_pages:
                    time.sleep(random.uniform(*sleep_between_pages))

            return all_jobs
        finally:
            if self.driver:
                self.driver.quit()


def load_keywords(filename: str = 'keywords.json') -> List[str]:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return ['vagas']


def deduplicate_jobs(jobs: List[Dict]) -> List[Dict]:
    seen, out = set(), []
    for job in jobs:
        key = job.get('url') or job.get('nome')
        if key and key not in seen:
            seen.add(key)
            out.append(job)
    return out


def main():
    keywords = load_keywords('keywords.json')
    print("🚀 Indeed: iniciando scraping...")
    all_jobs: List[Dict] = []
    scraper = IndeedScraper(headless=True)
    
    for i, kw in enumerate(keywords, 1):
        print(f"\n🔍 ({i}/{len(keywords)}) '{kw}'...")
        jobs = scraper.scrape_jobs(term=kw, max_pages=5)
        all_jobs.extend(jobs)
    
    unique_jobs = deduplicate_jobs(all_jobs)
    with open('vagas_indeed.json', 'w', encoding='utf-8') as f:
        json.dump(unique_jobs, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Indeed: {len(unique_jobs)} vagas únicas salvas em vagas_indeed.json")


if __name__ == '__main__':
    main()
