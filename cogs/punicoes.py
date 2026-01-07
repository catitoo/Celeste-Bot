import discord
from discord.ext import commands
from database.setup_database import registrar_punicao
from datetime import timedelta
import os

# Lista de regras
REGRAS = [
    "Regra 01 - Ofensa",
    "Regra 02 - Discriminação ou Atos Depreciativos",
    "Regra 03 - Desordem no Chat",
    "Regra 04 - Desinformação",
    "Regra 05 - Nome ou Perfil Inadequado",
    "Regra 06 - Fugir do Assunto em Tópicos",
    "Regra 07 - Divulgação Simples",
    "Regra 08 - Divulgação Grave",
    "Regra 09 - Falsificação de fatos",
    "Regra 10 - Anti-jogo",
    "Regra 11 - Abuso de Bug",
    "Regra 12 - Abuso de Comandos",
    "Regra 13 - Uso de Trapaças",
    "Regra 14 - Conta Falsa",
    "Regra 15 - Compartilhamento de conteúdo NSFW",
    "Regra 16 - Punição in-game",
]

# Exemplo de configuração de instâncias por regra
INSTANCIAS_REGRAS = {
    "Regra 01": [
        {"punicao": "mute", "duracao": timedelta(days=1), "motivo": "Regra 01 - Ofensa (1ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=3), "motivo": "Regra 01 - Ofensa (2ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=7), "motivo": "Regra 01 - Ofensa (3ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=15), "motivo": "Regra 01 - Ofensa (4ª incidência)"},
        {"punicao": "ban", "motivo": "Regra 01 - Ofensa (5ª incidência)"},
    ],
    "Regra 02": [
        {"punicao": "mute", "duracao": timedelta(days=30), "motivo": "Regra 02 - Discriminação ou Atos Depreciativos (1ª incidência)"},
        {"punicao": "ban", "motivo": "Regra 02 - Discriminação ou Atos Depreciativos (2ª incidência)"},
    ],
    "Regra 03": [
        {"punicao": "mute", "duracao": timedelta(days=1), "motivo": "Regra 03 - Desordem no Chat (1ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=3), "motivo": "Regra 03 - Desordem no Chat (2ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=7), "motivo": "Regra 03 - Desordem no Chat (3ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=15), "motivo": "Regra 03 - Desordem no Chat (4ª incidência)"},
        {"punicao": "ban", "motivo": "Regra 03 - Desordem no Chat (5ª incidência)"},
    ],
    "Regra 04": [
        {"punicao": "mute", "duracao": timedelta(days=1), "motivo": "Regra 04 - Desinformação (1ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=3), "motivo": "Regra 04 - Desinformação (2ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=7), "motivo": "Regra 04 - Desinformação (3ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=15), "motivo": "Regra 04 - Desinformação (4ª incidência)"},
        {"punicao": "ban", "motivo": "Regra 04 - Desinformação (5ª incidência)"},
    ],
    "Regra 05": [
        {"punicao": "kick", "motivo": "Regra 05 - Nome ou Perfil Inadequado (1ª incidência)"},
        {"punicao": "ban", "motivo": "Regra 05 - Nome ou Perfil Inadequado (2ª incidência)"},
    ],
    "Regra 06": [
        {"punicao": "mute", "duracao": timedelta(days=1), "motivo": "Regra 06 - Fugir do Assunto em Tópicos (1ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=3), "motivo": "Regra 06 - Fugir do Assunto em Tópicos (2ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=7), "motivo": "Regra 06 - Fugir do Assunto em Tópicos (3ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=15), "motivo": "Regra 06 - Fugir do Assunto em Tópicos (4ª incidência)"},
        {"punicao": "ban", "motivo": "Regra 06 - Fugir do Assunto em Tópicos (5ª incidência)"},
    ],
    "Regra 07": [
        {"punicao": "mute", "duracao": timedelta(days=1), "motivo": "Regra 07 - Divulgação Simples (1ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=3), "motivo": "Regra 07 - Divulgação Simples (2ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=7), "motivo": "Regra 07 - Divulgação Simples (3ª incidência)"},
        {"punicao": "ban", "motivo": "Regra 07 - Divulgação Simples (4ª incidência)"},
    ],
    "Regra 08": [
        {"punicao": "mute", "duracao": timedelta(days=30), "motivo": "Regra 08 - Divulgação Grave (1ª incidência)"},
        {"punicao": "ban", "motivo": "Regra 08 - Divulgação Grave (2ª incidência)"},
    ],
    "Regra 09": [
        {"punicao": "ban", "motivo": "Regra 09 - Falsificação de fatos (1ª incidência)"},
    ],
    "Regra 10": [
        {"punicao": "ban", "motivo": "Regra 10 - Anti-jogo (1ª incidência)"},
    ],
    "Regra 11": [
        {"punicao": "ban", "motivo": "Regra 11 - Abuso de Bug (1ª incidência)"},
    ],
    "Regra 12": [
        {"punicao": "mute", "duracao": timedelta(days=1), "motivo": "Regra 12 - Abuso de Comandos (1ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=3), "motivo": "Regra 12 - Abuso de Comandos (2ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=7), "motivo": "Regra 12 - Abuso de Comandos (3ª incidência)"},
        {"punicao": "ban", "motivo": "Regra 12 - Abuso de Comandos (4ª incidência)"},
    ],
    "Regra 13": [
        {"punicao": "ban", "motivo": "Regra 13 - Uso de Trapaças (1ª incidência)"},
    ],
    "Regra 14": [
        {"punicao": "ban", "motivo": "Regra 14 - Conta Falsa (1ª incidência)"},
    ],
    "Regra 15": [
        {"punicao": "mute", "duracao": timedelta(days=1), "motivo": "Regra 15 - Compartilhamento de conteúdo NSFW (1ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=3), "motivo": "Regra 15 - Compartilhamento de conteúdo NSFW (2ª incidência)"},
        {"punicao": "mute", "duracao": timedelta(days=7), "motivo": "Regra 15 - Compartilhamento de conteúdo NSFW (3ª incidência)"},
        {"punicao": "ban", "motivo": "Regra 15 - Compartilhamento de conteúdo NSFW (4ª incidência)"},
    ],
    "Regra 16": [
        {"punicao": "ban", "motivo": "Regra 16 - Punição in-game (1ª incidência)"},
    ],
}

def formatar_timedelta(td):
    dias = td.days
    horas = td.seconds // 3600
    minutos = (td.seconds % 3600) // 60

    partes = []
    if dias > 0:
        partes.append(f"{dias} dia{'s' if dias > 1 else ''}")
    if horas > 0:
        partes.append(f"{horas} hora{'s' if horas > 1 else ''}")
    if minutos > 0:
        partes.append(f"{minutos} minuto{'s' if minutos > 1 else ''}")

    return ', '.join(partes) if partes else "menos de 1 minuto"

class Punicoes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def regra_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            discord.app_commands.Choice(name=regra, value=regra)
            for regra in REGRAS if current.lower() in regra.lower()
        ]

    @discord.app_commands.command(name="punir", description="Aplicar uma punição a um membro")
    @discord.app_commands.describe(membro="Nome do membro a ser punido", regra="Regra violada")
    @discord.app_commands.autocomplete(regra=regra_autocomplete)
    async def punir(self, interaction: discord.Interaction, membro: discord.Member, regra: str):
        # IDs dos cargos autorizados
        lider_id = int(os.getenv("LIDER_CARGO_ID", "0"))
        admin_id = int(os.getenv("ADMIN_CARGO_ID", "0"))
        moderador_id = int(os.getenv("MODERADOR_CARGO_ID", "0"))
        cargos_autorizados = [lider_id, admin_id, moderador_id]

        # Verifica se o autor possui algum dos cargos autorizados
        if not any(role.id in cargos_autorizados for role in interaction.user.roles):
            await interaction.response.send_message(
                "Você não tem permissão para usar este comando.", ephemeral=True
            )
            return

        user_id = str(membro.id)
        nome = membro.display_name

        instancia = registrar_punicao(user_id, regra, nome)

        regra_base = regra.split(" - ")[0]
        config = INSTANCIAS_REGRAS.get(regra_base)
        if config and instancia <= len(config):
            punicao = config[instancia-1]

            # Define o título e a cor conforme o tipo de punição
            emoji = "<a:Fkey_1:1359376998786662521>"
            if punicao["punicao"] == "mute":
                titulo_embed = f"{emoji} `{membro.display_name}` foi Silenciado(a)."
                cor_embed = discord.Color.from_rgb(255, 255, 0)
            elif punicao["punicao"] == "ban":
                titulo_embed = f"{emoji} `{membro.display_name}` foi Banido(a)."
                cor_embed = discord.Color.from_rgb(255, 0, 0)
            elif punicao["punicao"] == "kick":
                titulo_embed = f"{emoji} `{membro.display_name}` foi Expulso(a)."
                cor_embed = discord.Color.from_rgb(255, 165, 0)
            else:
                titulo_embed = f"{emoji} `{membro.display_name}` recebeu uma punição."
                cor_embed = discord.Color.default()

            embed = discord.Embed(
                title=titulo_embed,
                description=(
                    f"**Discord:** {membro.mention}\n"
                    f"**Punido por:** `{interaction.user.display_name}`\n"
                    f"**Duração:** `{formatar_timedelta(punicao.get('duracao')) if punicao['punicao'] == 'mute' else ('Permanente' if punicao['punicao'] == 'ban' else 'Não informado')}`\n"
                    f"**Motivo:** ```{punicao.get('motivo', 'Não informado')}```"
                ),
                color=cor_embed
            )
            embed.set_thumbnail(url=membro.display_avatar.url)
            if punicao["punicao"] == "mute":
                duracao = punicao["duracao"]
                motivo = punicao["motivo"]
                until = discord.utils.utcnow() + duracao
                await membro.timeout(until, reason=motivo)
            elif punicao["punicao"] == "ban":
                await membro.ban(reason=punicao["motivo"])
            elif punicao["punicao"] == "kick":
                await membro.kick(reason=punicao["motivo"])

            # Envia a embed no canal de punições
            canal_punicoes_id = os.getenv("PUNICOES_CHANNEL_ID")
            if canal_punicoes_id:
                canal_punicoes = interaction.guild.get_channel(int(canal_punicoes_id))
                if canal_punicoes:
                    await canal_punicoes.send(embed=embed)
            await interaction.response.send_message("Punição aplicada e registrada no canal de punições.", ephemeral=True)
        else:
            embed = discord.Embed(
                title="Punição aplicada",
                description=(
                    f"Membro: {membro.mention}\n"
                    f"Regra violada: `{regra}`\n"
                    f"Instância desta punição: **{instancia}**"
                ),
                color=discord.Color.red()
            )
            canal_punicoes_id = os.getenv("PUNICOES_CHANNEL_ID")
            if canal_punicoes_id:
                canal_punicoes = interaction.guild.get_channel(int(canal_punicoes_id))
                if canal_punicoes:
                    await canal_punicoes.send(embed=embed)
            await interaction.response.send_message("Punição registrada no canal de punições.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Punicoes(bot))