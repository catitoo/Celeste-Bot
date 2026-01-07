import discord
from discord.ext import commands
from discord import app_commands
from dotenv import set_key  # Adicione esta importação

class MenuTickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set-menu-tickets", description="Envia o menu dos tickets do chat")
    async def menu_servicos(self, interaction: discord.Interaction):
        # Salva o ID do canal no .env
        set_key(".env", "MENU_TICKETS_CHANNEL_ID", str(interaction.channel.id))

        await interaction.response.send_message(
            f"O menu de tickets será exibido no canal {interaction.channel.mention}.", ephemeral=True
        )
        # Cria a embed
        embed = discord.Embed(
            title="Menu de Serviços",
            description="Selecione o tipo de serviço desejado no menu abaixo.",
            color=discord.Color.blue()
        )
        # Envia a embed no canal público
        await interaction.channel.send(embed=embed, view=OpcoesView(self.bot))

class OpcoesTickets(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="Tirar uma dúvida",
                description="Tirar uma dúvida com a nossa equipe.",
                value="duvida",
                emoji="❓"
            ),
            discord.SelectOption(
                label="Fazer uma Sugestão",
                description="Faça uma sugestão para melhorar o servidor.",
                value="sugestao",
                emoji="💡"
            ),
        ]
        super().__init__(
            placeholder="Selecione um serviço...",
            options=options,
            custom_id="servicos_dropdown",
        )

    async def callback(self, interaction: discord.Interaction):
        servico = self.values[0]
        if servico == "duvida":
            cog = self.bot.get_cog("TicketDuvida")
            if cog:
                await cog.abrir_modal_duvida(interaction)
            else:
                await interaction.response.send_message("ticket de dúvidas não carregado.", ephemeral=True)
            await interaction.message.edit(view=OpcoesView(self.bot))
            return
        elif servico == "sugestao":
            cog = self.bot.get_cog("TicketSugestao")
            if cog:
                await cog.abrir_modal_sugestao(interaction)
            else:
                await interaction.response.send_message("ticket de sugestões não carregado.", ephemeral=True)
            await interaction.message.edit(view=OpcoesView(self.bot))
            return

        # Recria a view para permitir nova seleção
        await interaction.message.edit(view=OpcoesView(self.bot))

class OpcoesView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)  # timeout=None torna a view persistente
        self.add_item(OpcoesTickets(bot))

async def setup(bot):
    await bot.add_cog(MenuTickets(bot))
    # Registra a view globalmente para funcionar após reiniciar o bot
    bot.add_view(OpcoesView(bot))