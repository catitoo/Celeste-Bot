import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, set_key
from datetime import datetime
import asyncio  # Necessário para o timer
import time     # Necessário para o rate limit
from database.setup_database import SessionLocal, FormulariosDesenvolvedor, FormulariosDesenvolvedorAprovados, FormulariosDesenvolvedorRejeitados

# (novo) tenta importar a tabela de formulários ativos; se não existir, usa fallback
try:
    from database.setup_database import FormulariosAtivos  # type: ignore
except Exception:
    FormulariosAtivos = None  # fallback

load_dotenv()

# --- Função Auxiliar para agendar a atualização (Hook) ---
def agendar_atualizacao_canal(bot: commands.Bot):
    cog = bot.get_cog("registrar_usuario")
    if cog:
        cog.schedule_channel_rename()

class MotivoRejeicaoModal(discord.ui.Modal):
    def __init__(
        self,
        parent_view: "BotoesFormulario",
        bot: commands.Bot,
        message_id: int,
        channel_id: int,
        reviewer_display_name: str,
    ):
        super().__init__(title="Rejeitar Formulário")
        self.parent_view = parent_view
        self.bot = bot
        self.message_id = int(message_id)
        self.channel_id = int(channel_id)
        self.reviewer_display_name = reviewer_display_name

        self.motivo = discord.ui.TextInput(
            label="Motivo da Rejeição (Opcional)",
            style=discord.TextStyle.long,
            required=False,
            max_length=500,
        )
        self.add_item(self.motivo)

    async def on_submit(self, interaction: discord.Interaction):
        motivo_txt = (self.motivo.value or "").strip()
        if not motivo_txt:
            motivo_txt = "Não Informado"

        await interaction.response.defer(ephemeral=True)
        await self.parent_view._process_rejection(
            interaction,
            message_id=self.message_id,
            channel_id=self.channel_id,
            reviewer_apelido=self.reviewer_display_name,
            motivo=motivo_txt,
        )

