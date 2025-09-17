# indeed_scraper.py
# -*- coding: utf-8 -*-
import json
import re
import time
import random
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Callable
from urllib.parse import urlsplit, urlunsplit

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


# -------------------------
# Utilidades de salvamento
# -------------------------
def _atomic_write_json(path: str, data) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # gravação atômica

def _normalize_url(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    # Para URLs do Indeed com jk, manter o parâmetro jk para deduplicação
    if "indeed.com/viewjob" in u and "jk=" in u:
        return u  # Manter URL completa para Indeed
    # Para outras URLs, remover query/fragment para dedup
    parts = urlsplit(u)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

def _deduplicate_jobs(jobs: List[Dict]) -> List[Dict]:
    seen, out = set(), []
    for j in jobs:
        url_norm = _normalize_url(j.get("url"))
        
        # Se a URL é um redirecionamento genérico do Indeed, usar nome+empresa como chave
        if url_norm and "indeed.com/rc/clk" in url_norm:
            key = f"name:{(j.get('nome') or '').strip().lower()}|" \
                  f"{(j.get('empresa') or '').strip().lower()}"
        elif url_norm and "indeed.com/viewjob" in url_norm:
            # Para URLs específicas do Indeed, usar a URL como chave
            key = f"url:{url_norm}"
        elif url_norm:
            key = f"url:{url_norm}"
        else:
            # fallback estável
            key = f"name:{(j.get('nome') or '').strip().lower()}|" \
                  f"{(j.get('empresa') or '').strip().lower()}|" \
                  f"{(j.get('local') or '').strip().lower()}"
        
        if key not in seen:
            seen.add(key)
            # se normalizou URL, reflita no objeto salvo
            if url_norm:
                j = {**j, "url": url_norm}
            out.append(j)
    return out


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
        opts.page_load_strategy = "eager"
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1366,768")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        service = ChromeService(self.chromedriver_path)

        driver = webdriver.Chrome(service=service, options=opts)

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
        try:
            WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(
                    (
                        By.CSS_SELECTOR,
                        "#onetrust-accept-btn-handler, button#onetrust-accept-btn-handler, "
                        "button[aria-label*='Aceitar'], button[aria-label*='Accept']",
                    )
                )
            ).click()
            time.sleep(0.3)
        except Exception:
            pass

    def _build_url(self, query: str, start: int) -> str:
        # exemplo: https://br.indeed.com/jobs?q=java&l=Home%20Office&fromage=1&start=10&sort=date
        q = query.strip().replace(" ", "+")
        l = self.location.strip().replace(" ", "+")
        params = [f"q={q}", f"l={l}", "sort=date"]
        # ⚠️ A flag de remoto no Indeed muda bastante; deixe sem forçar sc=... por robustez.
        if self.days is not None:
            params.append(f"fromage={int(self.days)}")
        params.append(f"start={int(start)}")
        return f"{self.site}/jobs?{'&'.join(params)}"

    # -------------------------
    # Parsing
    # -------------------------
    def _extract_job_info(self, card_html: str) -> Optional[Dict]:
        try:
            soup = BeautifulSoup(card_html, "html.parser")

            a_title = soup.select_one("a.jcs-JobTitle")
            nome = (a_title.get_text(strip=True) if a_title else None) or ""
            
            # Extrair URL correta usando data-jk ou href
            url = None
            if a_title:
                # Primeiro, tentar extrair data-jk para construir URL específica
                data_jk = a_title.get("data-jk")
                if data_jk:
                    url = f"{self.site}/viewjob?jk={data_jk}"
                else:
                    # Fallback para href original
                    href = a_title.get("href")
                    if href:
                        if href.startswith("/"):
                            url = f"{self.site}{href}"
                        else:
                            url = href

            empresa_el = soup.select_one('[data-testid="company-name"]')
            empresa = empresa_el.get_text(strip=True) if empresa_el else None

            local_el = soup.select_one('[data-testid="text-location"]')
            local = local_el.get_text(strip=True) if local_el else None

            resumo_el = soup.select_one('[data-testid="belowJobSnippet"]')
            if not resumo_el:
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
        # NEW: callback de progresso p/ salvar incrementalmente
        progress_callback: Optional[Callable[[List[Dict], Dict], None]] = None,
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

                self._maybe_accept_cookies()

                try:
                    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.jcs-JobTitle")))
                except TimeoutException:
                    print("⏳ Timeout esperando títulos de vagas; seguindo para próxima página…")
                    # checkpoint mesmo assim
                    if progress_callback:
                        progress_callback(all_jobs, {"term": term, "page": page + 1, "url": url})
                    continue

                time.sleep(0.8)

                cards = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div.cardOutline.tapItem, div.cardOutline.tapItem.result",
                )

                if not cards:
                    print("🛑 Nenhuma vaga encontrada; encerrando a paginação.")
                    # checkpoint final desta keyword
                    if progress_callback:
                        progress_callback(all_jobs, {"term": term, "page": page + 1, "url": url})
                    break

                print(f"🔎 Encontrados {len(cards)} cards na página {page+1}.")

                page_jobs: List[Dict] = []
                for idx, card in enumerate(cards, start=1):
                    try:
                        outer_html = card.get_attribute("outerHTML")
                        info = self._extract_job_info(outer_html)
                        if not info:
                            continue

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

                # checkpoint após cada página (removido para evitar problemas)
                # if progress_callback:
                #     progress_callback(all_jobs, {"term": term, "page": page + 1, "url": url})

                if sleep_between_pages:
                    time.sleep(random.uniform(*sleep_between_pages))

            return all_jobs
        finally:
            if self.driver:
                self.driver.quit()


