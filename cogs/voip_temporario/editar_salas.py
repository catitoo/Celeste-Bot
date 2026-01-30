import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, set_key
from datetime import datetime, timedelta
import re

load_dotenv()

class Components(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

    container1 = discord.ui.Container(
        discord.ui.Section(
            discord.ui.TextDisplay(content="**PAINEL DE CONTROLE DA SALA**\n"),
            discord.ui.TextDisplay(content="\u200b"),
            discord.ui.TextDisplay(content="Gerencie sua chamada de forma rápida e intuitiva!"),
            accessory=discord.ui.Thumbnail(
                media="https://i.ibb.co/yBZ5Jjsk/painel-de-controle.png",
            ),
        ),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.MediaGallery(
            discord.MediaGalleryItem(
                media="https://i.ibb.co/fGrJNfRL/Imagem-guia-para-editar-os-grupos-1.png",
            ),
        ),
        discord.ui.TextDisplay(content="Utilize os botões abaixo para personalizar e controlar todos os aspectos da sua sala."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.ActionRow(
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:Editar_Nome:1437591536463249448>", custom_id="grupo_editar_nome"),
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:Convidar_Jogadores:1437594789800312852>", custom_id="grupo_convidar"),
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:Remover_Membro:1437599768246222958>", custom_id="grupo_remover"),
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:Trocar_Limite_Membro:1437601993404452874>", custom_id="grupo_trocar_limite"),
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:Deletar_Chamada:1437598183449690204>", custom_id="grupo_deletar"),
        ),
        discord.ui.ActionRow(
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:Bloquear_Chamada:1437593371869708459>", custom_id="grupo_bloquear"),
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:Liberar_Chamada:1437593661285073006>", custom_id="grupo_liberar"),
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:Assumir_Lideranca:1437592237763723476>", custom_id="grupo_assumir_lideranca"),
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:Transferir_Lideranca:1437625407972315251>", custom_id="grupo_transferir_lideranca"),
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:Trocar_Regiao:1437606614910894120>", custom_id="grupo_trocar_regiao"),
        ),
        discord.ui.ActionRow(
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:ocultar:1460317226153545759>", custom_id="grupo_ocultar"),
            discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="<:revelar:1460318751189635133>", custom_id="grupo_revelar"),
        ),
        accent_colour=discord.Colour(51455),
    )

class ConvidarMembrosSelect(discord.ui.UserSelect):
    def __init__(self, *, channel_id: int, leader_id: int):
        super().__init__(
            placeholder="Selecione os usuários que voce quer convidar para a chamada.",
            min_values=1,
            max_values=25,
        )
        self.channel_id = channel_id
        self.leader_id = leader_id

    async def callback(self, interaction: discord.Interaction):
        deferred = False
        try:
            await interaction.response.defer(ephemeral=True)
            deferred = True
        except Exception:
            pass

        async def _reply(msg: str):
            if deferred:
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)

        if interaction.user.id != self.leader_id:
            await _reply("**ERRO:** Apenas quem abriu este menu pode usar.")
            return

        guild = interaction.guild
        if not guild:
            await _reply("**ERRO:** Este menu só funciona dentro de um servidor.")
            return

        leader_member = guild.get_member(self.leader_id)
        if not leader_member or not leader_member.voice or not leader_member.voice.channel:
            await _reply("**ERRO:** Você precisa estar em um canal de voz para usar este menu.")
            return
        if leader_member.voice.channel.id != self.channel_id:
            await _reply("**ERRO:** Você não está mais na mesma sala onde abriu o menu.")
            return

        channel = leader_member.voice.channel

        try:
            invite = await channel.create_invite(
                max_age=600,
                max_uses=1,
                unique=True,
                reason=f"Convite para chamada criado por {interaction.user}"
            )
        except discord.Forbidden:
            await _reply("**ERRO:** Não tenho permissão para criar convite neste canal.")
            return
        except discord.HTTPException:
            await _reply("**ERRO:** Não foi possível criar o convite agora. Tente novamente.")
            return

        enviados: list[str] = []
        falharam: list[str] = []
        ignorados: list[str] = []

        for target in self.values:
            if not isinstance(target, discord.Member):
                target = guild.get_member(getattr(target, "id", None))

            if not target:
                continue

            if target.bot or target.id == self.leader_id:
                ignorados.append(target.display_name)
                continue

            if getattr(target, "voice", None) and target.voice.channel and target.voice.channel.id == self.channel_id:
                ignorados.append(target.display_name)
                continue

            try:
                now_br = datetime.utcnow() - timedelta(hours=3)
                footer_text = now_br.strftime("%d/%m/%Y  •  %H:%M:%S")
                embed = discord.Embed(
                    title="Convite para chamada de voz",
                    description=(
                        f"Você foi convidado(a) por `{interaction.user.display_name}` para entrar em:\n"
                        f"Canal de voz: **{channel.name}**\n"
                        f"Servidor: **{guild.name}**\n\n"
                        "Clique no botão abaixo para entrar na chamada!\n"
                    ),
                    color=discord.Color.from_rgb(128, 0, 128),
                )
                embed.set_footer(text=footer_text, icon_url=(guild.icon.url if getattr(guild, "icon", None) else None))
                view = discord.ui.View()
                view.add_item(discord.ui.Button(label="Entrar na chamada", url=invite.url))
                await target.send(embed=embed, view=view, delete_after=300)
                enviados.append(target.display_name)
            except discord.Forbidden:
                falharam.append(target.display_name)
            except discord.HTTPException:
                falharam.append(target.display_name)

        partes = []
        if enviados:
            partes.append("**Convites enviados por DM:**\n- " + "\n- ".join(f"`{n}`" for n in enviados))
        if falharam:
            partes.append("**Não foi possível enviar DM (provavelmente DM fechada):**\n- " + "\n- ".join(f"`{n}`" for n in falharam))
        if ignorados:
            partes.append("**Ignorados:**\n- " + "\n- ".join(f"`{n}`" for n in ignorados))

        await _reply("\n\n".join(partes) if partes else "Nada para fazer.")