class BotoesFormulario(discord.ui.View):
    def __init__(self, bot: commands.Bot, *, timeout: float = None):
        super().__init__(timeout=timeout)
        self.bot = bot

    @staticmethod
    def _motivo_deve_aparecer(motivo: str) -> bool:
        txt = (motivo or "").strip()
        if not txt:
            return False
        txt_fold = txt.casefold()
        return txt_fold not in {"não informado", "nao informado"}

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
            await interaction.response.send_message("Você não tem permissão para fazer isso.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        old_message_id = str(interaction.message.id)

        # Busca o formulário original e valida
        session = SessionLocal()
        try:
            form = session.query(FormulariosDesenvolvedor).filter_by(id_mensagem=old_message_id).first()
            if not form:
                await interaction.followup.send("Formulário não encontrado.", ephemeral=True)
                return
            if form.status != "pendente":
                await interaction.followup.send("Formulário já foi avaliado.", ephemeral=True)
                return

            # (novo) remove marcação de "ativo" do usuário (se a tabela existir)
            if FormulariosAtivos is not None:
                try:
                    session.query(FormulariosAtivos).filter_by(id_usuario=str(form.id_usuario)).delete(synchronize_session=False)
                except Exception:
                    # não bloqueia a aprovação se a tabela/colunas não baterem
                    pass

            # Copia os dados necessários para possível reversão
            original_data = {
                "id_usuario": form.id_usuario,
                "id_mensagem": form.id_mensagem,
                "nome": form.nome,
                "sexo": form.sexo,
                "genero_favorito": form.genero_favorito,
                "plataforma_principal": form.plataforma_principal,
                "redes_sociais": form.redes_sociais,
                "status": form.status,
                "data_envio": form.data_envio
            }

            # Cria registro aprovado (sem id_mensagem por enquanto) e remove o original
            approver_apelido = getattr(member, "display_name", str(member))
            aprovado = FormulariosDesenvolvedorAprovados(
                id_usuario=int(form.id_usuario),
                id_mensagem="",  # será atualizado após envio da mensagem
                nome=form.nome,
                sexo=form.sexo,
                genero_favorito=form.genero_favorito,
                plataforma_principal=form.plataforma_principal,
                redes_sociais=form.redes_sociais,
                status="aprovado",
                data_envio=form.data_envio,
                aprovado_por=approver_apelido,
                data_aprovacao=datetime.utcnow()
            )
            session.add(aprovado)
            session.delete(form)
            session.commit()
            aprovado_id = getattr(aprovado, "id", None)
        except Exception as e:
            session.rollback()
            session.close()
            print(f"Erro ao mover formulário no banco de dados: {e}")
            await interaction.followup.send("Erro ao mover formulário no banco de dados.", ephemeral=True)
            return
        finally:
            session.close()

        # Preparar embed/conteúdo a enviar (reuso do embed original do message)
        approver_apelido = getattr(member, "display_name", str(member))
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        content = interaction.message.content if not embed else None

        approved_channel_env = os.getenv("FORMULARIO_APROVADO_DESENVOLVEDOR_CHANNEL_ID")
        if not approved_channel_env:
            await interaction.followup.send("Canal de aprovados não configurado.", ephemeral=True)
            # tenta reverter caso algo tenha saído estranho (remoção já feita)
            try:
                s = SessionLocal()
                # remove aprovado criado e recria o original
                if aprovado_id is not None:
                    to_del = s.query(FormulariosDesenvolvedorAprovados).get(aprovado_id)
                    if to_del:
                        s.delete(to_del)
                recreated = FormulariosDesenvolvedor(**original_data)
                s.add(recreated)
                s.commit()
            except Exception:
                s.rollback()
            finally:
                s.close()
            return
        try:
            approved_channel_id = int(approved_channel_env)
        except ValueError:
            await interaction.followup.send("ID do canal de aprovados inválido.", ephemeral=True)
            # reverter DB
            try:
                s = SessionLocal()
                if aprovado_id is not None:
                    to_del = s.query(FormulariosDesenvolvedorAprovados).get(aprovado_id)
                    if to_del:
                        s.delete(to_del)
                recreated = FormulariosDesenvolvedor(**original_data)
                s.add(recreated)
                s.commit()
            except Exception:
                s.rollback()
            finally:
                s.close()
            return

        approved_channel = self.bot.get_channel(approved_channel_id)
        if approved_channel is None:
            await interaction.followup.send("Não encontrei o canal de aprovados configurado.", ephemeral=True)
            # reverter DB
            try:
                s = SessionLocal()
                if aprovado_id is not None:
                    to_del = s.query(FormulariosDesenvolvedorAprovados).get(aprovado_id)
                    if to_del:
                        s.delete(to_del)
                recreated = FormulariosDesenvolvedor(**original_data)
                s.add(recreated)
                s.commit()
            except Exception:
                s.rollback()
            finally:
                s.close()
            return

        # Envia a mensagem ao canal de aprovados (somente se DB já foi movido com sucesso)
        try:
            if embed:
                new_embed = discord.Embed(
                    title=embed.title if getattr(embed, "title", None) else None,
                    description=embed.description if getattr(embed, "description", None) else None,
                    colour=discord.Colour.from_str("#00ff40")
                )
                for f in embed.fields:
                    new_embed.add_field(name=f.name, value=f.value, inline=f.inline)
                new_embed.add_field(name="\u200b", value="", inline=False)
                new_embed.add_field(name=f"**Aprovado Por:** `{approver_apelido}`", value="", inline=False)
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
                new_embed.add_field(name="\u200b", value="", inline=False)
                new_embed.add_field(name=f"**Aprovado Por:** `{approver_apelido}`", value="", inline=False)
                new_embed.set_image(url="https://i.ibb.co/gZn6mfHS/formulario-aprovado-imagem.png")

            new_msg = await approved_channel.send(content=content, embed=new_embed)
        except Exception as e:
            print(f"Erro ao enviar a mensagem para o canal de aprovados: {e}")
            # tentativa de reversão no banco: remover o aprovado e recriar o original
            try:
                s = SessionLocal()
                if aprovado_id is not None:
                    to_del = s.query(FormulariosDesenvolvedorAprovados).get(aprovado_id)
                    if to_del:
                        s.delete(to_del)
                recreated = FormulariosDesenvolvedor(**original_data)
                s.add(recreated)
                s.commit()
            except Exception:
                s.rollback()
            finally:
                s.close()
            await interaction.followup.send("Erro ao enviar a mensagem para o canal de aprovados. A ação foi revertida.", ephemeral=True)
            return

        # Atualiza o registro aprovado com o id da mensagem enviada
        try:
            s = SessionLocal()
            approved_rec = s.query(FormulariosDesenvolvedorAprovados).get(aprovado_id)
            if approved_rec:
                approved_rec.id_mensagem = str(new_msg.id)
                s.add(approved_rec)
                s.commit()
        except Exception as e:
            s.rollback()
            print(f"Erro ao atualizar id_mensagem do formulário aprovado: {e}")
            # tenta remover a mensagem enviada para evitar inconsistência
            try:
                await new_msg.delete()
            except Exception:
                pass
            await interaction.followup.send("Erro ao atualizar o formulário aprovado no banco de dados.", ephemeral=True)
            return
        finally:
            s.close()

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

        # Atualiza cargos do usuário aprovado
        cargo_aviso = None
        guild = interaction.guild
        if guild is not None:
            visitante_env = os.getenv("VISITANTE_CARGO_ID")
            membro_env = os.getenv("MEMBRO_CARGO_ID")
            try:
                visitante_cargo_id = int(visitante_env) if visitante_env else 0
                membro_cargo_id = int(membro_env) if membro_env else 0
            except ValueError:
                visitante_cargo_id = 0
                membro_cargo_id = 0
                cargo_aviso = "IDs de cargo (VISITANTE_CARGO_ID/MEMBRO_CARGO_ID) inválidos no .env."

            if (visitante_cargo_id or membro_cargo_id) and cargo_aviso is None:
                try:
                    target_user_id = int(original_data.get("id_usuario") or 0)
                    target_member = guild.get_member(target_user_id) if target_user_id else None
                    if target_member is None and target_user_id:
                        try:
                            target_member = await guild.fetch_member(target_user_id)
                        except Exception:
                            target_member = None

                    if target_member is None:
                        cargo_aviso = "Não consegui encontrar o usuário no servidor para atualizar os cargos."
                    else:
                        visitante_role = guild.get_role(visitante_cargo_id) if visitante_cargo_id else None
                        membro_role = guild.get_role(membro_cargo_id) if membro_cargo_id else None

                        # Remove visitante (se existir) e adiciona membro (se existir)
                        if visitante_role and visitante_role in target_member.roles:
                            await target_member.remove_roles(visitante_role, reason="Formulário aprovado")
                        if membro_role and membro_role not in target_member.roles:
                            await target_member.add_roles(membro_role, reason="Formulário aprovado")
                except discord.Forbidden:
                    cargo_aviso = "Sem permissão para gerenciar cargos (verifique 'Gerenciar Cargos' e hierarquia)."
                except Exception as e:
                    print(f"Erro ao atualizar cargos do usuário aprovado: {e}")
                    cargo_aviso = "Erro ao atualizar os cargos do usuário aprovado."

                # Enviar mensagem ao usuário aprovado (DM)
                try:
                    target_user_id = int(original_data.get("id_usuario") or 0)
                    user_obj = None
                    # se encontramos o membro no guild, preferimos usar esse objeto
                    if guild is not None and 'target_member' in locals() and target_member is not None:
                        user_obj = target_member
                    else:
                        try:
                            user_obj = self.bot.get_user(target_user_id) or await self.bot.fetch_user(target_user_id)
                        except Exception:
                            user_obj = None

                    if user_obj is not None:
                        membro_mention = getattr(user_obj, 'mention', f"<@{target_user_id}>")
                        embed_aprovado = discord.Embed(
                            title="<:formulario_aprovado:1469811985364291634>  Formulário Aprovado!",
                            description=(
                                f"Parabéns {membro_mention}, seu formulário para se tornar um membro da nossa comunidade foi **aprovado**! <a:gg_gif_1:1469820399159083161>\n\n"
                                "Seja muito bem-vindo(a)! Agora você tem acesso aos canais exclusivos para membros.\n"
                                "Sinta-se à vontade para interagir, tirar dúvidas e participar das atividades.\n\n"
                                "<:aviso_1:1469818296848093286> **Próximo passo:** Leia as regras da comunidade e as informações presentes nos seguintes canais:\n 1. https://discord.com/channels/1452819645575991409/1452830800818212874\n 2. https://discord.com/channels/1452819645575991409/1452932256887865498\n\n"
                                "<a:anuncio_1:1469811972114616399> É muito **importante** fazer isso! Pois fazer isso garante um melhor ambiente de desenvolvimento para todos!"
                            ),
                            colour=discord.Colour.from_str("#00ff40")
                        )
                        embed_aprovado.set_image(url="https://i.ibb.co/gZn6mfHS/formulario-aprovado-imagem.png")
                        try:
                            await user_obj.send(embed=embed_aprovado)
                        except Exception:
                            # não bloquear a aprovação se DM falhar
                            pass
                except Exception:
                    pass

        msg = "<:membro_aprovado:1469811980117344502> **Formulário Aprovado!**\nUma mensagem foi enviada ao usuario com informações iniciais da comunidade."
        if cargo_aviso:
            msg += f"\n\n**Aviso:** {cargo_aviso}"

        await interaction.followup.send(msg, ephemeral=True)
        
        # [HOOK] Atualiza o nome do canal (Removeu 1 da lista)
        agendar_atualizacao_canal(self.bot)

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
            member = None
            # tenta resolver via guild (get_member ou fetch_member)
            guild = interaction.guild or (interaction.message.guild if getattr(interaction, "message", None) else None)
            if guild is not None:
                try:
                    member = guild.get_member(interaction.user.id)
                except Exception:
                    member = None
                if member is None:
                    try:
                        member = await guild.fetch_member(interaction.user.id)
                    except Exception:
                        member = None

        if not member or not any(role.id == admin_cargo_id for role in getattr(member, "roles", [])):
            await interaction.response.send_message("Você não tem permissão para fazer isso.", ephemeral=True)
            return

        reviewer_apelido = getattr(member, "display_name", str(member))
        modal = MotivoRejeicaoModal(
            parent_view=self,
            bot=self.bot,
            message_id=int(interaction.message.id),
            channel_id=int(interaction.channel.id),
            reviewer_display_name=reviewer_apelido,
        )
        await interaction.response.send_modal(modal)

    async def _process_rejection(
        self,
        interaction: discord.Interaction,
        *,
        message_id: int,
        channel_id: int,
        reviewer_apelido: str,
        motivo: str,
    ):
        # Verifica se quem submeteu o modal possui o cargo de administrador
        admin_cargo_id = os.getenv("ADMINISTRADOR_CARGO_ID")
        if not admin_cargo_id:
            try:
                await interaction.response.send_message("Cargo administrador não configurado.", ephemeral=True)
            except Exception:
                pass
            return
        try:
            admin_cargo_id = int(admin_cargo_id)
        except ValueError:
            try:
                await interaction.response.send_message("Cargo administrador inválido.", ephemeral=True)
            except Exception:
                pass
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            try:
                member = interaction.guild.get_member(member.id)
            except Exception:
                member = None
        if not member or not any(role.id == admin_cargo_id for role in getattr(member, "roles", [])):
            try:
                await interaction.response.send_message("Você não tem permissão para rejeitar.", ephemeral=True)
            except Exception:
                pass
            return
        old_message_id = str(message_id)

        # Busca a mensagem original (modal submit não tem interaction.message)
        source_channel = self.bot.get_channel(int(channel_id))
        if source_channel is None:
            try:
                source_channel = await self.bot.fetch_channel(int(channel_id))
            except Exception:
                source_channel = None
        if source_channel is None:
            await interaction.followup.send("Não encontrei o canal original do formulário.", ephemeral=True)
            return

        try:
            source_message = await source_channel.fetch_message(int(message_id))
        except Exception:
            source_message = None

        embed = source_message.embeds[0] if (source_message and source_message.embeds) else None
        content = source_message.content if (source_message and not embed) else None

        motivo_deve_aparecer = self._motivo_deve_aparecer(motivo)
        motivo_block = None
        if motivo_deve_aparecer:
            motivo_sanitizado = motivo.replace("```", "` ` `")
            motivo_block = f"```{motivo_sanitizado}```"

        # No canal de rejeitados, o campo Motivo deve sempre aparecer.
        motivo_canal_txt = (motivo or "").strip()
        if not motivo_canal_txt or motivo_canal_txt.casefold() in {"não informado", "nao informado"}:
            motivo_canal_txt = "Não Informado"
        motivo_canal_txt = motivo_canal_txt.replace("```", "` ` `")
        motivo_block_canal = f"```{motivo_canal_txt}```"

        # Busca o formulário original e valida
        session = SessionLocal()
        try:
            form = session.query(FormulariosDesenvolvedor).filter_by(id_mensagem=old_message_id).first()
            if not form:
                await interaction.followup.send("Formulário não encontrado.", ephemeral=True)
                return
            if form.status != "pendente":
                await interaction.followup.send("Formulário já foi avaliado.", ephemeral=True)
                return

            # remove marcação de "ativo" do usuário (se a tabela existir)
            if FormulariosAtivos is not None:
                try:
                    session.query(FormulariosAtivos).filter_by(id_usuario=str(form.id_usuario)).delete(synchronize_session=False)
                except Exception:
                    pass

            original_data = {
                "id_usuario": form.id_usuario,
                "id_mensagem": form.id_mensagem,
                "nome": form.nome,
                "sexo": form.sexo,
                "genero_favorito": form.genero_favorito,
                "plataforma_principal": form.plataforma_principal,
                "redes_sociais": form.redes_sociais,
                "status": form.status,
                "data_envio": form.data_envio,
            }

            rejeitado = FormulariosDesenvolvedorRejeitados(
                id_usuario=int(form.id_usuario),
                id_mensagem="",
                nome=form.nome,
                sexo=form.sexo,
                genero_favorito=form.genero_favorito,
                plataforma_principal=form.plataforma_principal,
                redes_sociais=form.redes_sociais,
                motivo=motivo,
                status="rejeitado",
                data_envio=form.data_envio,
                rejeitado_por=reviewer_apelido,
                data_rejeicao=datetime.utcnow(),
            )
            session.add(rejeitado)
            session.delete(form)
            session.commit()
            rejeitado_id = getattr(rejeitado, "id", None)
        except Exception as e:
            session.rollback()
            session.close()
            print(f"Erro ao mover formulário rejeitado no banco de dados: {e}")
            await interaction.followup.send("Erro ao mover formulário no banco de dados.", ephemeral=True)
            return
        finally:
            session.close()

        rejected_channel_env = os.getenv("FORMULARIO_REJEITADO_DESENVOLVEDOR_CHANNEL_ID")
        if not rejected_channel_env:
            await interaction.followup.send("Canal de rejeitados não configurado.", ephemeral=True)
            try:
                s = SessionLocal()
                if rejeitado_id is not None:
                    to_del = s.query(FormulariosDesenvolvedorRejeitados).get(rejeitado_id)
                    if to_del:
                        s.delete(to_del)
                s.add(FormulariosDesenvolvedor(**original_data))
                s.commit()
            except Exception:
                s.rollback()
            finally:
                s.close()
            return
        try:
            rejected_channel_id = int(rejected_channel_env)
        except ValueError:
            await interaction.followup.send("ID do canal de rejeitados inválido.", ephemeral=True)
            try:
                s = SessionLocal()
                if rejeitado_id is not None:
                    to_del = s.query(FormulariosDesenvolvedorRejeitados).get(rejeitado_id)
                    if to_del:
                        s.delete(to_del)
                s.add(FormulariosDesenvolvedor(**original_data))
                s.commit()
            except Exception:
                s.rollback()
            finally:
                s.close()
            return

        rejected_channel = self.bot.get_channel(rejected_channel_id)
        if rejected_channel is None:
            await interaction.followup.send("Não encontrei o canal de rejeitados configurado.", ephemeral=True)
            try:
                s = SessionLocal()
                if rejeitado_id is not None:
                    to_del = s.query(FormulariosDesenvolvedorRejeitados).get(rejeitado_id)
                    if to_del:
                        s.delete(to_del)
                s.add(FormulariosDesenvolvedor(**original_data))
                s.commit()
            except Exception:
                s.rollback()
            finally:
                s.close()
            return

        # Envia a mensagem ao canal de rejeitados
        try:
            if embed:
                new_embed = discord.Embed(
                    title=embed.title if getattr(embed, "title", None) else None,
                    description=embed.description if getattr(embed, "description", None) else None,
                    colour=discord.Colour.from_str("#d40000"),
                )
                for f in embed.fields:
                    new_embed.add_field(name=f.name, value=f.value, inline=f.inline)
                new_embed.add_field(name="\u200b", value="", inline=False)
                new_embed.add_field(name=f"**Rejeitado Por:** `{reviewer_apelido}`", value="", inline=False)
                new_embed.add_field(name="**Motivo:**", value=motivo_block_canal, inline=False)
                if getattr(embed, "thumbnail", None) and getattr(embed.thumbnail, "url", None):
                    new_embed.set_thumbnail(url=embed.thumbnail.url)
                if getattr(embed, "author", None) and getattr(embed.author, "name", None):
                    try:
                        new_embed.set_author(name=embed.author.name, icon_url=getattr(embed.author, "icon_url", None))
                    except Exception:
                        pass
                if getattr(embed, "footer", None) and getattr(embed.footer, "text", None):
                    new_embed.set_footer(text=embed.footer.text)
                new_embed.set_image(url="https://i.ibb.co/sJ38G3VN/formulario-rejeitado-imagem.png")
            else:
                new_embed = discord.Embed(colour=discord.Colour.from_str("#d40000"))
                new_embed.add_field(name="\u200b", value="", inline=False)
                new_embed.add_field(name=f"**Rejeitado Por:** `{reviewer_apelido}`", value="", inline=False)
                new_embed.add_field(name="**Motivo:**", value=motivo_block_canal, inline=False)
                new_embed.set_image(url="https://i.ibb.co/sJ38G3VN/formulario-rejeitado-imagem.png")

            new_msg = await rejected_channel.send(content=content, embed=new_embed)
        except Exception as e:
            print(f"Erro ao enviar a mensagem para o canal de rejeitados: {e}")
            try:
                s = SessionLocal()
                if rejeitado_id is not None:
                    to_del = s.query(FormulariosDesenvolvedorRejeitados).get(rejeitado_id)
                    if to_del:
                        s.delete(to_del)
                s.add(FormulariosDesenvolvedor(**original_data))
                s.commit()
            except Exception:
                s.rollback()
            finally:
                s.close()
            await interaction.followup.send(
                "Erro ao enviar a mensagem para o canal de rejeitados. A ação foi revertida.",
                ephemeral=True,
            )
            return

        # Atualiza o registro rejeitado com o id da mensagem enviada
        try:
            s = SessionLocal()
            rejected_rec = s.query(FormulariosDesenvolvedorRejeitados).get(rejeitado_id)
            if rejected_rec:
                rejected_rec.id_mensagem = str(new_msg.id)
                s.add(rejected_rec)
                s.commit()
        except Exception as e:
            s.rollback()
            print(f"Erro ao atualizar id_mensagem do formulário rejeitado: {e}")
            try:
                await new_msg.delete()
            except Exception:
                pass
            await interaction.followup.send("Erro ao atualizar o formulário rejeitado no banco de dados.", ephemeral=True)
            return
        finally:
            s.close()

        # Envia DM ao usuário informando a rejeição (falha aqui não deve quebrar o fluxo)
        dm_enviada = False
        try:
            user_id_int = int(original_data.get("id_usuario"))
        except Exception:
            user_id_int = None

        if user_id_int is not None:
            try:
                try:
                    user_obj = self.bot.get_user(user_id_int) or await self.bot.fetch_user(user_id_int)
                except Exception:
                    user_obj = None

                if user_obj is not None:
                    desc = (
                        f"Olá {user_obj.mention}, infelizmente seu formulário para se tornar um membro da nossa comunidade foi **rejeitado**! <:f_key_2:1469811974736183503>\n\n"
                    )
                    if motivo_deve_aparecer:
                        desc += f"**Motivo:**\n{motivo_block}\n"
                    desc += (
                        "Isso pode ter ocorrido por não atender aos critérios necessários ou por informações incompletas.\n\n"
                        "Mas não desanime! Você pode revisar suas respostas, conferir o motivo da rejeição (caso informado) e **enviar um novo formulário** quando estiver pronto.\n\n"
                        "Se tiver dúvidas sobre o motivo da rejeição, sinta-se à vontade para entrar em contato com a nossa equipe."
                    )

                    formulario_rejeitado_embed = discord.Embed(
                        title="<:formulario_rejeitado:1469811981228834823>  Formulário Rejeitado!",
                        description=desc,
                        colour=discord.Colour.from_str("#d40000"),
                    )
                    try:
                        formulario_rejeitado_embed.set_image(
                            url="https://i.ibb.co/sJ38G3VN/formulario-rejeitado-imagem.png"
                        )
                    except Exception:
                        pass

                    await user_obj.send(embed=formulario_rejeitado_embed)
                    dm_enviada = True
            except Exception as e:
                print(f"Erro ao enviar DM de rejeição: {e}")

        # Exclui a mensagem original
        if source_message is not None:
            try:
                await source_message.delete()
            except Exception:
                pass

        if dm_enviada:
            await interaction.followup.send("<:membro_rejeitado:1469813189259694100> **Formulário Rejeitado!**\nUma mensagem foi enviada ao usuário informando a rejeição.", ephemeral=True)
        else:
            await interaction.followup.send("<:membro_rejeitado:1469813189259694100> **Formulário Rejeitado!**\nUma mensagem foi enviada ao usuário informando a rejeição.", ephemeral=True)
        
        # [HOOK] Atualiza o nome do canal (Removeu 1 da lista)
        agendar_atualizacao_canal(self.bot)

class registrar_usuario(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()
        # [NOVO] Variável para armazenar a tarefa de atualização (Debounce)
        self.channel_rename_task = None
        # [NOVO] Guarda o momento (timestamp) em que será permitido renomear novamente
        self.next_allowed_rename_time = 0 

    # [NOVO] Método para agendar a atualização com debounce e fila inteligente
    def schedule_channel_rename(self):
        # Se já existe uma tarefa agendada, cancela para reiniciar o timer
        if self.channel_rename_task and not self.channel_rename_task.done():
            self.channel_rename_task.cancel()
        
        # Cria uma nova tarefa no loop de eventos
        self.channel_rename_task = self.bot.loop.create_task(self._perform_channel_rename())

    # [NOVO] Lógica principal de atualização
    async def _perform_channel_rename(self):
        try:
            # 1. Debounce Inicial: Espera 60 segundos para agrupar ações rápidas
            await asyncio.sleep(60)

            # 2. Verifica o Rate Limit de 10 minutos (600 segundos)
            now = time.time()
            if now < self.next_allowed_rename_time:
                wait_time = self.next_allowed_rename_time - now
                # Se ainda não passou o tempo seguro, dorme o restante
                print(f"⏳ Rate Limit Discord: Aguardando mais {int(wait_time)}s para renomear o canal...")
                await asyncio.sleep(wait_time)

            # --- ATUALIZAÇÃO ---
            channel_id_env = os.getenv("FORMULARIO_PENDENTE_DESENVOLVEDOR_CHANNEL_ID")
            if not channel_id_env: return
            try:
                channel_id = int(channel_id_env)
            except ValueError: return

            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not channel: return

            # Ler IDs do Banco de Dados
            session = SessionLocal()
            db_message_ids = set()
            try:
                # Pega todos os pendentes da tabela principal
                forms = session.query(FormulariosDesenvolvedor.id_mensagem).filter_by(status="pendente").all()
                db_message_ids = {str(f.id_mensagem) for f in forms if f.id_mensagem}
            except Exception as e:
                print(f"Erro ao ler banco: {e}")
                return
            finally:
                session.close()

            # Contar mensagens reais no canal
            count = 0
            async for message in channel.history(limit=None):
                if str(message.id) in db_message_ids:
                    count += 1
            
            new_name = f"📘・pendentes-{count}"
            
            # Só gasta a requisição da API se o nome realmente mudou
            if channel.name != new_name:
                await channel.edit(name=new_name)
                # print(f"✅ Canal renomeado para: {new_name}")
                
                # Define que a próxima renomeação só pode ocorrer daqui a 10 min + 10 seg de folga
                self.next_allowed_rename_time = time.time() + 610
            else:
                pass

        except asyncio.CancelledError:
            # Tarefa cancelada pois entrou nova ação; a nova tarefa assume.
            pass
        except Exception as e:
            print(f"Erro crítico ao renomear canal: {e}")

    @staticmethod
    async def _cleanup_aprovado_se_visitante(
        interaction: discord.Interaction,
        session,
        user_id_int: int,
    ) -> bool:
        """Se o usuário tiver registro aprovado, mas ainda estiver com cargo de visitante,
        remove o registro aprovado para permitir um novo envio.

        Retorna True quando removeu algo.
        """
        visitante_env = os.getenv("VISITANTE_CARGO_ID")
        if not visitante_env:
            return False
        try:
            visitante_cargo_id = int(visitante_env)
        except ValueError:
            return False
        if not visitante_cargo_id:
            return False

        guild = interaction.guild
        if guild is None:
            return False

        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None:
            try:
                member = guild.get_member(user_id_int)
            except Exception:
                member = None
        if member is None:
            try:
                member = await guild.fetch_member(user_id_int)
            except Exception:
                member = None
        if member is None:
            return False

        tem_visitante = any(getattr(r, "id", None) == visitante_cargo_id for r in getattr(member, "roles", []))
        if not tem_visitante:
            return False

        try:
            deletados = (
                session.query(FormulariosDesenvolvedorAprovados)
                .filter_by(id_usuario=int(user_id_int))
                .delete(synchronize_session=False)
            )
            if deletados:
                session.commit()
                return True
        except Exception as e:
            session.rollback()
            print(f"[registrar_usuario] Erro ao limpar aprovado (visitante): {e}")
        return False

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
                max_length=50
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
                required=True,
                max_length=200,
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
            user_id = str(interaction.user.id)
            user_id_int = int(interaction.user.id)

            # (novo) bloqueia se o usuário já tiver um formulário aprovado
            session = SessionLocal()
            try:
                ja_aprovado = session.query(FormulariosDesenvolvedorAprovados).filter_by(id_usuario=user_id_int).first()
                if ja_aprovado:
                    limpou = await registrar_usuario._cleanup_aprovado_se_visitante(interaction, session, user_id_int)
                    if not limpou:
                        await interaction.response.send_message(
                            "<:formulario_aprovado:1469811985364291634> Você já possui um formulário **aprovado** e não pode enviar um novo.",
                            ephemeral=True,
                        )
                        return

                # (novo) bloqueia se já existir formulário ativo/pendente para o usuário
                if FormulariosAtivos is not None:
                    existente = session.query(FormulariosAtivos).filter_by(id_usuario=user_id).first()
                else:
                    # fallback: usa a própria tabela de formulários pendentes
                    existente = (
                        session.query(FormulariosDesenvolvedor)
                        .filter_by(id_usuario=user_id, status="pendente")
                        .first()
                    )

                if existente:
                    await interaction.response.send_message(
                        "<:formulario_pendente:1469811982549913670> Você já possui um formulário em **análise**. Você será notificado quando houver uma atualização sobre seu formulário.",
                        ephemeral=True,
                    )
                    return
            finally:
                session.close()

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
                    id_usuario=str(interaction.user.id),
                    id_mensagem=str(msg.id),
                    nome=nome,
                    sexo=sexo,
                    genero_favorito=genero,
                    plataforma_principal=plataforma or "Não Informado",
                    redes_sociais=redes,
                    status="pendente",
                    data_envio=datetime.utcnow()
                )
                session.add(form)

                # (novo/opcional) cria marcação de "ativo" (ajuste os campos conforme seu modelo)
                if FormulariosAtivos is not None:
                    try:
                        session.add(FormulariosAtivos(id_usuario=user_id))
                    except Exception:
                        # não quebra caso o modelo exija colunas extras
                        pass

                session.commit()
            except Exception:
                session.rollback()
                await interaction.response.send_message("Erro ao salvar no banco de dados.", ephemeral=True)
                return
            finally:
                session.close()

            await interaction.response.send_message("**Formulário enviado com sucesso!**\nAgora aguarde até que um membro da nossa equipe analise seu formulario.", ephemeral=True)
            
            # [HOOK] Atualiza o nome do canal (Adicionou 1 na lista)
            agendar_atualizacao_canal(self.bot)

    class Registrar_Usurario_View(discord.ui.View):
        def __init__(self, bot: commands.Bot, *, timeout: float = None):
            super().__init__(timeout=timeout)
            self.bot = bot

        @discord.ui.button(label="Registrar-se", style=discord.ButtonStyle.primary, custom_id="registrar_se_button")
        async def registrar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = str(interaction.user.id)
            user_id_int = int(interaction.user.id)

            session = SessionLocal()
            try:
                ja_aprovado = session.query(FormulariosDesenvolvedorAprovados).filter_by(id_usuario=user_id_int).first()
                if ja_aprovado:
                    limpou = await registrar_usuario._cleanup_aprovado_se_visitante(interaction, session, user_id_int)
                    if not limpou:
                        await interaction.response.send_message(
                            "<:formulario_aprovado:1469811985364291634> Você já possui um formulário **aprovado** e não pode enviar um novo.",
                            ephemeral=True,
                        )
                        return

                if FormulariosAtivos is not None:
                    existente = session.query(FormulariosAtivos).filter_by(id_usuario=user_id).first()
                else:
                    existente = (
                        session.query(FormulariosDesenvolvedor)
                        .filter_by(id_usuario=user_id, status="pendente")
                        .first()
                    )

                if existente:
                    await interaction.response.send_message(
                        "<:formulario_pendente:1469811982549913670> Você já possui um formulário em **análise**. Você será notificado quando houver uma atualização sobre seu formulário.",
                        ephemeral=True,
                    )
                    return
            finally:
                session.close()

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

            user_id = str(interaction.user.id)
            user_id_int = int(interaction.user.id)

            session = SessionLocal()
            try:
                ja_aprovado = session.query(FormulariosDesenvolvedorAprovados).filter_by(id_usuario=user_id_int).first()
                if ja_aprovado:
                    limpou = await registrar_usuario._cleanup_aprovado_se_visitante(interaction, session, user_id_int)
                    if not limpou:
                        await interaction.response.send_message(
                            "<:formulario_aprovado:1469811985364291634> Você já possui um formulário **aprovado** e não pode enviar um novo.",
                            ephemeral=True,
                        )
                        return

                if FormulariosAtivos is not None:
                    existente = session.query(FormulariosAtivos).filter_by(id_usuario=user_id).first()
                else:
                    existente = (
                        session.query(FormulariosDesenvolvedor)
                        .filter_by(id_usuario=user_id, status="pendente")
                        .first()
                    )

                if existente:
                    await interaction.response.send_message(
                        "<:formulario_pendente:1469811982549913670> Você já possui um formulário em **análise**. Você será notificado quando houver uma atualização sobre seu formulário.",
                        ephemeral=True,
                    )
                    return
            finally:
                session.close()

            modal = registrar_usuario.Registrar_Usurario_Modal(self.bot)
            await interaction.response.send_modal(modal)
        except Exception:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("**ERRO interno ao processar interação.**", ephemeral=True)
            except Exception:
                pass
            raise

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Ao detectar que um membro saiu do servidor, remove qualquer formulário aprovado dele."""
        try:
            s = SessionLocal()
            try:
                aprovados = s.query(FormulariosDesenvolvedorAprovados).filter_by(id_usuario=int(member.id)).all()
                if aprovados:
                    for a in aprovados:
                        s.delete(a)
                    s.commit()
            except Exception as e:
                s.rollback()
                print(f"[registrar_usuario] Erro ao remover formulário aprovado ao sair do servidor: {e}")
            finally:
                s.close()
        except Exception:
            pass

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
    # Registra a View como persistente para que botões antigos continuem funcionando após reiniciar.
    # Os custom_id precisam ser fixos (já são: aprovar_button / rejeitar_button) e o timeout deve ser None.
    try:
        bot.add_view(BotoesFormulario(bot, timeout=None))
    except Exception as e:
        print(f"[registrar_usuario] Falha ao registrar BotoesFormulario como view persistente: {e}")
    # Inicia a tarefa que registra a view persistente (opcional)
    bot.loop.create_task(cog.registrar_view())