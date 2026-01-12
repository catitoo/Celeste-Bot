import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, set_key
from datetime import datetime, timedelta
load_dotenv()

class RemoverMembrosSelect(discord.ui.UserSelect):
    def __init__(self, *, channel_id: int, leader_id: int):
        # Visual “nativo” de seleção de usuários (bem parecido com o de cargos)
        super().__init__(
            placeholder="Selecione os usuários para remover da chamada…",
            min_values=1,
            max_values=25,  # limite do componente
        )
        self.channel_id = channel_id
        self.leader_id = leader_id

    async def callback(self, interaction: discord.Interaction):
        # Segurança: só o líder que abriu consegue executar
        if interaction.user.id != self.leader_id:
            await interaction.response.send_message("Apenas quem abriu este menu pode usar.", ephemeral=True)
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Este menu só funciona dentro de um servidor.", ephemeral=True)
            return

        # Confirma que o líder ainda está na mesma sala
        leader_member = guild.get_member(self.leader_id)
        if not leader_member or not leader_member.voice or not leader_member.voice.channel:
            await interaction.response.send_message("Você precisa estar em uma sala de voz para usar este menu.", ephemeral=True)
            return
        if leader_member.voice.channel.id != self.channel_id:
            await interaction.response.send_message("Você não está mais na mesma sala onde abriu o menu.", ephemeral=True)
            return

        removidos: list[str] = []
        ignorados: list[str] = []

        # `self.values` tende a vir como Members em contexto de guild
        for target in self.values:
            if not isinstance(target, discord.Member):
                target = guild.get_member(getattr(target, "id", None))

            if not target or not target.voice or not target.voice.channel or target.voice.channel.id != self.channel_id:
                if target:
                    ignorados.append(target.display_name)
                continue

            # (Opcional) impedir remover a si mesmo
            if target.id == self.leader_id:
                ignorados.append(target.display_name)
                continue

            try:
                await target.move_to(None, reason=f"Removido da call por {interaction.user}")
                removidos.append(target.display_name)
            except discord.Forbidden:
                await interaction.response.send_message(
                    "Não tenho permissão para mover/desconectar membros (perm: **Mover Membros**).",
                    ephemeral=True
                )
                return
            except discord.HTTPException:
                ignorados.append(target.display_name)

        msg = []
        if removidos:
            msg.append("**Removidos da chamada:**\n- " + "\n- ".join(f"`{n}`" for n in removidos))
        if ignorados:
            msg.append("**Não foi possivel remover:**\n- " + "\n- ".join(f"`{n}`" for n in ignorados))

        await interaction.response.send_message("\n\n".join(msg) if msg else "Nada para fazer.", ephemeral=True)


class RemoverMembrosView(discord.ui.View):
    def __init__(self, *, channel_id: int, leader_id: int):
        super().__init__(timeout=60)  # menu temporário
        self.add_item(RemoverMembrosSelect(channel_id=channel_id, leader_id=leader_id))