class ConvidarMembrosView(discord.ui.View):
    def __init__(self, *, channel_id: int, leader_id: int):
        super().__init__(timeout=60)
        self.add_item(ConvidarMembrosSelect(channel_id=channel_id, leader_id=leader_id))

class EditarSalas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def salvar_no_env(self, chave: str, valor):
        set_key(".env", chave, str(valor))
        os.environ[chave] = str(valor)
    
    @discord.app_commands.command(name="set-menu-editar-sala", description="Define o canal e envia a interface de edição da sala.")
    async def set_menu_editar_sala_2(self, interaction: discord.Interaction):
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

        # Envia a view que contém callbacks (GrupoView) para que os botões funcionem corretamente.
        try:
            view = GrupoView()
            await interaction.channel.send(view=view)
        except Exception:
            try:
                await interaction.followup.send("Menu enviado.", view=view, ephemeral=True)
            except Exception:
                pass

class RemoverMembrosSelect(discord.ui.UserSelect):
    def __init__(self, *, channel_id: int, leader_id: int):
        super().__init__(
            placeholder="Selecione os usuários que voce quer remover da chamada…",
            min_values=1,
            max_values=25,
        )
        self.channel_id = channel_id
        self.leader_id = leader_id

    async def callback(self, interaction: discord.Interaction):
        deferred = False
        try:
            await interaction.response.defer(ephemeral=True)
            deferred = True
        except Exception:
            pass

        async def _reply(msg: str):
            if deferred:
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)

        if interaction.user.id != self.leader_id:
            await _reply("**ERRO:** Apenas quem abriu este menu pode usar.")
            return

        guild = interaction.guild
        if not guild:
            await _reply("**ERRO:** Este menu só funciona dentro de um servidor.")
            return

        leader_member = guild.get_member(self.leader_id)
        if not leader_member or not getattr(leader_member, "voice", None) or not leader_member.voice.channel:
            await _reply("**ERRO:** Você precisa estar em um canal de voz para usar este menu.")
            return
        if leader_member.voice.channel.id != self.channel_id:
            await _reply("**ERRO:** Você não está mais na mesma sala onde abriu o menu.")
            return

        removidos: list[str] = []
        ignorados: list[str] = []

        for target in self.values:
            if not isinstance(target, discord.Member):
                target = guild.get_member(getattr(target, "id", None))

            if not target or not getattr(target, "voice", None) or not target.voice.channel or target.voice.channel.id != self.channel_id:
                if target:
                    ignorados.append(target.display_name)
                continue

            if target.id == self.leader_id:
                ignorados.append(target.display_name)
                continue

            try:
                await target.move_to(None, reason=f"Removido da call por {interaction.user}")
                removidos.append(target.display_name)
            except discord.Forbidden:
                await _reply("**ERRO:** Não tenho permissão para mover/desconectar membros.")
                return
            except discord.HTTPException:
                ignorados.append(target.display_name)

        partes = []
        if removidos:
            partes.append("**Removidos da chamada:**\n- " + "\n- ".join(f"`{n}`" for n in removidos))
        if ignorados:
            partes.append("**Não foi possivel remover:**\n- " + "\n- ".join(f"`{n}`" for n in ignorados))

        await _reply("\n\n".join(partes) if partes else "Nada para fazer.")


