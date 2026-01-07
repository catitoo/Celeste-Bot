import discord
from discord.ext import commands
from dotenv import load_dotenv, set_key
import os

# Carrega as variáveis do arquivo .env
load_dotenv()

class FormularioDropdown(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="Formulário para Membro",
                description="Acesse o formulário para membros.",
                value="formulario_membro",
                emoji="<:Pixel_Forms:1352167388153647134>"
            )
        ]
        super().__init__(
            placeholder="Selecione uma opção...",
            options=options,
            custom_id="formulario_dropdown"  # Adicione um custom_id único
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "formulario_membro":
            # Obtém o cog `formulario_membro`
            cog = self.bot.get_cog("formulario_membro")
            if cog:
                # Chama diretamente a função `abrir_formulario`
                await cog.abrir_formulario(interaction)

                # Recria a View e atualiza a mensagem
                view = FormularioView(self.bot)
                await interaction.message.edit(view=view)
            else:
                await interaction.response.send_message(
                    "O cog 'formulario_membro' não está carregado.",
                    ephemeral=True
                )


class FormularioView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.add_item(FormularioDropdown(bot))


class FormularioMenu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Função para salvar valores no arquivo .env
    def salvar_no_env(self, chave, valor):
        set_key(".env", chave, str(valor))

    # Comando /set-menu-formulario para configurar o canal e enviar a embed com o menu
    @discord.app_commands.command(name="set-menu-formulario", description="Define o canal para o menu de formulário e envia o menu.")
    async def set_menu_formulario(self, interaction: discord.Interaction):
        # Verifica se o usuário é o dono do servidor
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)
            return

        # Copia o ID do canal onde o comando foi executado
        canal_id = interaction.channel.id
        self.salvar_no_env("MENU_FORMULARIO_CHANNEL_ID", canal_id)

        # Mensagem efêmera para o usuário
        await interaction.response.send_message(f"O canal {interaction.channel.mention} foi definido para o menu de formulário.", ephemeral=True)

        # Criação da embed
        embed = discord.Embed(
            title="<:Minecraft_Livro:1361958151921995807> Formulários para o Clã",
            description=(
                "Seja muito bem-vindo! Para começar, escolha uma das opções no menu abaixo e preencha o formulário correspondente ao seu interesse.\n\n"
                "<:Pixel_Punho:1361956298043691100> **Membro**\n"
                "Quer se tornar um membro do nosso clã, participar das atividades e fazer parte da nossa comunidade? Esta é a opção certa para você!\n\n"
                "<:Minecraft_Axoloti:1361956120448729210> **Aliado**\n"
                "Você representa outro clã e quer formar uma aliança conosco, ou apenas deseja interagir com a nossa comunidade? Então esta é a escolha ideal!\n\n"
                "<a:Interrogacao_1:1361959644938895390> **Está em dúvida?**\n"
                "Tudo bem! Você pode preencher os formulários quando quiser. Reflita com calma e escolha a opção que mais combina com você."
            ),
            color=discord.Color.from_rgb(255, 110, 0)
        )

        # Envia a embed com a view no canal
        mensagem = await interaction.channel.send(embed=embed, view=FormularioView(self.bot))

        # Salva o ID da mensagem no .env
        self.salvar_no_env("MENU_FORMULARIO_MESSAGE_ID", mensagem.id)

    # Função para registrar a View novamente no evento on_ready
    async def registrar_view(self):
        canal_id = os.getenv("MENU_FORMULARIO_CHANNEL_ID")
        mensagem_id = os.getenv("MENU_FORMULARIO_MESSAGE_ID")

        if canal_id and mensagem_id:
            canal = self.bot.get_channel(int(canal_id))
            if canal:
                try:
                    mensagem = await canal.fetch_message(int(mensagem_id))
                    if mensagem:
                        # Registra a View novamente
                        self.bot.add_view(FormularioView(self.bot), message_id=mensagem.id)
                except discord.NotFound:
                    print("Mensagem do menu não encontrada.")
                except discord.Forbidden:
                    print("Permissões insuficientes para acessar o canal ou mensagem.")


# Setup function para adicionar o cog ao bot
async def setup(bot):
    cog = FormularioMenu(bot)
    await bot.add_cog(cog)

    # Registra a View globalmente
    bot.add_view(FormularioView(bot))

    # Registra a View no evento on_ready
    bot.add_listener(cog.registrar_view, "on_ready")