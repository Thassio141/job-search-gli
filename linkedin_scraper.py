#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper de vagas do LinkedIn (público), com prevenção/fechamento do modal de login,
controle de banner de cookies e scroll para lazy-load da lista de resultados.
"""

import json
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlencode, quote_plus

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class LinkedInScraper:
    BASE = "https://br.linkedin.com"
    SEARCH_PATH = "/jobs/search"

    def __init__(
        self,
        chromedriver_path: str = r'C:\\Users\\thass\\Downloads\\chromedriver-win64\\chromedriver.exe',
        headless: bool = False,
        user_agent: Optional[str] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    ):
        self.chromedriver_path = chromedriver_path
        self.headless = headless
        self.user_agent = user_agent
        self.driver: Optional[webdriver.Chrome] = None

    def _setup_driver(self) -> webdriver.Chrome:
        opts = Options()
        if self.headless:
            opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--window-size=1366,900')
        opts.add_argument('--lang=pt-BR')
        opts.add_argument('--accept-lang=pt-BR,pt;q=0.9,en;q=0.8')
        if self.user_agent:
            opts.add_argument(f'--user-agent={self.user_agent}')

        service = Service(self.chromedriver_path)
        driver = webdriver.Chrome(service=service, options=opts)
        driver.implicitly_wait(8)
        return driver

    def _dismiss_login_overlays(self, quick_timeout: float = 0.2, attempts: int = 20):
        """
        Fecha agressivamente modais e banners (incluindo cookies).
        - Só clica em **botões** (NÃO em <a>) para evitar navegação para /legal/*
        - Força CSS para esconder overlays
        - Mantém um MutationObserver para remover novos modais
        """
        kill_js = """
        (function(){
          try {
            // 1) Botões de fechar (X)
            const closeSel = [
              'button[aria-label="Fechar"]',
              'button[aria-label="Close"]',
              '.contextual-sign-in-modal__modal-dismiss',
              '.sign-in-modal__dismiss',
              '.modal__dismiss',
              'button[data-tracking-control-name*="dismiss"]'
            ].join(',');
            document.querySelectorAll(closeSel).forEach(b=>{ try{ if (b.offsetParent!==null) b.click(); }catch(e){} });

            // 2) Aceitar cookies: apenas <button> (nunca <a>)
            Array.from(document.querySelectorAll('button')).forEach(btn=>{
              try{
                const t = ((btn.innerText||btn.textContent||'') + ' ' + (btn.getAttribute('aria-label')||'')).toLowerCase();
                if (/(aceitar|aceito|accept|agree|allow all|permitir|ok)/.test(t) && btn.offsetParent!==null) {
                  btn.click();
                }
              }catch(e){}
            });

            // 3) Remover/ocultar estruturas de modal e backdrop
            const nukeSel = [
              'section[aria-modal="true"][role="dialog"]',
              '.modal__overlay','.modal__wrapper','.artdeco-modal',
              '.sign-in-modal','.contextual-sign-in-modal__screen',
              '#artdeco-global-alert-container' // contêiner comum de banners
            ];
            nukeSel.forEach(s => document.querySelectorAll(s).forEach(n => { try{ n.style.display='none'; n.remove?.(); }catch(e){} }));

            // 4) Não clique em links de políticas; em vez disso, neutralize-os
            document.querySelectorAll('a[href*="/legal/"]').forEach(a=>{
              try { a.setAttribute('data-li-neutralized','1'); a.addEventListener('click', e=>e.preventDefault(), {capture:true, once:true}); } catch(e){}
            });

            // 5) Garantir scroll
            document.documentElement.style.overflow = 'auto';
            document.body.style.overflow = 'auto';

            // 6) CSS anti-modal persistente
            if (!window.__liKillerStyle) {
              const st = document.createElement('style');
              st.id = '__liKillerStyle';
              st.textContent = `
                [role="dialog"], .modal__overlay, .modal__wrapper, .artdeco-modal,
                .sign-in-modal, .contextual-sign-in-modal__screen,
                #artdeco-global-alert-container { display:none !important; pointer-events:none !important; }
                html,body{ overflow:auto !important; }
              `;
              document.head.appendChild(st);
              window.__liKillerStyle = st;
            }

            // 7) Observer para apagar modais futuros
            if (!window.__liModalKiller) {
              const sel = '[role="dialog"],.modal__overlay,.modal__wrapper,.artdeco-modal,.sign-in-modal,.contextual-sign-in-modal__screen,#artdeco-global-alert-container';
              window.__liModalKiller = new MutationObserver(ms=>{
                for (const m of ms) for (const n of m.addedNodes) {
                  try {
                    if (n.nodeType===1 && (n.matches?.(sel) || n.querySelector?.(sel))) { n.remove(); }
                  } catch(e){}
                }
              });
              window.__liModalKiller.observe(document.documentElement,{childList:true,subtree:true});
            }
          } catch(e){}
        })();
        """
        for _ in range(attempts):
            try:
                self.driver.execute_script(kill_js)
            except Exception:
                pass
            try:
                self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            except Exception:
                pass
            time.sleep(quick_timeout)

    def _ensure_not_on_legal(self, safe_url: str):
        """Se caiu em /legal/*, volta para a URL de busca."""
        try:
            cur = self.driver.current_url
            if '/legal/' in cur or 'consent.linkedin.com' in cur:
                self.driver.get(safe_url)
        except Exception:
            try:
                self.driver.get(safe_url)
            except Exception:
                pass

    def _wait_for_results_list(self, timeout: int = 15) -> Optional[webdriver.remote.webelement.WebElement]:
        try:
            ul = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.jobs-search__results-list'))
            )
            WebDriverWait(self.driver, timeout).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, 'ul.jobs-search__results-list > li')) > 0
            )
            return ul
        except TimeoutException:
            return None

    def _progressive_scroll_results(self, max_scrolls: int = 20, pause: float = 0.4) -> int:
        last_count = 0
        stable_loops = 0
        for i in range(max_scrolls):
            try:
                self.driver.execute_script("window.scrollBy(0, Math.max(500, window.innerHeight*0.9));")
            except Exception:
                pass

            self._dismiss_login_overlays(quick_timeout=0.05, attempts=2)
            time.sleep(pause)

            try:
                count = len(self.driver.find_elements(By.CSS_SELECTOR, 'ul.jobs-search__results-list > li'))
            except Exception:
                count = 0

            print(f"   • scroll {i+1}/{max_scrolls} -> {count} cards")

            if count <= last_count:
                stable_loops += 1
            else:
                stable_loops = 0
                last_count = count

            if stable_loops >= 2:
                break

        return last_count

    @staticmethod
    def _ensure_quoted(keyword: str) -> str:
        kw = keyword.strip()
        if (kw.startswith('"') and kw.endswith('"')):
            return kw
        return f'"{kw}"'

    def _build_search_url(self, keyword: str, location: str = "Brasil", start: int = 0) -> str:
        quoted_kw = self._ensure_quoted(keyword)
        params = {
            "keywords": quoted_kw,
            "location": location,
            "geoId": "106057199",
            "f_TPR": "r86400",  # últimas 24h
            "f_WT": "2",        # remoto
            "position": "1",
            "pageNum": start // 25
        }
        query = urlencode(params, quote_via=quote_plus)
        return f"{self.BASE}{self.SEARCH_PATH}?{query}"

    @staticmethod
    def _parse_relative_time(text: str) -> Optional[datetime]:
        if not text:
            return None
        t = text.lower().strip()
        m = re.search(r'(\d+)\s+minute', t)
        if m:
            return datetime.now() - timedelta(minutes=int(m.group(1)))
        m = re.search(r'(\d+)\s+hour', t)
        if m:
            return datetime.now() - timedelta(hours=int(m.group(1)))
        m = re.search(r'(\d+)\s+day', t)
        if m:
            return datetime.now() - timedelta(days=int(m.group(1)))
        m = re.search(r'há\s+(\d+)\s+min', t)
        if m:
            return datetime.now() - timedelta(minutes=int(m.group(1)))
        m = re.search(r'há\s+(\d+)\s+hora', t)
        if m:
            return datetime.now() - timedelta(hours=int(m.group(1)))
        m = re.search(r'há\s+(\d+)\s+dia', t)
        if m:
            return datetime.now() - timedelta(days=int(m.group(1)))
        return None

    @staticmethod
    def _normalize_contract(title_or_meta: str) -> Optional[str]:
        if not title_or_meta:
            return None
        s = title_or_meta.lower()
        if 'efetivo' in s or 'clt' in s:
            return 'Efetivo'
        if 'tempor' in s:
            return 'Temporário'
        if 'estág' in s or 'estag' in s:
            return 'Estágio'
        if 'aprendiz' in s:
            return 'Aprendiz'
        if re.search(r'\bpj\b|p\.?j\.?', s):
            return 'PJ'
        return None

    @staticmethod
    def _extract_job_info(card_html: str) -> Optional[Dict]:
        soup = BeautifulSoup(card_html, 'html.parser')

        base = soup.select_one('.base-card.base-search-card.job-search-card') or soup

        a_full = base.select_one('a.base-card__full-link[href]') or base.select_one('a[href*="/jobs/view/"]')
        if not a_full:
            return None
        href = a_full.get('href')
        link = href if href.startswith('http') else urljoin("https://br.linkedin.com", href)

        title_el = base.select_one('h3.base-search-card__title')
        nome = title_el.get_text(strip=True) if title_el else (a_full.get_text(strip=True) if a_full else None)

        empresa_el = base.select_one('h4.base-search-card__subtitle a, h4.base-search-card__subtitle')
        empresa = empresa_el.get_text(strip=True) if empresa_el else None

        loc_el = base.select_one('span.job-search-card__location')
        localidade = loc_el.get_text(strip=True) if loc_el else None
        loc_low = (localidade or '').lower()
        remoto = any(k in loc_low for k in ['remoto', 'remote', 'home office'])

        time_el = base.select_one('time.job-search-card__listdate--new') or base.select_one('time')
        data_iso = None
        data_str = None
        if time_el:
            data_str = time_el.get_text(strip=True) or None
            dt_attr = time_el.get('datetime')
            if dt_attr:
                try:
                    data_iso = datetime.fromisoformat(dt_attr).isoformat()
                except Exception:
                    rel = LinkedInScraper._parse_relative_time(data_str or '')
                    data_iso = rel.isoformat() if rel else None
            else:
                rel = LinkedInScraper._parse_relative_time(data_str or '')
                data_iso = rel.isoformat() if rel else None

        footer_text = base.get_text(" ", strip=True)
        promovida = 'promoted' in footer_text.lower()
        easy_apply = 'easy apply' in footer_text.lower() or 'seja um dos primeiros' in footer_text.lower()
        tipo = LinkedInScraper._normalize_contract(f"{nome} {localidade} {footer_text}") or None

        job_id = None
        ent = base.get('data-entity-urn')
        if ent and 'jobPosting:' in ent:
            try:
                job_id = ent.split('jobPosting:')[-1]
            except Exception:
                job_id = None

        return {
            'jobId': job_id,
            'link': link,
            'nome': nome,
            'empresa': empresa,
            'localidade': localidade,
            'remoto': remoto,
            'tipoContrato': tipo,
            'promovida': promovida,
            'easyApply': easy_apply,
            'insights': None,
            'dataPublicacao': data_iso,
            'dataPublicacaoStr': data_str
        }

    def _collect_cards_current_page(self, cutoff_date: datetime) -> List[Dict]:
        results: List[Dict] = []

        cards = []
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, 'ul.jobs-search__results-list > li')
        except Exception:
            cards = []

        if not cards:
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            li_nodes = soup.select('ul.jobs-search__results-list > li')
            print(f"   • fallback page_source -> {len(li_nodes)} cards (soup)")
            for li in li_nodes:
                try:
                    info = self._extract_job_info(str(li))
                    if not info:
                        continue
                    if info.get('dataPublicacao'):
                        try:
                            dt = datetime.fromisoformat(info['dataPublicacao'])
                        except ValueError:
                            dt = None
                        if dt and dt < cutoff_date:
                            continue
                    results.append(info)
                except Exception:
                    continue
            return results

        for card in cards:
            self._dismiss_login_overlays(quick_timeout=0.05, attempts=2)
            try:
                info = self._extract_job_info(card.get_attribute('outerHTML'))
                if not info:
                    continue
                if info.get('dataPublicacao'):
                    try:
                        dt = datetime.fromisoformat(info['dataPublicacao'])
                    except ValueError:
                        dt = None
                    if dt and dt < cutoff_date:
                        continue
                results.append(info)
            except Exception:
                continue

        return results

    def scrape_jobs(self, term: str, location: str = "Brasil", max_pages: int = 5, max_days_old: int = 3) -> List[Dict]:
        self.driver = self._setup_driver()
        results: List[Dict] = []
        try:
            cutoff_date = datetime.now() - timedelta(days=max_days_old)

            for page in range(max_pages):
                start = page * 25
                url = self._build_search_url(term, location=location, start=start)
                print(f"\n🔎 Acessando: {url}")
                self.driver.get(url)

                # mata modal/banner e garante que não caiu em /legal/*
                self._dismiss_login_overlays()
                self._ensure_not_on_legal(url)

                ul = self._wait_for_results_list(timeout=18)
                if not ul:
                    print("⚠️ Não encontrei a lista de resultados nesta página. Próxima…")
                    continue

                total = self._progressive_scroll_results(max_scrolls=24, pause=0.35)
                print(f"✅ Lista visível com {total} cards (após scroll)")

                self._dismiss_login_overlays()
                self._ensure_not_on_legal(url)

                page_jobs = self._collect_cards_current_page(cutoff_date)
                print(f"🧾 Página {page+1}: {len(page_jobs)} vagas válidas coletadas.")
                results.extend(page_jobs)

                if total == 0 and len(page_jobs) == 0:
                    print("🛑 Zero cards coletados; interrompendo paginação para evitar loops.")
                    break

            return results
        finally:
            if self.driver:
                self.driver.quit()


def load_keywords(filename: str = 'keywords.json') -> List[str]:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return ['java']


def deduplicate_jobs(jobs: List[Dict]) -> List[Dict]:
    seen, out = set(), []
    for job in jobs:
        key = job.get('link') or job.get('jobId')
        if key and key not in seen:
            seen.add(key)
            out.append(job)
    return out


def main():
    keywords = load_keywords('keywords.json')
    print("🚀 LinkedIn: iniciando scraping...")
    all_jobs: List[Dict] = []
    scraper = LinkedInScraper()
    for i, kw in enumerate(keywords, 1):
        qkw = LinkedInScraper._ensure_quoted(kw)
        print(f"\n🔍 ({i}/{len(keywords)}) {qkw}...")
        jobs = scraper.scrape_jobs(term=kw, location='Brasil', max_pages=5, max_days_old=3)
        all_jobs.extend(jobs)
    unique_jobs = deduplicate_jobs(all_jobs)
    with open('vagas_linkedin.json', 'w', encoding='utf-8') as f:
        json.dump(unique_jobs, f, ensure_ascii=False, indent=2)
    print(f"\n✅ LinkedIn: {len(unique_jobs)} vagas únicas salvas em vagas_linkedin.json")


if __name__ == '__main__':
    main()
