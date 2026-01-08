import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, set_key

load_dotenv()

class registrar_usuario(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    # Função para salvar valores no arquivo .env
    def salvar_no_env(self, chave, valor):
        set_key(".env", chave, str(valor))

    class Registrar_Usurario_Modal(discord.ui.Modal):
        def __init__(self, bot: commands.Bot):
            super().__init__(title="Registro")
            self.bot = bot
            
            # Campo 1: Nome completo
            self.nome_completo = discord.ui.TextInput(
                label="Nome Completo",
                style=discord.TextStyle.short,
                required=True,
                min_length=3,
                max_length=64
            )
            self.add_item(self.nome_completo)
    class Registrar_Usurario_View(discord.ui.View):
        def __init__(self, bot: commands.Bot, *, timeout: float = None):
            super().__init__(timeout=timeout)
            self.bot = bot

        @discord.ui.button(label="Registrar-se", style=discord.ButtonStyle.primary, custom_id="registrar_se_button")
        async def registrar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            modal = registrar_usuario.Registrar_Usurario_Modal(self.bot)
            await interaction.response.send_modal(modal)

    @discord.app_commands.command(name="set-registro-formulario", description="Define o canal para o menu de registro e envia o menu no canal.")
    async def set_registro_formulario(self, interaction: discord.Interaction):
        # Verifica se o usuário possui o cargo de administrador definido em .env
        admin_cargo_id = os.getenv("ADMINISTRADOR_CARGO_ID")
        if not admin_cargo_id:
            await interaction.response.send_message(
                "❌ O cargo administrador não está configurado corretamente.",
                ephemeral=True
            )
            return

        try:
            admin_cargo_id = int(admin_cargo_id)
        except ValueError:
            await interaction.response.send_message("❌ O cargo administrador não está configurado corretamente.", ephemeral=True)
            return
        
        member = interaction.user
        if not isinstance(member, discord.Member):
            member = interaction.guild.get_member(member.id)
        if not member:
            await interaction.response.send_message(
                "❌ Não foi possível verificar suas permissões no servidor.",
                ephemeral=True
            )
            return

        if not any(role.id == admin_cargo_id for role in member.roles):
            await interaction.response.send_message(
                "Você não tem permissão para usar este comando.", ephemeral=True
            )
            return

        canal_id = interaction.channel.id
        # Salva o ID do canal específico de registro na variável REGISTRAR_CHANNEL_ID
        self.salvar_no_env("REGISTRAR_CHANNEL_ID", canal_id)

        await interaction.response.send_message(f"O canal {interaction.channel.mention} foi definido para o menu de formulário.", ephemeral=True)

        embed = discord.Embed(
            title="Registre-se para ter acesso ao nosso servidor!",
            description=(
                "Seja muito bem-vindo(a)!\n Para começar, clique em Registrar-se abaixo e preencha o formulário.\n\n"
                "❓ **Após submeter o seu formulario, ele passara por uma analise e se aprovado, você terá acesso ao nosso servidor.**\n\n" 
                "📌 **Regras importantes para o preenchimento:**\n"

            ),
            color=discord.Color.from_rgb(255, 110, 0)
        )

        await interaction.channel.send(embed=embed, view=self.Registrar_Usurario_View(self.bot))

    async def registrar_view(self):
        # registra view persistente quando o bot estiver pronto
        await self.bot.wait_until_ready()
        self.bot.add_view(self.Registrar_Usurario_View(self.bot))


async def setup(bot: commands.Bot):
    cog = registrar_usuario(bot)
    await bot.add_cog(cog)
    # Inicia a tarefa que registra a view persistente (opcional)
    bot.loop.create_task(cog.registrar_view())