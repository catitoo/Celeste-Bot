import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Variáveis de configuração
TOKEN = os.getenv('DISCORD_TOKEN')
COMMAND_PREFIX = os.getenv('COMMAND_PREFIX')

# Configuração de intents
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.presences = True
intents.message_content = True
intents.typing = True
intents.reactions = True

# Criação do bot
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)