#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orquestrador principal dos scrapers de vagas.
Executa Gupy → Indeed → LinkedIn em sequência com modo headless.
"""

import json
import time
from datetime import datetime
from typing import List, Dict

from gupy_scraper import GupyScraper, load_keywords, deduplicate_jobs
from indeed_scraper import IndeedScraper
from linkedin_scraper import LinkedInScraper


class MainScraper:
    """Orquestrador principal que executa todos os scrapers em sequência."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.results = {
            'gupy': [],
            'indeed': [],
            'linkedin': []
        }
        self.timestamps = {}
    
    def run_gupy_scraper(self, keywords: List[str]) -> List[Dict]:
        """Executa o scraper da Gupy."""
        print("🚀 Iniciando Gupy Scraper...")
        start_time = datetime.now()
        
        scraper = GupyScraper(headless=self.headless)
        all_jobs = []
        
        for i, keyword in enumerate(keywords, 1):
            print(f"\n🔍 Gupy ({i}/{len(keywords)}): Buscando '{keyword}'...")
            jobs = scraper.scrape_jobs(
                term=keyword,
                remote_only=True,
                max_pages=5,
                max_days_old=3
            )
            print(f"✅ Gupy '{keyword}': {len(jobs)} vagas encontradas")
            all_jobs.extend(jobs)
        
        unique_jobs = deduplicate_jobs(all_jobs)
        self.results['gupy'] = unique_jobs
        self.timestamps['gupy'] = {
            'start': start_time.isoformat(),
            'end': datetime.now().isoformat(),
            'duration': (datetime.now() - start_time).total_seconds()
        }
        
        print(f"✅ Gupy concluído: {len(unique_jobs)} vagas únicas")
        return unique_jobs
    
    def run_indeed_scraper(self, keywords: List[str]) -> List[Dict]:
        """Executa o scraper do Indeed."""
        print("\n🚀 Iniciando Indeed Scraper...")
        start_time = datetime.now()
        
        scraper = IndeedScraper(headless=self.headless)
        all_jobs = []
        
        for i, keyword in enumerate(keywords, 1):
            print(f"\n🔍 Indeed ({i}/{len(keywords)}): Buscando '{keyword}'...")
            jobs = scraper.scrape_jobs(
                term=keyword,
                max_pages=5
            )
            print(f"✅ Indeed '{keyword}': {len(jobs)} vagas encontradas")
            all_jobs.extend(jobs)
        
        unique_jobs = deduplicate_jobs(all_jobs)
        self.results['indeed'] = unique_jobs
        self.timestamps['indeed'] = {
            'start': start_time.isoformat(),
            'end': datetime.now().isoformat(),
            'duration': (datetime.now() - start_time).total_seconds()
        }
        
        print(f"✅ Indeed concluído: {len(unique_jobs)} vagas únicas")
        return unique_jobs
    
    def run_linkedin_scraper(self, keywords: List[str]) -> List[Dict]:
        """Executa o scraper do LinkedIn."""
        print("\n🚀 Iniciando LinkedIn Scraper...")
        start_time = datetime.now()
        
        scraper = LinkedInScraper(headless=self.headless)
        all_jobs = []
        
        for i, keyword in enumerate(keywords, 1):
            print(f"\n🔍 LinkedIn ({i}/{len(keywords)}): Buscando '{keyword}'...")
            jobs = scraper.scrape_jobs(
                term=keyword,
                location='Brasil',
                max_scrolls=50,
                max_days_old=3
            )
            print(f"✅ LinkedIn '{keyword}': {len(jobs)} vagas encontradas")
            all_jobs.extend(jobs)
        
        unique_jobs = deduplicate_jobs(all_jobs)
        self.results['linkedin'] = unique_jobs
        self.timestamps['linkedin'] = {
            'start': start_time.isoformat(),
            'end': datetime.now().isoformat(),
            'duration': (datetime.now() - start_time).total_seconds()
        }
        
        print(f"✅ LinkedIn concluído: {len(unique_jobs)} vagas únicas")
        return unique_jobs
    
    def save_results(self):
        """Salva os resultados de cada plataforma em arquivos separados."""
        print("\n💾 Salvando resultados...")
        
        # Salva resultados individuais
        for platform, jobs in self.results.items():
            filename = f'vagas_{platform}.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, ensure_ascii=False, indent=2)
            print(f"📄 {filename}: {len(jobs)} vagas salvas")
        
        # Salva resultados consolidados
        all_jobs = []
        for jobs in self.results.values():
            all_jobs.extend(jobs)
        
        consolidated_jobs = deduplicate_jobs(all_jobs)
        with open('vagas_consolidadas.json', 'w', encoding='utf-8') as f:
            json.dump(consolidated_jobs, f, ensure_ascii=False, indent=2)
        
        # Salva relatório de execução
        report = {
            'execucao': {
                'data': datetime.now().isoformat(),
                'modo_headless': self.headless,
                'total_vagas': len(consolidated_jobs)
            },
            'timestamps': self.timestamps,
            'resumo_por_plataforma': {
                platform: len(jobs) for platform, jobs in self.results.items()
            }
        }
        
        with open('relatorio_execucao.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"📊 Relatório salvo: relatorio_execucao.json")
        print(f"🔄 Consolidado: vagas_consolidadas.json ({len(consolidated_jobs)} vagas únicas)")
    
    def run_all_scrapers(self, keywords: List[str]):
        """Executa todos os scrapers na sequência: Gupy → Indeed → LinkedIn."""
        print("=" * 60)
        print("🤖 INICIANDO SCRAPING COMPLETO DE VAGAS")
        print("=" * 60)
        print(f"📋 Keywords: {keywords}")
        print(f"👁️ Modo headless: {'Sim' if self.headless else 'Não'}")
        print(f"🕐 Início: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 60)
        
        total_start = datetime.now()
        
        try:
            # Sequência: Gupy → Indeed → LinkedIn
            print("\n🎯 FASE 1: GUPY")
            self.run_gupy_scraper(keywords)
            
            print("\n🎯 FASE 2: INDEED")
            self.run_indeed_scraper(keywords)
            
            print("\n🎯 FASE 3: LINKEDIN")
            self.run_linkedin_scraper(keywords)
            
            # Salva todos os resultados
            self.save_results()
            
            # Relatório final
            total_duration = (datetime.now() - total_start).total_seconds()
            total_jobs = sum(len(jobs) for jobs in self.results.values())
            
            print("\n" + "=" * 60)
            print("✅ SCRAPING CONCLUÍDO COM SUCESSO!")
            print("=" * 60)
            print(f"⏱️ Tempo total: {total_duration:.1f} segundos")
            print(f"📊 Total de vagas coletadas:")
            for platform, jobs in self.results.items():
                print(f"   • {platform.upper()}: {len(jobs)} vagas")
            print(f"🔄 Total consolidado: {len(deduplicate_jobs([job for jobs in self.results.values() for job in jobs]))} vagas únicas")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ ERRO durante a execução: {e}")
            print("💾 Salvando resultados parciais...")
            self.save_results()
            raise


def main():
    """Função principal do orquestrador."""
    # Carrega keywords do arquivo
    keywords = load_keywords('keywords.json')
    
    if not keywords:
        print("❌ Nenhuma keyword encontrada em keywords.json")
        return
    
    # Cria e executa o orquestrador
    scraper = MainScraper(headless=True)  # Modo headless ativado
    scraper.run_all_scrapers(keywords)


if __name__ == '__main__':
    main()
