#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de inicialização do Bot de Vagas do Discord.
Execute este arquivo para iniciar o bot.
"""

import asyncio
from discord_bot import main

if __name__ == '__main__':
    print("🚀 Iniciando Bot de Vagas do Discord...")
    print("📋 Certifique-se de configurar o arquivo config.json")
    print("🛑 Para parar o bot, pressione Ctrl+C")
    print("-" * 50)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        input("Pressione Enter para sair...")
