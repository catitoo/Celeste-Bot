import discord
from discord.ext import commands
import os  # Importa o módulo os para acessar as variáveis de ambiente
from dotenv import load_dotenv  # Importa dotenv para carregar o .env

# Carrega as variáveis do .env
load_dotenv()

class eventos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    # membro entrou
    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        canal_id = int(os.getenv('ENTRADA_CHANNEL_ID'))  # Obtém o ID do canal de entrada do .env
        cargo_id = int(os.getenv('VISITANTE_CARGO_ID'))  # Obtém o ID do cargo de visitante do .env
        canal = guild.get_channel(canal_id)
        cargo = guild.get_role(cargo_id)  # Obtém o cargo pelo ID

        if cargo:  # Verifica se o cargo existe
            try:
                await member.add_roles(cargo)  # Adiciona o cargo ao membro
            except discord.Forbidden:
                print(f"Permissões insuficientes para adicionar o cargo {cargo.name} ao membro {member.name}.")
            except discord.HTTPException as e:
                print(f"Erro ao adicionar o cargo {cargo.name} ao membro {member.name}: {e}")

        if canal:  # Verifica se o canal existe
            membro_entrou = discord.Embed(
                title='**Um novo membro!**',
                description=f'{member.mention} entrou no servidor! \n\nAgora temos **{guild.member_count} membros!**',
                color=discord.Color.from_rgb(0, 255, 0)
            )
            membro_entrou.set_thumbnail(url=member.avatar.url if member.avatar else self.bot.user.avatar.url)
            await canal.send(embed=membro_entrou)

    # membro saiu
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        canal_id = int(os.getenv('SAIDA_CHANNEL_ID'))  # Obtém o ID do canal de saída do .env
        canal = guild.get_channel(canal_id)

        if canal:  # Verifica se o canal existe
            membro_saiu = discord.Embed(
                title='**Um membro saiu!**',
                description=f'{member.mention} saiu do servidor! \n\nAgora temos **{guild.member_count} membros!**',
                color=discord.Color.from_rgb(255, 0, 0)
            )
            membro_saiu.set_thumbnail(url=member.avatar.url if member.avatar else self.bot.user.avatar.url)
            await canal.send(embed=membro_saiu)

async def setup(bot):
    await bot.add_cog(eventos(bot))



