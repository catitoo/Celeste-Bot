import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, set_key
from datetime import datetime
from database.setup_database import SessionLocal, FormulariosDesenvolvedor, FormulariosDesenvolvedorAprovados

load_dotenv()

class BotoesFormulario(discord.ui.View):
    def __init__(self, bot: commands.Bot, *, timeout: float = None):
        super().__init__(timeout=timeout)
        self.bot = bot

    @discord.ui.button(label="Aprovar", style=discord.ButtonStyle.success, custom_id="aprovar_button")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        admin_cargo_id = os.getenv("ADMINISTRADOR_CARGO_ID")
        if not admin_cargo_id:
            await interaction.response.send_message("Cargo administrador não configurado.", ephemeral=True)
            return
        try:
            admin_cargo_id = int(admin_cargo_id)
        except ValueError:
            await interaction.response.send_message("Cargo administrador inválido.", ephemeral=True)
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            member = interaction.guild.get_member(member.id)
        if not member or not any(role.id == admin_cargo_id for role in member.roles):
            await interaction.response.send_message("Você não tem permissão para aprovar.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        old_message_id = str(interaction.message.id)

        # Busca o formulário original
        session = SessionLocal()
        try:
            form = session.query(FormulariosDesenvolvedor).filter_by(id_mensagem=old_message_id).first()
            if not form:
                await interaction.followup.send("Formulário não encontrado.", ephemeral=True)
                return
            if form.status != "pendente":
                await interaction.followup.send("Formulário já foi avaliado.", ephemeral=True)
                return
        except Exception:
            session.rollback()
            await interaction.followup.send("Erro ao acessar o banco de dados.", ephemeral=True)
            return
        finally:
            session.close()

        # Prepara conteúdo/embed para reenviar
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        content = interaction.message.content if not embed else None

        approved_channel_env = os.getenv("FORMULARIO_APROVADO_DESENVOLVEDOR_CHANNEL_ID")
        if not approved_channel_env:
            await interaction.followup.send("Canal de aprovados não configurado.", ephemeral=True)
            return
        try:
            approved_channel_id = int(approved_channel_env)
        except ValueError:
            await interaction.followup.send("ID do canal de aprovados inválido.", ephemeral=True)
            return

        approved_channel = self.bot.get_channel(approved_channel_id)
        if approved_channel is None:
            await interaction.followup.send("Não encontrei o canal de aprovados configurado.", ephemeral=True)
            return

        try:
            # Cria nova embed com cor e imagem de aprovado, preservando dados do embed original
            if embed:
                new_embed = discord.Embed(
                    title=embed.title if getattr(embed, "title", None) else None,
                    description=embed.description if getattr(embed, "description", None) else None,
                    colour=discord.Colour.from_str("#00ff40")
                )
                for f in embed.fields:
                    new_embed.add_field(name=f.name, value=f.value, inline=f.inline)
                if getattr(embed, "thumbnail", None) and getattr(embed.thumbnail, "url", None):
                    new_embed.set_thumbnail(url=embed.thumbnail.url)
                if getattr(embed, "author", None) and getattr(embed.author, "name", None):
                    try:
                        new_embed.set_author(name=embed.author.name, icon_url=getattr(embed.author, "icon_url", None))
                    except Exception:
                        pass
                if getattr(embed, "footer", None) and getattr(embed.footer, "text", None):
                    new_embed.set_footer(text=embed.footer.text)
                new_embed.set_image(url="https://i.ibb.co/gZn6mfHS/formulario-aprovado-imagem.png")
            else:
                new_embed = discord.Embed(colour=discord.Colour.from_str("#00ff40"))
                new_embed.set_image(url="https://i.ibb.co/gZn6mfHS/formulario-aprovado-imagem.png")

            new_msg = await approved_channel.send(content=content, embed=new_embed)
        except Exception:
            await interaction.followup.send("Erro ao enviar a mensagem para o canal de aprovados.", ephemeral=True)
            return

        # Move registro: insere em aprovados e remove o original
        approver_apelido = getattr(member, "display_name", str(member))
        session = SessionLocal()
        try:
            original = session.query(FormulariosDesenvolvedor).filter_by(id_mensagem=old_message_id).first()
            if original:
                aprovado = FormulariosDesenvolvedorAprovados(
                    id_usuario=int(original.id_usuario),
                    id_mensagem=str(new_msg.id),
                    nome=original.nome,
                    sexo=original.sexo,
                    genero_favorito=original.genero_favorito,
                    plataforma_principal=original.plataforma_principal,
                    redes_sociais=original.redes_sociais,
                    status="aprovado",
                    data_envio=original.data_envio,
                    aprovado_por=approver_apelido,
                    data_aprovacao=datetime.utcnow()
                )
                session.add(aprovado)
                session.delete(original)
                session.commit()
        except Exception:
            session.rollback()
            await interaction.followup.send("Erro ao mover formulário no banco de dados.", ephemeral=True)
            return
        finally:
            session.close()

        # Tenta excluir a mensagem original
        try:
            await interaction.message.delete()
        except Exception:
            pass

        # Atualiza view (desabilita botões)
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.channel.send("", delete_after=0)  # noop para evitar exceptions ao editar view após delete
        except Exception:
            pass

        await interaction.followup.send("**Formulário Aprovado!**\n Uma mensagem foi enviada ao usuario com informações iniciais da comunidade.", ephemeral=True)

    @discord.ui.button(label="Rejeitar", style=discord.ButtonStyle.danger, custom_id="rejeitar_button")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        admin_cargo_id = os.getenv("ADMINISTRADOR_CARGO_ID")
        if not admin_cargo_id:
            await interaction.response.send_message("Cargo administrador não configurado.", ephemeral=True)
            return
        try:
            admin_cargo_id = int(admin_cargo_id)
        except ValueError:
            await interaction.response.send_message("Cargo administrador inválido.", ephemeral=True)
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            member = interaction.guild.get_member(member.id)
        if not member or not any(role.id == admin_cargo_id for role in member.roles):
            await interaction.response.send_message("Você não tem permissão para rejeitar.", ephemeral=True)
            return

        session = SessionLocal()
        try:
            form = session.query(FormulariosDesenvolvedor).filter_by(id_mensagem=str(interaction.message.id)).first()
            if not form:
                await interaction.response.send_message("Formulário não encontrado.", ephemeral=True)
                return
            if form.status != "pendente":
                await interaction.response.send_message("Formulário já foi avaliado.", ephemeral=True)
                return
            form.status = "rejeitado"
            session.commit()
        except Exception:
            session.rollback()
            await interaction.response.send_message("Erro ao atualizar no banco de dados.", ephemeral=True)
            return
        finally:
            session.close()

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("Formulário rejeitado.", ephemeral=True)
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
            # Campo 2: Sexo
            self.sexo = discord.ui.TextInput(
                label="Sexo",
                style=discord.TextStyle.short,
                required=True,
                min_length=1,
                max_length=32
            )
            self.add_item(self.sexo)
            # Campo 3: Gênero de jogos favorito
            self.genero_jogos = discord.ui.TextInput(
                label="Qual é o seu genero de jogos favorito?",
                style=discord.TextStyle.short,
                required=True,
                min_length=1,
                max_length=200
            )
            self.add_item(self.genero_jogos)
            # Campo 4: Plataforma principal
            self.plataforma_principal = discord.ui.TextInput(
                label="Qual sua plataforma principal?",
                style=discord.TextStyle.short,
                required=False,
                max_length=64,
                placeholder="Ex: PC / PS / Xbox / Mobile / Switch"
            )
            self.add_item(self.plataforma_principal)
            # Campo 5: Redes Sociais (Opcional)
            self.redes_sociais = discord.ui.TextInput(
                label="Redes Sociais (Opcional)",
                style=discord.TextStyle.long,
                required=False,
                max_length=200,
                placeholder="Ex: Instagram:@usuario, Steam:perfil"
            )
            self.add_item(self.redes_sociais)
        
        async def on_submit(self, interaction: discord.Interaction):
            # Coleta valores do modal
            nome = (self.nome_completo.value or "").strip()
            sexo = (self.sexo.value or "").strip()
            genero = (self.genero_jogos.value or "").strip()
            plataforma = (self.plataforma_principal.value or "").strip() or None
            redes = (self.redes_sociais.value or "").strip() or None

            # Recupera canal configurado via .env
            canal_env = os.getenv("FORMULARIO_PENDENTE_DESENVOLVEDOR_CHANNEL_ID")
            if not canal_env:
                await interaction.response.send_message("Canal de formulários não configurado.", ephemeral=True)
                return
            try:
                canal_id = int(canal_env)
            except ValueError:
                await interaction.response.send_message("ID do canal de formulários inválido.", ephemeral=True)
                return

            channel = self.bot.get_channel(canal_id)
            if channel is None:
                await interaction.response.send_message("Não encontrei o canal configurado.", ephemeral=True)
                return

            # Monta o embed do formulário
            safe_name = getattr(interaction.user, "display_name", str(interaction.user)).replace("`", "'")
            embed = discord.Embed(
                title=f"Formulário de `{safe_name}`", 
                colour=discord.Colour.from_str("#57bef1")
            )
            embed.set_thumbnail(url=getattr(interaction.user, 'display_avatar').url)
            embed.add_field(
                name="\u200b",
                value=(
                    f"**Nome:** `{nome or 'Não Informado'}`\n"
                    f"**Sexo:** `{sexo or 'Não Informado'}`\n"
                    f"**Gênero de jogos favorito:** `{genero or 'Não Informado'}`\n"
                    f"**Plataforma Principal:** `{plataforma or 'Não Informado'}`\n"
                    f"**Redes sociais:** `{redes or 'Não Informado'}`"
                ),
                inline=False
            )
            embed.set_image(url="https://i.ibb.co/xqmX2PBW/formulario-pendente-imagem.png")

            # Envia o embed ao canal configurado com os botões de review
            try:
                view = BotoesFormulario(self.bot)
                msg = await channel.send(embed=embed, view=view)

                # Adiciona reações ao formulário
                try:
                    await msg.add_reaction("<:arrow_up:1469527813307633664>")
                    await msg.add_reaction("<:arrow_down:1469527811935961149>")
                except Exception:
                    pass

                # Cria uma thread vinculada a esta mensagem
                try:
                    thread = await msg.create_thread(
                        name=f"Discussão Sobre: {safe_name}",
                        auto_archive_duration= 4320 ,  # 4320 = 72 horas
                        reason=f"Discussão sobre o formulário de {safe_name}"
                    )
                except Exception:
                    thread = None

            except Exception:
                await interaction.response.send_message("Erro ao enviar formulário ao canal.", ephemeral=True)
                return

            # Salva no banco de dados
            session = SessionLocal()
            try:
                form = FormulariosDesenvolvedor(
                    id_usuario=int(interaction.user.id),
                    id_mensagem=str(msg.id),
                    nome=nome,
                    sexo=sexo,
                    genero_favorito=genero,
                    plataforma_principal=plataforma,
                    redes_sociais=redes,
                    status="pendente",
                    data_envio=datetime.utcnow()
                )
                session.add(form)
                session.commit()
            except Exception:
                session.rollback()
                await interaction.response.send_message("Erro ao salvar no banco de dados.", ephemeral=True)
                return
            finally:
                session.close()

            await interaction.response.send_message("Formulário enviado com sucesso!", ephemeral=True)
    class Registrar_Usurario_View(discord.ui.View):
        def __init__(self, bot: commands.Bot, *, timeout: float = None):
            super().__init__(timeout=timeout)
            self.bot = bot

        @discord.ui.button(label="Registrar-se", style=discord.ButtonStyle.primary, custom_id="registrar_se_button")
        async def registrar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            modal = registrar_usuario.Registrar_Usurario_Modal(self.bot)
            await interaction.response.send_modal(modal)

    # novo: container visual para registro (substitui embed)
    class RegistroComponents(discord.ui.LayoutView):
        def __init__(self):
            super().__init__(timeout=None)

        container1 = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(content="**REGISTRE-SE**"),
                discord.ui.TextDisplay(content="\u200b"),
                discord.ui.TextDisplay(content="Seja muito bem-vindo(a). Para começar, clique no botão abaixo e preencha o formulário de inscrição."),
                accessory=discord.ui.Thumbnail(
                    media="https://i.ibb.co/qMpksCc3/imagem-registro-icon.png",
                ),
                
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            discord.ui.Section(
            discord.ui.TextDisplay(content="Após o envio, seus dados passarão por uma breve análise. Assim que aprovado, você receberá acesso total à nossa comunidade."),
            accessory=discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="Registrar-se",
                custom_id="registrar_se_button",
            ),
        ),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.MediaGallery(
            discord.MediaGalleryItem(
                media="https://i.ibb.co/0jFYT63k/imagem-registro.png",
            ),
        ),
        accent_colour=discord.Colour(16740864),
    )

    async def registrar_view(self):
        await self.bot.wait_until_ready()
        self.bot.add_view(self.RegistroComponents())


    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # trata o clique no botão do container e abre o modal
        try:
            if interaction.type != discord.InteractionType.component:
                return
            data = getattr(interaction, "data", None) or {}
            custom_id = data.get("custom_id")
            if custom_id != "registrar_se_button":
                return
            if interaction.response.is_done():
                return
            modal = registrar_usuario.Registrar_Usurario_Modal(self.bot)
            await interaction.response.send_modal(modal)
        except Exception:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("**ERRO interno ao processar interação.**", ephemeral=True)
            except Exception:
                pass
            raise

    @discord.app_commands.command(name="set-canal-registro", description="Define o canal para o menu de registro e envia o menu no canal.")
    async def set_canal_registro(self, interaction: discord.Interaction):
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
        # Salva o ID do canal específico de registro na variável FORMULARIO_REGISTRAR_DESENVOLVEDOR_CHANNEL_ID
        self.salvar_no_env("FORMULARIO_REGISTRAR_DESENVOLVEDOR_CHANNEL_ID", canal_id)

        await interaction.response.send_message(f"O canal {interaction.channel.mention} foi definido para o menu de formulário.", ephemeral=True)

        # envia o Container visual com o botão que abre o modal
        await interaction.channel.send(view=self.RegistroComponents())

async def setup(bot: commands.Bot):
    cog = registrar_usuario(bot)
    await bot.add_cog(cog)
    # Inicia a tarefa que registra a view persistente (opcional)
    bot.loop.create_task(cog.registrar_view())