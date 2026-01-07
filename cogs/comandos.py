import discord
from discord import app_commands
from discord.ext import commands

class comandos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # comando !ping
    @commands.command(name='ping')
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000)
        await ctx.reply(f'**Pong!** - Latência: {latency}ms')

    # comando !sobre
    @commands.command(name='sobre')
    async def sobre(self, ctx):
        sobre = discord.Embed(
            title='**Sobre o nosso Bot.**',
            description=f'Olá, eu sou o **{self.bot.user.name}**, um bot criado para ajudar a todos! :)',
            color=discord.Color.orange()
        )
        sobre.add_field(name='**Comandos disponíveis:**', value='`!ping` - `!sobre`', inline=False)
        sobre.set_footer(text='Bot criado por: Catito')
        await ctx.reply(embed=sobre)

async def setup(bot):
    await bot.add_cog(comandos(bot))



