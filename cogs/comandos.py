import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from pathlib import Path
import re
import os

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

    # comando /limpar-dm (comando para apagar mensagens do bot na DM)
    @app_commands.command(
        name="limpar-dm",
        description="Apaga todas as mensagens enviadas pelo bot na DM."
    )
    async def limpar_chat(self, interaction: discord.Interaction):
        # Só permitir na DM com o bot
        if interaction.guild is not None:
            await interaction.response.send_message("Use este comando na DM com o bot.", ephemeral=True)
            return

        class ConfirmarLimparDMView(discord.ui.View):
            def __init__(self, bot: commands.Bot, requester_id: int):
                super().__init__(timeout=60)
                self.bot = bot
                self.requester_id = requester_id

            async def interaction_check(self, i: discord.Interaction) -> bool:
                # Só quem executou o comando pode clicar
                if i.user.id != self.requester_id:
                    await i.response.send_message("Só você pode usar estes botões.", ephemeral=True)
                    return False
                return True

            @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.success)
            async def confirmar(self, i: discord.Interaction, _: discord.ui.Button):
                for item in self.children:
                    item.disabled = True

                embed_andamento = discord.Embed(
                    title="Limpando DM…",
                    description="Apagando minhas mensagens nesta conversa. Isso pode levar um tempo.",
                    color=discord.Color.orange(),
                )
                await i.response.edit_message(embed=embed_andamento, view=self)

                channel = i.channel
                apagadas = 0

                # DM não suporta bulk delete. Se deletarmos muito rápido,
                # o Discord retorna 429 e o discord.py loga warnings.
                # Um pequeno delay fixo evita estourar o rate limit.
                delete_delay_seconds = 0.75

                async for msg in channel.history(limit=None, oldest_first=False):
                    if msg.author and msg.author.id == self.bot.user.id:
                        try:
                            await msg.delete()
                            apagadas += 1
                            await asyncio.sleep(delete_delay_seconds)
                        except (discord.NotFound, discord.Forbidden):
                            # Mensagem já foi apagada ou não temos permissão.
                            await asyncio.sleep(delete_delay_seconds)
                        except discord.HTTPException:
                            # Em caso de falha (incluindo rate limit), desacelera um pouco mais.
                            await asyncio.sleep(max(1.25, delete_delay_seconds))

                embed_final = discord.Embed(
                    title="Pronto.",
                    description=f"Apaguei **{apagadas}** mensagens minhas nesta DM.",
                    color=discord.Color.from_rgb(0, 255, 0),
                )
                await i.edit_original_response(embed=embed_final, view=None)

            @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.danger)
            async def cancelar(self, i: discord.Interaction, _: discord.ui.Button):
                for item in self.children:
                    item.disabled = True

                embed_cancelado = discord.Embed(
                    title="Cancelado.",
                    description="Nada foi apagado.",
                    color=discord.Color.from_rgb(255, 0, 0),
                )
                await i.response.edit_message(embed=embed_cancelado, view=self)

        embed = discord.Embed(
            title="Confirmar limpeza do chat?",
            description="Isso vai apagar **todas as mensagens que EU enviei** nesta DM.\n"
                        "Eu não consigo apagar mensagens enviadas por você.",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(
            embed=embed,
            view=ConfirmarLimparDMView(self.bot, interaction.user.id),
            ephemeral=True
        )

    @app_commands.command(
        name="set-canal-regras",
        description="Envia as regras no canal onde o comando for usado"
    )
    async def set_canal_regras(self, interaction: discord.Interaction):
        # Só pode ser usado em servidor
        if interaction.guild is None:
            await interaction.response.send_message("Use este comando em um servidor (canal de texto).", ephemeral=True)
            return

        # Checa se variável ADMINISTRADOR_CARGO_ID está definida no .env
        admin_env = os.getenv('ADMINISTRADOR_CARGO_ID')
        if not admin_env:
            await interaction.response.send_message("A variável de ambiente `ADMINISTRADOR_CARGO_ID` não está configurada.", ephemeral=True)
            return
        m = re.search(r"(\d+)", admin_env)
        if not m:
            await interaction.response.send_message("Valor inválido em `ADMINISTRADOR_CARGO_ID`.", ephemeral=True)
            return
        admin_role_id = int(m.group(1))

        # Recupera o membro no guild para checar os cargos
        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(interaction.user.id)
            except Exception:
                member = interaction.user

        role_obj = interaction.guild.get_role(admin_role_id)
        role_name = role_obj.name if role_obj else f'ID {admin_role_id}'

        if isinstance(member, discord.Member):
            has_role = any(r.id == admin_role_id for r in member.roles)
        else:
            has_role = False

        if not has_role:
            await interaction.response.send_message(f"Você precisa do cargo `{role_name}` para usar este comando.", ephemeral=True)
            return

        # Envia confirmação ephemeral ao usuário
        await interaction.response.send_message("Canal de regras foi definido com sucesso. As regras serão enviadas neste canal", ephemeral=True)

        # Envia a view/container no canal onde o comando foi usado
        view = Components()
        channel = interaction.channel
        try:
            await channel.send(view=view)
            # salva o id do canal numa variável de módulo
            global REGRAS_CHANNEL_ID
            REGRAS_CHANNEL_ID = channel.id

            # Atualiza o arquivo .env no diretório raiz do projeto
            try:
                env_path = Path(__file__).resolve().parent.parent / '.env'
                if env_path.exists():
                    content = env_path.read_text(encoding='utf-8')
                    if re.search(r'^REGRAS_CHANNEL_ID=.*$', content, flags=re.MULTILINE):
                        content = re.sub(r"^REGRAS_CHANNEL_ID=.*$", f"REGRAS_CHANNEL_ID='{channel.id}'", content, flags=re.MULTILINE)
                    else:
                        content = content + f"\nREGRAS_CHANNEL_ID='{channel.id}'\n"
                    env_path.write_text(content, encoding='utf-8')
                else:
                    env_path.write_text(f"REGRAS_CHANNEL_ID='{channel.id}'\n", encoding='utf-8')
            except Exception as e:
                try:
                    await interaction.followup.send(f"Erro ao atualizar .env: {e}", ephemeral=True)
                except Exception:
                    pass
        except Exception as e:
            # tenta notificar o usuário via followup se houver erro
            try:
                await interaction.followup.send(f"Falha ao enviar mensagem no canal: {e}", ephemeral=True)
            except Exception:
                pass

class Components(discord.ui.LayoutView):
    container1 = discord.ui.Container(
        discord.ui.Section(
            discord.ui.TextDisplay(content="**REGRAS DO SERVIDOR**"),
            discord.ui.TextDisplay(content="\u200b"),
            discord.ui.TextDisplay(content="Fique por dentro das nossas regras de convivência! \nLeia atentamente para garantir a melhor experiência na comunidade."),
            accessory=discord.ui.Thumbnail(
                media="https://i.ibb.co/bgnn4m7h/imagem-regras-icon.png",
            ),
        ),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="**1. Postura e Ética Profissional**\n<:seta_referente:1468405685963198528> **1.1. Postura Ética:** Todos os membros devem manter postura ética, respeitosa e profissional durante períodos de desenvolvimento.\n<:seta_referente:1468405685963198528> **1.2. Respeito Mútuo:** Não serão toleradas atitudes ofensivas, desrespeitosas ou comportamentos incompatíveis com ambiente corporativo.\n<:seta_referente:1468405685963198528> **1.3. Debate Técnico:** Divergências técnicas devem ser tratadas de forma objetiva e construtiva."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="**2. Comunicação Institucional**\n<:seta_referente:1468405685963198528> **2.1. Uso de Canais:** Cada canal deve ser utilizado conforme sua finalidade.\n<:seta_referente:1468405685963198528> **2.2. Registro de Informações:** Assuntos estratégicos ou técnicos relevantes devem ser registrados de forma clara.\n<:seta_referente:1468405685963198528> **2.3. Documentação Decisória:** Decisões importantes devem ser documentadas para consulta futura.\n<:seta_referente:1468405685963198528> **2.4. Foco e Relevância:** Evitar mensagens irrelevantes ou fora de contexto nos canais operacionais."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="**3. Confidencialidade e Sigilo**\n<:seta_referente:1468405685963198528> **3.1. Proteção de Dados:** Todas as informações, arquivos, códigos-fonte, artes, builds, documentos e estratégias discutidos neste servidor são confidenciais.\n<:seta_referente:1468405685963198528> **3.2. Compartilhamento Restrito:** É expressamente proibido compartilhar qualquer conteúdo interno sem autorização formal da direção.\n<:seta_referente:1468405685963198528> **3.3. Conformidade e Sanções:** A violação de confidencialidade poderá resultar em desligamento imediato e medidas cabíveis."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="**4. Responsabilidades e Prazos**\n<:seta_referente:1468405685963198528> **4.1. Compromisso com Entregas:** Cada membro é responsável pelo cumprimento de suas entregas dentro dos prazos estabelecidos.\n<:seta_referente:1468405685963198528> **4.2. Comunicação de Impedimentos:** Eventuais impedimentos devem ser comunicados previamente à liderança.\n<:seta_referente:1468405685963198528> **4.3. Transparência Profissional:** Comprometimento e transparência são princípios essenciais."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="**5. Segurança da Informação**\n<:seta_referente:1468405685963198528> **5.1. Credenciais de Acesso:** Não compartilhar credenciais de acesso.\n<:seta_referente:1468405685963198528> **5.2. Reporte de Riscos:** Links suspeitos ou potenciais riscos devem ser reportados imediatamente."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="**6. Estrutura Organizacional**\n<:seta_referente:1468405685963198528> **6.1. Liderança e Estratégia:** As decisões estratégicas e de direcionamento de projeto competem à liderança designada.\n<:seta_referente:1468405685963198528> **6.2. Hierarquia e Funções:** A hierarquia e as funções atribuídas devem ser respeitadas."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="**7. Reuniões e Sincronia**\n<:seta_referente:1468405685963198528> **7.1. Pontualidade:** Reuniões agendadas devem ser respeitadas. Em caso de ausência, avise com antecedência.\n<:seta_referente:1468405685963198528> **7.2. Resumos:** Ao final de reuniões de voz, o responsável deve postar um breve resumo das decisões tomadas no canal de texto correspondente."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="**8. Boas Práticas de Ambiente**\n<:seta_referente:1468405685963198528> **8.1. Canais de Descompressão:** Assuntos não relacionados ao trabalho (memes, recomendações, conversas casuais) devem ser restritos aos canais de \"Off-topic\"."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.MediaGallery(
            discord.MediaGalleryItem(
                media="https://i.ibb.co/V4GfrX0/Footers-Discord-bot-1.png",
            ),
        ),
        accent_colour=discord.Colour(16722217),
    )

async def setup(bot):
    await bot.add_cog(comandos(bot))