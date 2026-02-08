import re
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands


class CanalRegras(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
        discord.ui.TextDisplay(content="<:1_vermelho:1469818336383733934>  **Postura e Ética Profissional**\n\n<:seta_referente:1468405685963198528> **1.1. Postura Ética:** Todos os membros devem manter postura ética, respeitosa e profissional durante períodos de desenvolvimento.\n<:seta_referente:1468405685963198528> **1.2. Respeito Mútuo:** Não serão toleradas atitudes ofensivas, desrespeitosas ou comportamentos incompatíveis com ambiente corporativo.\n<:seta_referente:1468405685963198528> **1.3. Debate Técnico:** Divergências técnicas devem ser tratadas de forma objetiva e construtiva."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="<:2_vermelho:1469818337780564221>  **Comunicação Institucional**\n\n<:seta_referente:1468405685963198528> **2.1. Uso de Canais:** Cada canal deve ser utilizado conforme sua finalidade.\n<:seta_referente:1468405685963198528> **2.2. Registro de Informações:** Assuntos estratégicos ou técnicos relevantes devem ser registrados de forma clara.\n<:seta_referente:1468405685963198528> **2.3. Documentação Decisória:** Decisões importantes devem ser documentadas para consulta futura.\n<:seta_referente:1468405685963198528> **2.4. Foco e Relevância:** Evitar mensagens irrelevantes ou fora de contexto nos canais operacionais."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="<:3_vermelho:1469818339781251267>  **Confidencialidade e Sigilo**\n\n<:seta_referente:1468405685963198528> **3.1. Proteção de Dados:** Todas as informações, arquivos, códigos-fonte, artes, builds, documentos e estratégias discutidos neste servidor são confidenciais.\n<:seta_referente:1468405685963198528> **3.2. Compartilhamento Restrito:** É expressamente proibido compartilhar qualquer conteúdo interno sem autorização formal da direção.\n<:seta_referente:1468405685963198528> **3.3. Conformidade e Sanções:** A violação de confidencialidade poderá resultar em desligamento imediato e medidas cabíveis."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="<:4_vermelho:1469818340955394071>  **Responsabilidades e Prazos**\n\n<:seta_referente:1468405685963198528> **4.1. Compromisso com Entregas:** Cada membro é responsável pelo cumprimento de suas entregas dentro dos prazos estabelecidos.\n<:seta_referente:1468405685963198528> **4.2. Comunicação de Impedimentos:** Eventuais impedimentos devem ser comunicados previamente à liderança.\n<:seta_referente:1468405685963198528> **4.3. Transparência Profissional:** Comprometimento e transparência são princípios essenciais."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="<:5_vermelho:1469818341945508123>  **Segurança da Informação**\n\n<:seta_referente:1468405685963198528> **5.1. Credenciais de Acesso:** Não compartilhar credenciais de acesso.\n<:seta_referente:1468405685963198528> **5.2. Reporte de Riscos:** Links suspeitos ou potenciais riscos devem ser reportados imediatamente."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="<:6_vermelho:1469818343622967367>  **Estrutura Organizacional**\n\n<:seta_referente:1468405685963198528> **6.1. Liderança e Estratégia:** As decisões estratégicas e de direcionamento de projeto competem à liderança designada.\n<:seta_referente:1468405685963198528> **6.2. Hierarquia e Funções:** A hierarquia e as funções atribuídas devem ser respeitadas."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="<:7_vermelho:1469818345053225143>  **Reuniões e Sincronia**\n\n<:seta_referente:1468405685963198528> **7.1. Pontualidade:** Reuniões agendadas devem ser respeitadas. Em caso de ausência, avise com antecedência.\n<:seta_referente:1468405685963198528> **7.2. Resumos:** Ao final de reuniões de voz, o responsável deve postar um breve resumo das decisões tomadas no canal de texto correspondente."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.TextDisplay(content="<:8_vermelho:1469818346504716474>  **Boas Práticas de Ambiente**\n\n<:seta_referente:1468405685963198528> **8.1. Canais de Descompressão:** Assuntos não relacionados ao trabalho (memes, recomendações, conversas casuais) devem ser restritos aos canais de \"Off-topic\"."),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        discord.ui.MediaGallery(
            discord.MediaGalleryItem(
                media="https://i.ibb.co/V4GfrX0/Footers-Discord-bot-1.png",
            ),
        ),
        accent_colour=discord.Colour(16722217),
    )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CanalRegras(bot))
