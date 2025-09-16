#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para fazer scraping de vagas no portal da Gupy com paginação.
Coleta: link, nome, empresa, remoto (true/false), tipoContrato
Salva os dados em vagas_gupy.json
"""

import json
import re
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


class GupyScraper:
    """Classe para fazer scraping de vagas da Gupy"""
    
    def __init__(self, chromedriver_path: str = r'C:\Users\thass\Downloads\chromedriver-win64\chromedriver.exe'):
        self.chromedriver_path = chromedriver_path
        self.driver = None
        self.base_url = 'https://portal.gupy.io'
    
    def _setup_driver(self, headless: bool = True) -> webdriver.Chrome:
        """Configura e inicializa o Chrome WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--lang=pt-BR')
        chrome_options.add_argument('--accept-lang=pt-BR,pt;q=0.9,en;q=0.8')
        
        if headless:
            chrome_options.add_argument('--headless')
        
        service = Service(self.chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10)
        
        return driver

    @staticmethod
    def _extract_job_info(job_card_html: str, base_url: str) -> Optional[Dict]:
        """Extrai informações de uma vaga a partir do HTML do card"""
        soup = BeautifulSoup(job_card_html, 'html.parser')

        # Link da vaga
        link_element = soup.find('a', {'aria-label': lambda x: x and x.startswith('Ir para vaga')})
        if not link_element:
            return None

        href = link_element.get('href', '')
        if not href:
            return None

        link = href if href.startswith('http') else urljoin(base_url, href)

        # Título da vaga
        title_element = link_element.find('h3')
        nome = title_element.get_text(strip=True) if title_element else None

        # Empresa
        company_element = link_element.find('p')
        empresa = company_element.get_text(strip=True) if company_element else None

        # Detalhes (local/remoto/tipo de contrato)
        detail_spans = link_element.find_all('span')
        detail_texts = [span.get_text(strip=True) for span in detail_spans if span.get_text(strip=True)]

        # Verificar se é remoto
        detail_text_combined = ' '.join(detail_texts).lower()
        remoto = 'remoto' in detail_text_combined or 'home office' in detail_text_combined

        # Extrair tipo de contrato
        tipo_contrato = None
        contract_patterns = [
            r'efetivo',
            r'tempor[aá]rio',
            r'est[aá]gio',
            r'aprendiz',
            r'pj|p\.?j\.?'
        ]

        # Primeiro, tenta encontrar nos detalhes
        for detail in detail_texts:
            for pattern in contract_patterns:
                if re.search(pattern, detail.lower()):
                    tipo_contrato = detail
                    break
            if tipo_contrato:
                break

        # Se não encontrou, tenta no aria-label
        if not tipo_contrato:
            aria_label = link_element.get('aria-label', '')
            match = re.search(r'tipo\s+([^.]+)\.', aria_label, re.IGNORECASE)
            if match:
                tipo_contrato = match.group(1).strip()

        # Normalizar tipo de contrato
        if tipo_contrato:
            tipo_lower = tipo_contrato.lower()
            if 'efetivo' in tipo_lower:
                tipo_contrato = 'Efetivo'
            elif 'tempor' in tipo_lower:
                tipo_contrato = 'Temporário'
            elif 'estág' in tipo_lower or 'estag' in tipo_lower:
                tipo_contrato = 'Estágio'
            elif 'aprendiz' in tipo_lower:
                tipo_contrato = 'Aprendiz'
            elif 'pj' in tipo_lower:
                tipo_contrato = 'PJ'
            else:
                tipo_contrato = tipo_contrato.strip()

        return {
            'link': link,
            'nome': nome,
            'empresa': empresa,
            'remoto': remoto,
            'tipoContrato': tipo_contrato
        }

    def scrape_jobs(self, term: str = 'vagas', remote_only: bool = True, max_pages: int = 10, headless: bool = True) -> List[Dict]:
        """
        Faz scraping de vagas na Gupy com paginação
        
        Args:
            term: termo de busca
            remote_only: se True, aplica filtro remoto
            max_pages: máximo de páginas para percorrer
            headless: se True, roda o browser em modo headless
            
        Returns:
            Lista de dicionários com dados das vagas
        """
        self.driver = self._setup_driver(headless)
        
        try:
            # Monta URL de busca
            search_url = f'{self.base_url}/job-search/term={quote(term)}'
            if remote_only:
                search_url += '&workplaceTypes[]=remote'
            
            print(f"Acessando: {search_url}")
            self.driver.get(search_url)
            
            # Espera inicial - aguarda cards de vaga ou paginação aparecer
            wait = WebDriverWait(self.driver, 10)
            try:
                wait.until(
                    lambda driver: driver.find_elements(By.CSS_SELECTOR, 'a[aria-label^="Ir para vaga"]') or
                                  driver.find_elements(By.CSS_SELECTOR, 'nav[aria-label="pagination navigation"]')
                )
            except TimeoutException:
                print("Timeout aguardando elementos da página")
                return []
            
            all_jobs = []
            current_page = 1
            
            while current_page <= max_pages:
                print(f"Processando página {current_page}...")
                
                # Aguarda um pouco para garantir que a página carregou
                time.sleep(1.2)
                
                # Busca todos os cards de vaga na página atual
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, 'a[aria-label^="Ir para vaga"]')
                
                if not job_cards:
                    print("Nenhuma vaga encontrada nesta página")
                    break
                
                page_jobs = []
                for card in job_cards:
                    try:
                        job_info = self._extract_job_info(card.get_attribute('outerHTML'), self.base_url)
                        if job_info and job_info['link']:
                            page_jobs.append(job_info)
                    except Exception as e:
                        print(f"Erro ao processar card de vaga: {e}")
                        continue
                
                all_jobs.extend(page_jobs)
                print(f"Coletadas {len(page_jobs)} vagas da página {current_page}")
                
                # Tenta ir para a próxima página
                try:
                    next_button = self.driver.find_element(
                        By.CSS_SELECTOR, 
                        'nav[aria-label="pagination navigation"] button[aria-label="Próxima página"]:not([disabled])'
                    )
                    
                    # Clica no botão de próxima página
                    self.driver.execute_script("arguments[0].click();", next_button)
                    
                    # Aguarda um pouco para a página carregar
                    time.sleep(1)
                    
                    current_page += 1
                    
                except NoSuchElementException:
                    print("Botão 'Próxima página' não encontrado ou desabilitado")
                    break
                except Exception as e:
                    print(f"Erro ao navegar para próxima página: {e}")
                    break
            
            print(f"Scraping finalizado! Total de vagas coletadas: {len(all_jobs)}")
            return all_jobs
            
        except Exception as e:
            print(f"Erro durante o scraping: {e}")
            return []
            
        finally:
            if self.driver:
                self.driver.quit()