class ConvidarMembrosSelect(discord.ui.UserSelect):
    def __init__(self, *, channel_id: int, leader_id: int):
        super().__init__(
            placeholder="Selecione os usuários para convidar para a chamada…",
            min_values=1,
            max_values=25,
        )
        self.channel_id = channel_id
        self.leader_id = leader_id

    async def callback(self, interaction: discord.Interaction):
        # Segurança: só o líder que abriu consegue executar
        if interaction.user.id != self.leader_id:
            await interaction.response.send_message("Apenas quem abriu este menu pode usar.", ephemeral=True)
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Este menu só funciona dentro de um servidor.", ephemeral=True)
            return

        leader_member = guild.get_member(self.leader_id)
        if not leader_member or not leader_member.voice or not leader_member.voice.channel:
            await interaction.response.send_message("Você precisa estar em uma sala de voz para usar este menu.", ephemeral=True)
            return
        if leader_member.voice.channel.id != self.channel_id:
            await interaction.response.send_message("Você não está mais na mesma sala onde abriu o menu.", ephemeral=True)
            return

        channel = leader_member.voice.channel

        # Cria um convite curto (10 min / 1 uso) para mandar por DM
        try:
            invite = await channel.create_invite(
                max_age=600,
                max_uses=1,
                unique=True,
                reason=f"Convite para call criado por {interaction.user} (ID {interaction.user.id})"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Não tenho permissão para criar convite neste canal (perm: **Criar Convite Instantâneo**).",
                ephemeral=True
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message("Não foi possível criar o convite agora. Tente novamente.", ephemeral=True)
            return

        enviados: list[str] = []
        falharam: list[str] = []
        ignorados: list[str] = []

        for target in self.values:
            if not isinstance(target, discord.Member):
                target = guild.get_member(getattr(target, "id", None))

            if not target:
                continue

            # Ignora bots e o próprio líder
            if target.bot or target.id == self.leader_id:
                ignorados.append(target.display_name)
                continue

            # (Opcional) ignorar quem já está na mesma call
            if target.voice and target.voice.channel and target.voice.channel.id == self.channel_id:
                ignorados.append(target.display_name)
                continue

            try:
                now = discord.utils.utcnow()
                now_br = datetime.utcnow() - timedelta(hours=3)  # UTC-3
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

                embed.set_footer(
                    text=footer_text,
                    icon_url=(guild.icon.url if getattr(guild, "icon", None) else None)
                )
                view = discord.ui.View()
                view.add_item(discord.ui.Button(label="Entrar na chamada", url=invite.url))
                await target.send(embed=embed, view=view, delete_after=300)  # apaga em 5 minutos
                enviados.append(target.display_name)
            except discord.Forbidden:
                # DM fechada / não aceita DMs do servidor
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

        await interaction.response.send_message("\n\n".join(partes) if partes else "Nada para fazer.", ephemeral=True)


class ConvidarMembrosView(discord.ui.View):
    def __init__(self, *, channel_id: int, leader_id: int):
        super().__init__(timeout=60)
        self.add_item(ConvidarMembrosSelect(channel_id=channel_id, leader_id=leader_id))


class TransferirLiderSelect(discord.ui.UserSelect):
    def __init__(self, *, channel_id: int, leader_id: int):
        super().__init__(
            placeholder="Selecione o usuário para transferir a liderança…",
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

        # Segurança: só o líder que abriu consegue executar
        if interaction.user.id != self.leader_id:
            await _reply("Apenas quem abriu este menu pode usar.")
            return

        guild = interaction.guild
        if not guild:
            await _reply("Este menu só funciona dentro de um servidor.")
            return

        leader_member = guild.get_member(self.leader_id)
        if not leader_member or not getattr(leader_member, "voice", None) or not leader_member.voice.channel:
            await _reply("Você precisa estar em uma sala de voz para usar este menu.")
            return
        if leader_member.voice.channel.id != self.channel_id:
            await _reply("Você não está mais na mesma sala onde abriu o menu.")
            return

        target = self.values[0]
        if not isinstance(target, discord.Member):
            target = guild.get_member(getattr(target, "id", None))

        if not target:
            await _reply("**Erro ao transferir liderança:** Usuário inválido.")
            return

        if target.bot:
            await _reply("**Erro ao transferir liderança:** Não é possível transferir liderança para um bot.")
            return

        if not getattr(target, "voice", None) or not target.voice.channel or target.voice.channel.id != self.channel_id:
            await _reply("**Erro ao transferir liderança:** O usuário precisa estar presente na chamada para receber a liderança.")
            return

        if target.id == self.leader_id:
            await _reply("**Erro ao transferir liderança:** Você já é o líder dessa sala.")
            return

        try:
            criar_cog = interaction.client.get_cog("CriarGrupos")
            if not criar_cog:
                await _reply("Módulo de criação de salas não encontrado.")
                return

            if not hasattr(criar_cog, "canais_criados") or not isinstance(criar_cog.canais_criados, dict):
                criar_cog.canais_criados = {}

            criar_cog.canais_criados[self.channel_id] = target.id

            # envia a confirmação primeiro
            await _reply(f"**Liderança transferida** para `{target.display_name}`.")

            # então tenta apagar a mensagem do menu (tratando casos deferred e non-deferred)
            try:
                if deferred:
                    await interaction.delete_original_response()
                else:
                    if getattr(interaction, "message", None):
                        await interaction.message.delete()
            except Exception:
                pass
        except Exception:
            await _reply("Erro ao transferir liderança. Tente novamente.")

class TransferirLiderView(discord.ui.View):
    def __init__(self, *, channel_id: int, leader_id: int):
        super().__init__(timeout=60)
        self.add_item(TransferirLiderSelect(channel_id=channel_id, leader_id=leader_id))


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

    # Editar nome da sala
    @discord.ui.button(emoji="<:Editar_Nome:1437591536463249448>", style=discord.ButtonStyle.secondary, custom_id="grupo_editar_nome")
    async def editar_nome(self, interaction: discord.Interaction, button: discord.ui.Button):
        import re
        channel, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        CHANNEL_NAME_MAX = 50
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
                    await modal_interaction.response.send_message("Nome inválido após sanitização.", ephemeral=True)
                    return

                max_part = CHANNEL_NAME_MAX - len(PREFIX)
                if max_part <= 0:
                    await modal_interaction.response.send_message("Erro de configuração: limite de nome inválido.", ephemeral=True)
                    return

                novo_trunc = novo[:max_part].strip()
                nome_final = f"{PREFIX}{novo_trunc}"

                try:
                    await channel.edit(name=nome_final)
                    await modal_interaction.response.send_message(f"Nome da sala alterado para: `{novo_trunc}`", ephemeral=True)
                except discord.Forbidden:
                    await modal_interaction.response.send_message("Você não tem permissão para renomear este canal.", ephemeral=True)
                except discord.HTTPException as e:
                    if getattr(e, "status", None) == 429:
                        await modal_interaction.response.send_message("Erro: rate limit do Discord. Tente novamente mais tarde.", ephemeral=True)
                    else:
                        await modal_interaction.response.send_message("Erro ao renomear a sala (nome inválido ou limite).", ephemeral=True)

        await interaction.response.send_modal(RenomearModal())

    # Convidar jogadores
    @discord.ui.button(emoji="<:Convidar_Jogadores:1437594789800312852>", style=discord.ButtonStyle.secondary, custom_id="grupo_convidar")
    async def convidar(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        view = ConvidarMembrosView(channel_id=channel.id, leader_id=interaction.user.id)
        await interaction.response.send_message(
            "Selecione abaixo quem você quer **convidar** para a chamada (o bot vai enviar DM com o link):",
            view=view,
            ephemeral=True
        )

    # Remover membro
    @discord.ui.button(emoji="<:Remover_Membro:1437599768246222958>", style=discord.ButtonStyle.secondary, custom_id="grupo_remover")
    async def remover_membro(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        view = RemoverMembrosView(channel_id=channel.id, leader_id=interaction.user.id)
        await interaction.response.send_message(
            "Selecione abaixo quem você quer remover da chamada:",
            view=view,
            ephemeral=True
        )

    # Trocar limite de membros
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

    # Deletar chamada de voz
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
            await interaction.followup.send("Não tenho permissão para deletar este canal.", ephemeral=True)
        except discord.HTTPException as e:
            if getattr(e, "status", None) == 429:
                await interaction.followup.send("Erro: rate limit do Discord. Tente novamente mais tarde.", ephemeral=True)
            else:
                await interaction.followup.send("Erro ao deletar o canal.", ephemeral=True)

    # Ocultar chamada
    @discord.ui.button(emoji="<:Bloquear_Chamada:1437593371869708459>", style=discord.ButtonStyle.secondary, custom_id="grupo_ocultar")
    async def ocultar(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message("Função: Ocultar Chamada.", ephemeral=True)

    # Revelar chamada
    @discord.ui.button(emoji="<:Liberar_Chamada:1437593661285073006>", style=discord.ButtonStyle.secondary, custom_id="grupo_revelar")
    async def revelar_chamada(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message("Função: Revelar Chamada.", ephemeral=True)

    # Assumir liderança
    @discord.ui.button(emoji="<:Assumir_Lideranca:1437592237763723476>", style=discord.ButtonStyle.secondary, custom_id="grupo_assumir")
    async def assumir_lideranca(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        if not getattr(member, "voice", None) or not member.voice.channel:
            await interaction.response.send_message("Você precisa estar em um canal de voz para fazer isso.", ephemeral=True)
            return

        channel = member.voice.channel

        CATEGORIA_GRUPOS_ID = int(os.getenv('GRUPOS_CRIADOS_CATEGORY_ID') or 0)
        CRIAR_SALA_ID = int(os.getenv('CRIAR_SALA_CHANNEL_ID') or 0)

        if CRIAR_SALA_ID and channel.id == CRIAR_SALA_ID:
            await interaction.response.send_message("Este canal não pode ser editado.", ephemeral=True)
            return

        if CATEGORIA_GRUPOS_ID:
            if not getattr(channel, "category", None) or channel.category.id != CATEGORIA_GRUPOS_ID:
                await interaction.response.send_message("Este menu só funciona para canais de voz temporarios.", ephemeral=True)
                return

        criar_cog = interaction.client.get_cog("CriarGrupos")
        if not criar_cog:
            await interaction.response.send_message("Módulo de criação de salas não encontrado.", ephemeral=True)
            return

        if not hasattr(criar_cog, "canais_criados") or not isinstance(criar_cog.canais_criados, dict):
            criar_cog.canais_criados = {}

        current_leader_id = criar_cog.canais_criados.get(channel.id)

        if current_leader_id == member.id:
            await interaction.response.send_message("Você já é o líder desta sala.", ephemeral=True)
            return

        guild = interaction.guild
        leader_member = guild.get_member(current_leader_id) if current_leader_id else None

        if leader_member and getattr(leader_member, "voice", None) and leader_member.voice.channel and leader_member.voice.channel.id == channel.id:
            await interaction.response.send_message("**Você não pode assumir a liderança desta chamada.**  O líder atual ainda está presente na chamada. ", ephemeral=True)
            return

        criar_cog.canais_criados[channel.id] = member.id

        try:
            await interaction.response.send_message(f"Você agora é o líder desta chamada.", ephemeral=True)
        except Exception:
            pass

    # Transferir liderança
    @discord.ui.button(emoji="<:Transferir_Lideranca:1437625407972315251>", style=discord.ButtonStyle.secondary, custom_id="grupo_transferir_lideranca")
    async def transferir_lideranca(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel, is_leader, err = self._verificar_lider(interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        view = TransferirLiderView(channel_id=channel.id, leader_id=interaction.user.id)
        await interaction.response.send_message(
            "Selecione o usuário para transferir a liderança (o usuário precisa estar na chamada):",
            view=view,
            ephemeral=True
        )

    # Trocar região
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