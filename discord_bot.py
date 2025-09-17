#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot do Discord para envio automático de vagas de emprego.
Integra com o sistema de scraping e envia vagas para canal específico.
"""

import json
import os
import asyncio
import schedule
import time
from datetime import datetime
from typing import List, Dict, Set
import discord
from discord.ext import commands, tasks

from main_scraper import MainScraper, load_keywords


class VagasBot(commands.Bot):
    """Bot do Discord para envio de vagas de emprego."""
    
    def __init__(self, config_file: str = 'config.json'):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=None, intents=intents)
        
        # Carrega configurações
        self.config = self.load_config(config_file)
        self.token = self.config['discord']['token']
        self.channel_id = self.config['discord']['channel_id']
        self.headless = self.config['discord']['headless']
        self.interval_hours = self.config['scraping']['interval_hours']
        
        self.sent_jobs_file = 'vagas_enviadas.json'
        self.sent_jobs: Set[str] = set()
        self.load_sent_jobs()
    
    def load_config(self, config_file: str) -> Dict:
        """Carrega configurações do arquivo JSON."""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Arquivo de configuração {config_file} não encontrado")
            print("📝 Criando arquivo de configuração padrão...")
            default_config = {
                "discord": {
                    "token": "SEU_TOKEN_DO_DISCORD_AQUI",
                    "channel_id": 123456789,
                    "headless": True
                },
                "scraping": {
                    "interval_hours": 1,
                    "max_pages_gupy": 5,
                    "max_pages_indeed": 5,
                    "max_scrolls_linkedin": 50,
                    "max_days_old": 3
                },
                "bot": {
                    "send_notifications": True,
                    "max_jobs_per_message": 1
                }
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            return default_config
        except Exception as e:
            print(f"❌ Erro ao carregar configurações: {e}")
            raise
        
    def load_sent_jobs(self):
        """Carrega vagas já enviadas do arquivo."""
        if os.path.exists(self.sent_jobs_file):
            try:
                with open(self.sent_jobs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.sent_jobs = set(data.get('sent_jobs', []))
                print(f"📋 Carregadas {len(self.sent_jobs)} vagas já enviadas")
            except Exception as e:
                print(f"⚠️ Erro ao carregar vagas enviadas: {e}")
                self.sent_jobs = set()
        else:
            self.sent_jobs = set()
    
    def save_sent_jobs(self):
        """Salva vagas enviadas no arquivo."""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'sent_jobs': list(self.sent_jobs)
            }
            with open(self.sent_jobs_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"💾 Salvas {len(self.sent_jobs)} vagas enviadas")
        except Exception as e:
            print(f"❌ Erro ao salvar vagas enviadas: {e}")
    
    def create_job_id(self, job: Dict) -> str:
        """Cria um ID único para a vaga baseado em título, empresa e plataforma."""
        title = job.get('titulo', '').lower().strip()
        company = job.get('empresa', '').lower().strip()
        platform = job.get('plataforma', '').lower().strip()
        return f"{platform}_{company}_{title}".replace(' ', '_')
    
    def format_job_embed(self, job: Dict) -> discord.Embed:
        """Formata uma vaga como embed do Discord."""
        embed = discord.Embed(
            title=f"💼 {job.get('titulo', 'Vaga sem título')}",
            color=0x00ff00 if job.get('plataforma') == 'gupy' else 
                  0x0066cc if job.get('plataforma') == 'indeed' else 0x0077b5,
            timestamp=datetime.now()
        )
        
        # Adiciona campos principais
        if job.get('empresa'):
            embed.add_field(name="🏢 Empresa", value=job['empresa'], inline=True)
        
        if job.get('localizacao'):
            embed.add_field(name="📍 Localização", value=job['localizacao'], inline=True)
        
        if job.get('tipo_contrato'):
            embed.add_field(name="📋 Tipo", value=job['tipo_contrato'], inline=True)
        
        if job.get('salario'):
            embed.add_field(name="💰 Salário", value=job['salario'], inline=True)
        
        if job.get('plataforma'):
            embed.add_field(name="🌐 Plataforma", value=job['plataforma'].upper(), inline=True)
        
        if job.get('data_publicacao'):
            embed.add_field(name="📅 Publicado", value=job['data_publicacao'], inline=True)
        
        # Descrição (limitada)
        if job.get('descricao'):
            desc = job['descricao'][:1000] + "..." if len(job['descricao']) > 1000 else job['descricao']
            embed.add_field(name="📝 Descrição", value=desc, inline=False)
        
        # Link da vaga
        if job.get('link'):
            embed.add_field(name="🔗 Link", value=f"[Ver vaga]({job['link']})", inline=False)
        
        embed.set_footer(text=f"ID: {self.create_job_id(job)}")
        
        return embed
    
    async def send_new_jobs(self):
        """Envia novas vagas para o canal do Discord."""
        try:
            channel = self.get_channel(self.channel_id)
            if not channel:
                print(f"❌ Canal {self.channel_id} não encontrado")
                return
            
            # Verifica se existe arquivo de vagas consolidadas
            if not os.path.exists('vagas_consolidadas.json'):
                print("⚠️ Arquivo vagas_consolidadas.json não encontrado")
                return
            
            # Carrega vagas do arquivo
            with open('vagas_consolidadas.json', 'r', encoding='utf-8') as f:
                all_jobs = json.load(f)
            
            # Filtra apenas vagas novas
            new_jobs = []
            for job in all_jobs:
                job_id = self.create_job_id(job)
                if job_id not in self.sent_jobs:
                    new_jobs.append(job)
                    self.sent_jobs.add(job_id)
            
            if not new_jobs:
                print("ℹ️ Nenhuma vaga nova encontrada")
                return
            
            print(f"📤 Enviando {len(new_jobs)} novas vagas para o Discord...")
            
            # Envia mensagem de início
            await channel.send(f"🚀 **{len(new_jobs)} novas vagas encontradas!**")
            
            # Envia cada vaga como embed
            for i, job in enumerate(new_jobs, 1):
                try:
                    embed = self.format_job_embed(job)
                    await channel.send(embed=embed)
                    
                    # Pequena pausa para evitar rate limiting
                    await asyncio.sleep(1)
                    
                    if i % 10 == 0:
                        print(f"📤 Enviadas {i}/{len(new_jobs)} vagas...")
                        
                except Exception as e:
                    print(f"❌ Erro ao enviar vaga {i}: {e}")
                    continue
            
            # Salva vagas enviadas
            self.save_sent_jobs()
            
            print(f"✅ {len(new_jobs)} vagas enviadas com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro ao enviar vagas: {e}")
    
    async def run_scraper(self):
        """Executa o scraper de vagas."""
        try:
            print("🤖 Iniciando scraping de vagas...")
            
            # Carrega keywords
            keywords = load_keywords('keywords.json')
            if not keywords:
                print("❌ Nenhuma keyword encontrada")
                return
            
            # Executa scraping
            scraper = MainScraper(headless=self.headless)
            scraper.run_all_scrapers(keywords)
            
            print("✅ Scraping concluído!")
            
        except Exception as e:
            print(f"❌ Erro no scraping: {e}")
    
    async def on_ready(self):
        """Evento disparado quando o bot está pronto."""
        print(f"🤖 Bot conectado como {self.user}")
        print(f"📺 Canal alvo: {self.channel_id}")
        print("⏰ Iniciando agendamento...")
        
        # Inicia o loop de agendamento
        self.scheduler_loop.start()
        
        # Executa scraping imediatamente ao iniciar
        print("🚀 Executando scraping inicial...")
        await self.run_scraper()
        await self.send_new_jobs()
        
        print("✅ Scraping inicial concluído! Próxima execução em 1 hora.")
    
    @tasks.loop(seconds=60)
    async def scheduler_loop(self):
        """Loop que verifica o agendamento a cada minuto."""
        schedule.run_pending()
    
    
    async def start_bot(self):
        """Inicia o bot."""
        # Configura o agendamento
        interval = self.interval_hours
        schedule.every(interval).hours.do(lambda: asyncio.create_task(self.run_scraper()))
        schedule.every(interval).hours.do(lambda: asyncio.create_task(self.send_new_jobs()))
        
        print(f"⏰ Agendamento configurado: scraping e envio a cada {interval} hora(s)")
        
        # Inicia o bot
        await self.start(self.token)


async def main():
    """Função principal."""
    print("🤖 Iniciando Bot de Vagas do Discord...")
    print("📋 Certifique-se de configurar o arquivo config.json com seu token e channel_id")
    
    # Cria e inicia o bot
    bot = VagasBot()
    
    try:
        await bot.start_bot()
    except KeyboardInterrupt:
        print("🛑 Bot interrompido pelo usuário")
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
    finally:
        await bot.close()


if __name__ == '__main__':
    asyncio.run(main())
