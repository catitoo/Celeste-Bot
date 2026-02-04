import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, set_key

load_dotenv()

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
        # Salva o ID do canal específico de registro na variável REGISTRAR_CHANNEL_ID
        self.salvar_no_env("REGISTRAR_CHANNEL_ID", canal_id)

        await interaction.response.send_message(f"O canal {interaction.channel.mention} foi definido para o menu de formulário.", ephemeral=True)

        # envia o Container visual com o botão que abre o modal
        await interaction.channel.send(view=self.RegistroComponents())


async def setup(bot: commands.Bot):
    cog = registrar_usuario(bot)
    await bot.add_cog(cog)
    # Inicia a tarefa que registra a view persistente (opcional)
    bot.loop.create_task(cog.registrar_view())