import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, set_key
load_dotenv()

class GrupoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def _verificar_lider(self, interaction: discord.Interaction):
        member = interaction.user
        if not getattr(member, "voice", None) or not member.voice.channel:
            return None, False, "Você precisa estar em uma sala de voz para usar este botão."

        channel = member.voice.channel

        # Checa categoria e canal de criação
        CATEGORIA_GRUPOS_ID = int(os.getenv('GRUPOS_CRIADOS_CATEGORY_ID') or 0)
        CRIAR_SALA_ID = int(os.getenv('CRIAR_SALA_CHANNEL_ID') or 0)

        if CRIAR_SALA_ID and channel.id == CRIAR_SALA_ID:
            return channel, False, "Este canal não pode ser editado."

        if CATEGORIA_GRUPOS_ID:
            if not getattr(channel, "category", None) or channel.category.id != CATEGORIA_GRUPOS_ID:
                return channel, False, "Este menu só funciona para canais de voz temporarios."

        criar_cog = None
        try:
            criar_cog = interaction.client.get_cog("CriarGrupos")
        except Exception:
            criar_cog = None

        if criar_cog and hasattr(criar_cog, "canais_criados"):
            lider_id = criar_cog.canais_criados.get(channel.id)
            if lider_id == member.id:
                return channel, True, None

        return channel, False, "Apenas o líder da sala pode fazer isso."

    @discord.ui.button(emoji="<:Editar_Nome:1437591536463249448>", style=discord.ButtonStyle.secondary, custom_id="grupo_editar_nome")
    async def editar_nome(self, interaction: discord.Interaction, button: discord.ui.Button):
        import re
        channel, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        CHANNEL_NAME_MAX = 32

        class RenomearModal(discord.ui.Modal, title="Renomear Sala"):
            novo_nome = discord.ui.TextInput(
                label="Novo nome da sala",
                style=discord.TextStyle.short,
                placeholder=channel.name,
                max_length=CHANNEL_NAME_MAX,
                required=True
            )

            async def on_submit(self, modal_interaction: discord.Interaction):
                novo_raw = self.novo_nome.value.strip()
                novo = re.sub(r"[^\w\s\-\u00C0-\u017F]", "", novo_raw)
                novo = re.sub(r"\s+", " ", novo).strip()
                if not novo:
                    await modal_interaction.response.send_message("Nome inválido após sanitização.", ephemeral=True)
                    return
                novo_trunc = novo[:CHANNEL_NAME_MAX]
                try:
                    await channel.edit(name=novo_trunc)
                    await modal_interaction.response.send_message(f"Nome da sala alterado para: `{novo_trunc}`", ephemeral=True)
                except discord.Forbidden:
                    await modal_interaction.response.send_message("Você não tem permissão para renomear este canal.", ephemeral=True)
                except discord.HTTPException as e:
                    if getattr(e, "status", None) == 429:
                        await modal_interaction.response.send_message("Erro: rate limit do Discord. Tente novamente mais tarde.", ephemeral=True)
                    else:
                        await modal_interaction.response.send_message("Erro ao renomear a sala (nome inválido ou limite).", ephemeral=True)

        await interaction.response.send_modal(RenomearModal())

    @discord.ui.button(emoji="<:Convidar_Jogadores:1437594789800312852>", style=discord.ButtonStyle.secondary, custom_id="grupo_convidar")
    async def convidar(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message("Função: Convidar Jogadores.", ephemeral=True)

    @discord.ui.button(emoji="<:Remover_Membro:1437599768246222958>", style=discord.ButtonStyle.secondary, custom_id="grupo_remover")
    async def remover_membro(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message("Função: Remover Membro.", ephemeral=True)

    @discord.ui.button(emoji="<:Trocar_Limite_Membro:1437601993404452874>", style=discord.ButtonStyle.secondary, custom_id="grupo_trocar_limite")
    async def trocar_limite(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        current_limit = getattr(channel, "user_limit", 0) or 0
        placeholder = str(current_limit) if current_limit > 0 else "Sem limite"

        class LimiteModal(discord.ui.Modal, title="Trocar limite de membros"):
            limite = discord.ui.TextInput(
                label="Novo limite (0–99 / 0 = sem limite)",
                style=discord.TextStyle.short,
                placeholder=placeholder,
                max_length=2,
                required=True
            )

            async def on_submit(self, modal_interaction: discord.Interaction):
                val = self.limite.value.strip()
                if not val.isdigit():
                    await modal_interaction.response.send_message("Informe um número entre 0 e 99.", ephemeral=True)
                    return
                num = int(val)
                if num < 0 or num > 99:
                    await modal_interaction.response.send_message("Número inválido. Use um valor entre 0 e 99.", ephemeral=True)
                    return
                try:
                    await channel.edit(user_limit=0 if num == 0 else num)
                    if num == 0:
                        await modal_interaction.response.send_message("Limite removido (sem limite).", ephemeral=True)
                    else:
                        await modal_interaction.response.send_message(f"Limite de membros alterado para: `{num}`", ephemeral=True)
                except discord.Forbidden:
                    await modal_interaction.response.send_message("Não tenho permissão para alterar o limite deste canal.", ephemeral=True)
                except discord.HTTPException as e:
                    if getattr(e, "status", None) == 429:
                        await modal_interaction.response.send_message("Erro: rate limit do Discord. Tente novamente mais tarde.", ephemeral=True)
                    else:
                        await modal_interaction.response.send_message("Erro ao alterar o limite do canal.", ephemeral=True)

        await interaction.response.send_modal(LimiteModal())

    @discord.ui.button(emoji="<:Deletar_Chamada:1437598183449690204>", style=discord.ButtonStyle.secondary, custom_id="grupo_deletar")
    async def deletar_chamada(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message("Função: Deletar Chamada.", ephemeral=True)

    @discord.ui.button(emoji="<:Bloquear_Chamada:1437593371869708459>", style=discord.ButtonStyle.secondary, custom_id="grupo_bloquear")
    async def bloquear(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message("Função: Bloquear Chamada.", ephemeral=True)

    @discord.ui.button(emoji="<:Liberar_Chamada:1437593661285073006>", style=discord.ButtonStyle.secondary, custom_id="grupo_liberar")
    async def liberar_chamada(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message("Função: Liberar Chamada.", ephemeral=True)

    @discord.ui.button(emoji="<:Assumir_Lideranca:1437592237763723476>", style=discord.ButtonStyle.secondary, custom_id="grupo_assumir")
    async def assumir_lideranca(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message("Função: Assumir Liderança.", ephemeral=True)

    @discord.ui.button(emoji="<:Transferir_Lideranca:1437625407972315251>", style=discord.ButtonStyle.secondary, custom_id="grupo_transferir_lideranca")
    async def transferir_lideranca(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message("Função: Transferir Liderança.", ephemeral=True)

    @discord.ui.button(emoji="<:Trocar_Regiao:1437606614910894120>", style=discord.ButtonStyle.secondary, custom_id="grupo_trocar_regiao")
    async def trocar_regiao(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message("Função: Trocar Região.", ephemeral=True)

class EditarSalas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def salvar_no_env(self, chave: str, valor):
        set_key(".env", chave, str(valor))
        # garante que a variável passe a valer também no processo atual
        os.environ[chave] = str(valor)

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
        self.salvar_no_env("EDITAR_SALAS_CHANNEL_ID", canal_id)

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