class RemoverMembrosView(discord.ui.View):
    def __init__(self, *, channel_id: int, leader_id: int):
        super().__init__(timeout=60)
        self.add_item(RemoverMembrosSelect(channel_id=channel_id, leader_id=leader_id))


class TransferirLiderSelect(discord.ui.UserSelect):
    def __init__(self, *, channel_id: int, leader_id: int):
        super().__init__(
            placeholder="Selecione o usuário para transferir a liderança.",
            min_values=1,
            max_values=1,
        )
        self.channel_id = channel_id
        self.leader_id = leader_id

    async def callback(self, interaction: discord.Interaction):
        deferred = False
        try:
            await interaction.response.defer(ephemeral=True)
            deferred = True
        except Exception:
            pass

        async def _reply(msg: str):
            if deferred:
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)

        if interaction.user.id != self.leader_id:
            await _reply("**ERRO:** Apenas quem abriu este menu pode usar.")
            return

        guild = interaction.guild
        if not guild:
            await _reply("**ERRO:** Este menu só funciona dentro de um servidor.")
            return

        leader_member = guild.get_member(self.leader_id)
        if not leader_member or not getattr(leader_member, "voice", None) or not leader_member.voice.channel:
            await _reply("**ERRO:** Você precisa estar em um canal de voz para usar este menu.")
            return
        if leader_member.voice.channel.id != self.channel_id:
            await _reply("**ERRO:** Você não está mais na mesma sala onde abriu o menu.")
            return

        # pega o alvo selecionado
        target = self.values[0] if self.values else None
        if not isinstance(target, discord.Member):
            target = guild.get_member(getattr(target, "id", None))

        if not target:
            await _reply("**ERRO:** Usuário inválido selecionado.")
            return

        if target.bot:
            await _reply("**ERRO:** Não é possível transferir liderança para um bot.")
            return

        if target.id == self.leader_id:
            await _reply("**ERRO:** Você já é o líder desta sala.")
            return

        if not getattr(target, "voice", None) or not target.voice.channel or target.voice.channel.id != self.channel_id:
            await _reply("**ERRO:** O usuário precisa estar na chamada para receber a liderança.")
            return

        try:
            criar_cog = interaction.client.get_cog("CriarGrupos")
        except Exception:
            criar_cog = None

        if not criar_cog:
            await _reply("**ERRO:** Módulo de criação de salas não encontrado.")
            return

        if not hasattr(criar_cog, "canais_criados") or not isinstance(criar_cog.canais_criados, dict):
            criar_cog.canais_criados = {}

        # transfere a liderança
        criar_cog.canais_criados[self.channel_id] = target.id

        await _reply(f"**Liderança transferida**, agora `{target.display_name}` é o novo líder deste canal de voz.")


class TransferirLiderView(discord.ui.View):
    def __init__(self, *, channel_id: int, leader_id: int):
        super().__init__(timeout=60)
        self.add_item(TransferirLiderSelect(channel_id=channel_id, leader_id=leader_id))

