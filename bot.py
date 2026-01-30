import discord
from config import bot, TOKEN  # Importa do arquivo config.py
import os
import logging

# Silencia logs informativos do discord
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)

async def carregar_cogs():
    for root, dirs, files in os.walk('./cogs'):
        for file in files:
            if file.endswith('.py'):
                path = os.path.relpath(os.path.join(root, file), '.').replace(os.sep, '.')
                await bot.load_extension(path[:-3])

# bot iniciou
@bot.event
async def on_ready():
    print(f'{bot.user} funcionando!')

    try:
        await carregar_cogs()  # Carrega os cogs
        await bot.tree.sync()  # Sincroniza comandos de barra
        print("Todos os comandos foram sincronizados com sucesso!")

    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")

bot.run(TOKEN)