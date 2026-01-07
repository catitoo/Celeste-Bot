import discord
from discord.ext import commands
import os
import re  # Adicionar import
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
            
            # Campo 1: Nome de Exibição
            self.nome_exibicao = discord.ui.TextInput(
                label="Nome de Exibição",
                style=discord.TextStyle.short,
                placeholder="Exemplo: RaiderMan",
                required=True,
                min_length=2,
                max_length=16
            )
            self.add_item(self.nome_exibicao)
            
            # Campo 2: Código de Usuário
            self.codigo_usuario = discord.ui.TextInput(
                label="Código de Usuário",
                style=discord.TextStyle.short,
                placeholder="Exemplo: 1234 ou #1234",
                required=True,
                min_length=4,
                max_length=5  # 4 números + possível "#"
            )
            self.add_item(self.codigo_usuario)

        def validar_nome_exibicao(self, texto: str) -> tuple[bool, str]:
            """Valida o formato do Nome de Exibição"""
            
            # Verifica tamanho (2-16 caracteres)
            if len(texto) < 2 or len(texto) > 16:
                return False, "❌ No campo de `Nome de Exibição`: deve conter entre 2 e 16 caracteres."
            
            # Verifica se inicia com letra ou número
            if not texto[0].isalnum():
                return False, "❌ No campo de `Nome de Exibição`: deve iniciar com uma letra ou número."
            
            # Verifica se contém apenas caracteres permitidos
            if not re.match(r'^[A-Za-z0-9._-]+$', texto):
                return False, "❌ No campo de `Nome de Exibição`: use apenas letras , números , hífen `-` , underline `_` e ponto `.` ."
            
            # Verifica máximo de 4 números em sequência
            if re.search(r'\d{5,}', texto):
                return False, "❌ No campo de `Nome de Exibição`: não são permitidos mais de 4 números em sequência."
            
            # Verifica máximo de 1 símbolo em sequência
            if re.search(r'[._-]{2,}', texto):
                return False, "❌ No campo de `Nome de Exibição`: não são permitidos mais de 1 símbolo em sequência."
            
            return True, "✅ Formato válido!"

        def validar_codigo_usuario(self, texto: str) -> tuple[bool, str, str]:
            """Valida e formata o Código de Usuário
            
            Retorna: (valido, mensagem_erro, codigo_formatado)
            """
            texto = texto.strip()
            
            # Remove o # se existir para validar apenas os números
            codigo_limpo = texto.replace("#", "")
            
            # Verifica se contém apenas números
            if not codigo_limpo.isdigit():
                return False, "❌ No campo de `Código de Usuário`: deve conter apenas números (ex: 1234 ou #1234).", ""
            
            # Verifica se tem exatamente 4 dígitos
            if len(codigo_limpo) != 4:
                return False, "❌ No campo de `Código de Usuário`: deve ter exatamente 4 números.", ""
            
            # Formata com # se não tiver
            codigo_formatado = texto if texto.startswith("#") else f"#{codigo_limpo}"
            
            return True, "✅ Código válido!", codigo_formatado

        async def on_submit(self, interaction: discord.Interaction):
            nome_limpo = self.nome_exibicao.value.strip()
            codigo_limpo = self.codigo_usuario.value.strip()
            
            # Valida o Nome de Exibição
            valido_nome, mensagem_nome = self.validar_nome_exibicao(nome_limpo)
            if not valido_nome:
                await interaction.response.send_message(mensagem_nome, ephemeral=True)
                return
            
            # Valida o Código de Usuário
            valido_codigo, mensagem_codigo, codigo_formatado = self.validar_codigo_usuario(codigo_limpo)
            if not valido_codigo:
                await interaction.response.send_message(mensagem_codigo, ephemeral=True)
                return
            
            # Combina Nome + Código com espaço entre eles
            apelido_final = f"{nome_limpo} {codigo_formatado}"
            
            # Verifica se o apelido final não ultrapassa 32 caracteres (limite do Discord)
            if len(apelido_final) > 32:
                await interaction.response.send_message(
                    "❌ O apelido completo excede 32 caracteres. Escolha um nome mais curto.",
                    ephemeral=True
                )
                return
            
            # Altera o apelido do usuário e gerencia cargos
            try:
                # Altera o apelido
                await interaction.user.edit(nick=apelido_final)
                
                # Obtém os IDs dos cargos do .env
                raider_cargo_id = os.getenv("RAIDER_CARGO_ID")
                visitante_cargo_id = os.getenv("VISITANTE_CARGO_ID")
                
                # Adiciona o cargo de Raider
                if raider_cargo_id:
                    raider_cargo = interaction.guild.get_role(int(raider_cargo_id))
                    if raider_cargo:
                        await interaction.user.add_roles(raider_cargo)
                
                # Remove o cargo de Visitante
                if visitante_cargo_id:
                    visitante_cargo = interaction.guild.get_role(int(visitante_cargo_id))
                    if visitante_cargo and visitante_cargo in interaction.user.roles:
                        await interaction.user.remove_roles(visitante_cargo)
                
                await interaction.response.send_message(
                    f"✅ Obrigado! Seu apelido foi alterado para: `{apelido_final}` e você agora é um Raider!", 
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ Não tenho permissão para alterar seu apelido ou gerenciar seus cargos.", 
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ Ocorreu um erro: {str(e)}", 
                    ephemeral=True
                )

        async def on_error(self, interaction: discord.Interaction, error: Exception):
            await interaction.response.send_message("Ocorreu um erro no envio do formulário.", ephemeral=True)

    class Registrar_Usurario_View(discord.ui.View):
        def __init__(self, bot: commands.Bot, *, timeout: float = None):
            super().__init__(timeout=timeout)
            self.bot = bot

        @discord.ui.button(label="Registrar-se", style=discord.ButtonStyle.primary, custom_id="registrar_se_button")
        async def registrar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            modal = registrar_usuario.Registrar_Usurario_Modal(self.bot)
            await interaction.response.send_modal(modal)

    @discord.app_commands.command(name="set-registro-formulario", description="Define o canal para o menu de registro e envia o menu no canal.")
    async def set_registro_formulario(self, interaction: discord.Interaction):
        # Verifica se o usuário é o dono do servidor
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)
            return

        canal_id = interaction.channel.id
        # Salva o ID do canal específico de registro na variável REGISTRAR_CHANNEL_ID
        self.salvar_no_env("REGISTRAR_CHANNEL_ID", canal_id)

        await interaction.response.send_message(f"O canal {interaction.channel.mention} foi definido para o menu de formulário.", ephemeral=True)

        embed = discord.Embed(
            title="Registre-se na nossa comunidade e torne-se um Raider!",
            description=(
                "Seja muito bem-vindo(a)!\n Para começar, clique em Registrar-se abaixo e preencha o formulário com a sua ID do ARC Raiders.\n\n"
                "❓ **Não sabe qual é a sua ID de usuário no ARC Raiders?**\n\n" 
                "Siga os passos abaixo:\n"
                "> 1. Abra o jogo ARC Raiders.\n"
                "> 2. Vá até o menu de sistema.\n"
                "> 3. Na área de grupos, localize a sua conta e selecione ela.\n"
                "> 4. Clique na opção \"Copiar nome\".\n"
                "> 5. Cole a ID (ex: NomePlayer#1234) nos campos do formulário separadamente (ex: 'NomePlayer' no primeiro campo e '#1234' no segundo campo)."
            ),
            color=discord.Color.from_rgb(255, 110, 0)
        )

        mensagem = await interaction.channel.send(embed=embed, view=self.Registrar_Usurario_View(self.bot))

    async def registrar_view(self):
        # registra view persistente quando o bot estiver pronto
        await self.bot.wait_until_ready()
        self.bot.add_view(self.Registrar_Usurario_View(self.bot))


async def setup(bot: commands.Bot):
    cog = registrar_usuario(bot)
    await bot.add_cog(cog)
    # Inicia a tarefa que registra a view persistente (opcional)
    bot.loop.create_task(cog.registrar_view())