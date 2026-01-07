import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, set_key
load_dotenv()

class GrupoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(emoji="<:Editar_Nome:1437591536463249448>", style=discord.ButtonStyle.secondary, custom_id="grupo_editar_nome")
    async def editar_nome(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Função: Editar Nome.", ephemeral=True)

    @discord.ui.button(emoji="<:Convidar_Jogadores:1437594789800312852>", style=discord.ButtonStyle.secondary, custom_id="grupo_convidar")
    async def convidar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Função: Convidar Jogadores.", ephemeral=True)

    @discord.ui.button(emoji="<:Remover_Membro:1437599768246222958>", style=discord.ButtonStyle.secondary, custom_id="grupo_remover")
    async def remover_membro(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Função: Remover Membro.", ephemeral=True)

    @discord.ui.button(emoji="<:Trocar_Limite_Membro:1437601993404452874>", style=discord.ButtonStyle.secondary, custom_id="grupo_trocar_limite")
    async def trocar_limite(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Função: Trocar Limite de Membros.", ephemeral=True)

    @discord.ui.button(emoji="<:Deletar_Chamada:1437598183449690204>", style=discord.ButtonStyle.secondary, custom_id="grupo_deletar")
    async def deletar_chamada(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Função: Deletar Chamada.", ephemeral=True)

    @discord.ui.button(emoji="<:Bloquear_Chamada:1437593371869708459>", style=discord.ButtonStyle.secondary, custom_id="grupo_bloquear")
    async def bloquear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Função: Bloquear Chamada.", ephemeral=True)

    @discord.ui.button(emoji="<:Liberar_Chamada:1437593661285073006>", style=discord.ButtonStyle.secondary, custom_id="grupo_liberar")
    async def liberar_chamada(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Função: Liberar Chamada.", ephemeral=True)

    @discord.ui.button(emoji="<:Assumir_Lideranca:1437592237763723476>", style=discord.ButtonStyle.secondary, custom_id="grupo_assumir")
    async def assumir_lideranca(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Função: Assumir Liderança.", ephemeral=True)

    @discord.ui.button(emoji="<:Transferir_Lideranca:1437625407972315251>", style=discord.ButtonStyle.secondary, custom_id="grupo_transferir_lideranca")
    async def transferir_lideranca(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Função: Transferir Liderança.", ephemeral=True)

    @discord.ui.button(emoji="<:Trocar_Regiao:1437606614910894120>", style=discord.ButtonStyle.secondary, custom_id="grupo_trocar_regiao")
    async def trocar_regiao(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Função: Trocar Região.", ephemeral=True)

class EditarSalas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def salvar_no_env(self, chave: str, valor):
        set_key(".env", chave, str(valor))

    @discord.app_commands.command(name="set-menu-editar-sala", description="Define o canal e envia a embed com o menu para editar a sala.")
    async def set_menu_editar_sala(self, interaction: discord.Interaction):
        admin_role_id = int(os.getenv('ADMINISTRADOR_CARGO_ID') or 0)
        member = interaction.user
        has_admin_role = False
        if admin_role_id and hasattr(member, "roles"):
            has_admin_role = any(role.id == admin_role_id for role in member.roles)

        if interaction.user.id != interaction.guild.owner_id and not has_admin_role:
            await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)
            return

        canal_id = interaction.channel.id
        self.salvar_no_env("CRIAR_SALA_CHANNEL_ID", canal_id)

        await interaction.response.send_message(
            f"O menu de edição das salas será exibido em {interaction.channel.mention}.",
            ephemeral=True
        )

        embed = discord.Embed(
            title="Painel de Controle da Sala",
            description=(
                "**Gerencie sua chamada de forma rápida e intuitiva!**\n\n"
                "Utilize os botões abaixo para personalizar e controlar todos os aspectos da sua sala.\n\n"
                "Clique nos botões para começar!"
            ),
            color=discord.Color.orange()
        )
        embed.set_image(url="https://i.ibb.co/LDKGwgLY/Imagem-guia-para-editar-os-grupos.png")

        await interaction.channel.send(embed=embed, view=GrupoView())

async def setup(bot: commands.Bot):
    await bot.add_cog(EditarSalas(bot))
    bot.add_view(GrupoView())