class GrupoView(discord.ui.View):
    def __init__(self, *, timeout: float | None = None):
        super().__init__(timeout=timeout)

    def _verificar_lider(self, interaction: discord.Interaction):
        member = interaction.user
        if not getattr(member, "voice", None) or not member.voice.channel:
            return None, False, "**ERRO:** Você precisa estar em um canal de voz para usar este botão."

        channel = member.voice.channel

        # Checa categoria e canal de criação (se configurados)
        CATEGORIA_GRUPOS_ID = int(os.getenv('GRUPOS_CRIADOS_CATEGORY_ID') or 0)
        CRIAR_SALA_ID = int(os.getenv('CRIAR_SALA_CHANNEL_ID') or 0)

        if CRIAR_SALA_ID and channel.id == CRIAR_SALA_ID:
            return channel, False, "**ERRO:** Este canal não pode ser editado."

        if CATEGORIA_GRUPOS_ID:
            if not getattr(channel, "category", None) or channel.category.id != CATEGORIA_GRUPOS_ID:
                return channel, False, "**ERRO:** Este menu só funciona para canais de voz temporarios."

        criar_cog = None
        try:
            criar_cog = interaction.client.get_cog("CriarGrupos")
        except Exception:
            criar_cog = None

        if criar_cog and hasattr(criar_cog, "canais_criados"):
            lider_id = criar_cog.canais_criados.get(channel.id)
            if lider_id == member.id:
                return channel, True, None

        return channel, False, "**ERRO:** Apenas o líder da sala pode fazer isso."

    # EDITAR NOME DA SALA
    @discord.ui.button(emoji="<:Editar_Nome:1437591536463249448>", style=discord.ButtonStyle.secondary, custom_id="grupo_editar_nome")
    async def editar_nome(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        CHANNEL_NAME_MAX = 100
        PREFIX = "📢・"

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
                    await modal_interaction.response.send_message("**ERRO:** Nome inválido após sanitização.", ephemeral=True)
                    return

                max_part = CHANNEL_NAME_MAX - len(PREFIX)
                if max_part <= 0:
                    await modal_interaction.response.send_message("***ERRO:*** limite de nome inválido.", ephemeral=True)
                    return

                novo_trunc = novo[:max_part].strip()
                nome_final = f"{PREFIX}{novo_trunc}"

                try:
                    await channel.edit(name=nome_final)
                    await modal_interaction.response.send_message("**Nome da sala alterado para:** `{}`".format(novo_trunc), ephemeral=True)
                except discord.Forbidden:
                    await modal_interaction.response.send_message("**ERRO:** Não tenho permissão para renomear este canal.", ephemeral=True)
                except discord.HTTPException:
                    await modal_interaction.response.send_message("**ERRO:** Erro ao renomear a sala.", ephemeral=True)

        await interaction.response.send_modal(RenomearModal())

    # CONVIDAR USUÁRIOS PARA CHAMADA
    @discord.ui.button(emoji="<:Convidar_Jogadores:1437594789800312852>", style=discord.ButtonStyle.secondary, custom_id="grupo_convidar")
    async def convidar(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        view = ConvidarMembrosView(channel_id=channel.id, leader_id=interaction.user.id)
        await interaction.response.send_message(
            "Selecione abaixo quem você quer **convidar** para a chamada (o convite será enviado por DM):",
            view=view,
            ephemeral=True
        )

    # REMOVER USUÁRIOS DA CHAMADA
    @discord.ui.button(emoji="<:Remover_Membro:1437599768246222958>", style=discord.ButtonStyle.secondary, custom_id="grupo_remover")
    async def remover_membro(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        view = RemoverMembrosView(channel_id=channel.id, leader_id=interaction.user.id)
        await interaction.response.send_message(
            "Selecione abaixo quem você quer **remover** da chamada:",
            view=view,
            ephemeral=True
        )

    # TROCAR LIMITE DE MEMBROS DA CHAMADA
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
                    await modal_interaction.response.send_message("**ERRO:** Informe um número entre 0 e 99.", ephemeral=True)
                    return
                num = int(val)
                if num < 0 or num > 99:
                    await modal_interaction.response.send_message("**ERRO:** Número inválido. Use um valor entre 0 e 99.", ephemeral=True)
                    return
                try:
                    await channel.edit(user_limit=0 if num == 0 else num)
                    if num == 0:
                        await modal_interaction.response.send_message("Limite removido (sem limite).", ephemeral=True)
                    else:
                        await modal_interaction.response.send_message(f"Limite de membros alterado para: `{num}`", ephemeral=True)
                except discord.Forbidden:
                    await modal_interaction.response.send_message("**ERRO:** Não tenho permissão para alterar o limite deste canal.", ephemeral=True)
                except discord.HTTPException as e:
                    if getattr(e, "status", None) == 429:
                        await modal_interaction.response.send_message("**ERRO:** Rate limit do Discord. Tente novamente mais tarde.", ephemeral=True)
                    else:
                        await modal_interaction.response.send_message("**ERRO:** Não foi possível alterar o limite do canal.", ephemeral=True)

        await interaction.response.send_modal(LimiteModal())

    # DELETAR CHAMADA DE VOZ
    @discord.ui.button(emoji="<:Deletar_Chamada:1437598183449690204>", style=discord.ButtonStyle.secondary, custom_id="grupo_deletar")
    async def deletar_chamada(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        try:
            await interaction.response.send_message("Canal de voz deletado.", ephemeral=True)
        except Exception:
            pass

        try:
            criar_cog = interaction.client.get_cog("CriarGrupos")
            if criar_cog and hasattr(criar_cog, "canais_criados"):
                criar_cog.canais_criados.pop(channel.id, None)
        except Exception:
            pass

        try:
            await channel.delete(reason=f"Deletado pelo líder {interaction.user} (ID {interaction.user.id})")
        except discord.Forbidden:
            await interaction.followup.send("**ERRO:** Não tenho permissão para deletar este canal.", ephemeral=True)
        except discord.HTTPException as e:
            if getattr(e, "status", None) == 429:
                await interaction.followup.send("**ERRO:** Tente novamente mais tarde.", ephemeral=True)
            else:
                await interaction.followup.send("**ERRO:** Não foi possível deletar o canal.", ephemeral=True)

    # ASSUMIR LIDERANÇA
    @discord.ui.button(emoji="<:Assumir_Lideranca:1437592237763723476>", style=discord.ButtonStyle.secondary, custom_id="grupo_assumir_lideranca")
    async def assumir_lideranca(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        if not getattr(member, "voice", None) or not member.voice.channel:
            await interaction.response.send_message("**ERRO:** Você precisa estar em um canal de voz para usar este botão.", ephemeral=True)
            return

        channel = member.voice.channel

        # Checa categoria e canal de criação (se configurados)
        CATEGORIA_GRUPOS_ID = int(os.getenv('GRUPOS_CRIADOS_CATEGORY_ID') or 0)
        CRIAR_SALA_ID = int(os.getenv('CRIAR_SALA_CHANNEL_ID') or 0)

        if CRIAR_SALA_ID and channel.id == CRIAR_SALA_ID:
            await interaction.response.send_message("**ERRO:** Este canal não pode ser editado.", ephemeral=True)
            return

        if CATEGORIA_GRUPOS_ID:
            if not getattr(channel, "category", None) or channel.category.id != CATEGORIA_GRUPOS_ID:
                await interaction.response.send_message("**ERRO:** Este menu só funciona para canais de voz temporarios.", ephemeral=True)
                return

        try:
            criar_cog = interaction.client.get_cog("CriarGrupos")
        except Exception:
            criar_cog = None

        if not criar_cog:
            await interaction.response.send_message("**ERRO:** Módulo de criação de salas não encontrado.", ephemeral=True)
            return

        if not hasattr(criar_cog, "canais_criados") or not isinstance(criar_cog.canais_criados, dict):
            criar_cog.canais_criados = {}

        lider_atual_id = criar_cog.canais_criados.get(channel.id)
        if lider_atual_id:
            # Se quem clicou já é o líder, informa e retorna
            if lider_atual_id == member.id:
                await interaction.response.send_message("**ERRO:** Você já é o líder desta sala.", ephemeral=True)
                return

            lider_member = channel.guild.get_member(lider_atual_id)
            if lider_member and getattr(lider_member, "voice", None) and lider_member.voice.channel and lider_member.voice.channel.id == channel.id:
                await interaction.response.send_message("**ERRO:** O líder atual ainda está presente na chamada.", ephemeral=True)
                return

        criar_cog.canais_criados[channel.id] = member.id
        try:
            await interaction.response.send_message(f"**Liderança assumida**, agora `{member.display_name}` é o líder desta sala.", ephemeral=True)
        except Exception:
            pass

    # TRANSFERIR LIDERANÇA
    @discord.ui.button(emoji="<:Transferir_Lideranca:1437625407972315251>", style=discord.ButtonStyle.secondary, custom_id="grupo_transferir_lideranca")
    async def transferir_lideranca(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        view = TransferirLiderView(channel_id=channel.id, leader_id=interaction.user.id)
        await interaction.response.send_message(
            "Selecione abaixo para quem deseja transferir a liderança:",
            view=view,
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(EditarSalas(bot))
    bot.add_view(Components())
    bot.add_view(GrupoView())