def load_keywords(filename: str = 'keywords.json') -> List[str]:
    """Carrega lista de keywords do arquivo JSON"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            keywords = json.load(f)
        return keywords if isinstance(keywords, list) else []
    except FileNotFoundError:
        print(f"⚠️ Arquivo {filename} não encontrado. Usando keyword padrão 'vagas'")
        return ['vagas']
    except json.JSONDecodeError as e:
        print(f"⚠️ Erro ao ler {filename}: {e}. Usando keyword padrão 'vagas'")
        return ['vagas']


def deduplicate_jobs(jobs: List[Dict]) -> List[Dict]:
    """Remove vagas duplicadas baseado no link"""
    seen_links = set()
    unique_jobs = []
    
    for job in jobs:
        if job['link'] not in seen_links:
            seen_links.add(job['link'])
            unique_jobs.append(job)
    
    return unique_jobs


def main():
    """Função principal"""
    # Configurações
    remote_only = True      # False para buscar também presencial/híbrido
    max_pages = 5           # Limite de páginas por keyword (reduzido para múltiplas buscas)
    headless = True         # False para ver o browser funcionando
    
    # Carrega keywords do arquivo
    keywords = load_keywords()
    
    print("🔍 Iniciando scraping de vagas da Gupy...")
    print(f"Keywords encontradas: {', '.join(keywords)}")
    print(f"Apenas remotas: {remote_only}")
    print(f"Máximo de páginas por keyword: {max_pages}")
    print("-" * 50)
    
    scraper = GupyScraper()
    all_jobs = []
    
    # Busca por cada keyword
    for i, keyword in enumerate(keywords, 1):
        print(f"\n🔍 Buscando por '{keyword}' ({i}/{len(keywords)})...")
        
        try:
            jobs = scraper.scrape_jobs(
                term=keyword, 
                remote_only=remote_only, 
                max_pages=max_pages, 
                headless=headless
            )
            
            if jobs:
                print(f"✅ Encontradas {len(jobs)} vagas para '{keyword}'")
                all_jobs.extend(jobs)
            else:
                print(f"⚠️ Nenhuma vaga encontrada para '{keyword}'")
                
        except Exception as e:
            print(f"❌ Erro ao buscar '{keyword}': {e}")
            continue
    
    # Remove duplicatas
    print(f"\n🔄 Removendo duplicatas...")
    unique_jobs = deduplicate_jobs(all_jobs)
    duplicates_removed = len(all_jobs) - len(unique_jobs)
    
    if duplicates_removed > 0:
        print(f"✅ Removidas {duplicates_removed} vagas duplicadas")
    
    # Salva o resultado em JSON
    output_file = 'vagas_gupy.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_jobs, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Salvo {len(unique_jobs)} vagas únicas em {output_file}")
    
    # Mostra algumas estatísticas
    if unique_jobs:
        empresas = set(job['empresa'] for job in unique_jobs if job['empresa'])
        remotas = sum(1 for job in unique_jobs if job['remoto'])
        tipos_contrato = set(job['tipoContrato'] for job in unique_jobs if job['tipoContrato'])
        
        print(f"\n📊 Estatísticas Finais:")
        print(f"   • Total de vagas únicas: {len(unique_jobs)}")
        print(f"   • Empresas diferentes: {len(empresas)}")
        print(f"   • Vagas remotas: {remotas}")
        print(f"   • Tipos de contrato encontrados: {', '.join(sorted(tipos_contrato)) if tipos_contrato else 'Nenhum'}")
        
        # Estatísticas por keyword
        print(f"\n📈 Vagas por keyword:")
        for keyword in keywords:
            keyword_jobs = [job for job in unique_jobs if keyword.lower() in job['nome'].lower() or keyword.lower() in job.get('empresa', '').lower()]
            print(f"   • {keyword}: {len(keyword_jobs)} vagas")


if __name__ == "__main__":
    main()