# -------------------------
# Execução
# -------------------------
def load_keywords(filename: str = 'keywords.json') -> List[str]:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return ['vagas']


def main():
    OUTFILE = 'vagas_indeed.json'
    all_jobs: List[Dict] = []
    keywords = load_keywords('keywords.json')
    print("🚀 Indeed: iniciando scraping...")

    def on_progress(current_jobs: List[Dict], ctx: Dict):
        """
        Salva incrementalmente de forma ATÔMICA a cada página/keyword.
        """
        # Usar all_jobs em vez de current_jobs para salvar todas as vagas acumuladas
        uniq = _deduplicate_jobs(all_jobs)
        _atomic_write_json(OUTFILE, uniq)
        print(f"💾 Checkpoint salvo ({len(uniq)} vagas) "
              f"[term='{ctx.get('term')}', page={ctx.get('page')}]")

    scraper = IndeedScraper(headless=True)

    try:
        for i, kw in enumerate(keywords, 1):
            print(f"\n🔍 ({i}/{len(keywords)}) '{kw}'...")
            jobs = scraper.scrape_jobs(
                term=kw,
                max_pages=5,
                senior_filter=True,
                progress_callback=None,  # Não usar callback interno
            )
            all_jobs.extend(jobs)
            print(f"✅ {kw}: {len(jobs)} vagas encontradas, total acumulado: {len(all_jobs)}")
    except KeyboardInterrupt:
        print("\n🛑 Interrompido pelo usuário (Ctrl+C). Salvando progresso...")
    except Exception as e:
        print(f"\n⚠️ Erro inesperado: {e}. Salvando progresso parcial...")
    finally:
        unique_jobs = _deduplicate_jobs(all_jobs)
        _atomic_write_json(OUTFILE, unique_jobs)
        print(f"\n✅ Indeed: {len(unique_jobs)} vagas únicas salvas em {OUTFILE}")


if __name__ == '__main__':
    main()

# --- (Opcional) Se quiser NDJSON incremental (append) ---
# def append_ndjson(path, jobs):
#     with open(path, "a", encoding="utf-8") as f:
#         for j in jobs:
#             f.write(json.dumps(j, ensure_ascii=False) + "\n")
