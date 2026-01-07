import discord
from discord.ext import commands
import os
import re
from dotenv import load_dotenv, set_key
load_dotenv()

class CriarGrupos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.canais_criados = {}

    def salvar_no_env(self, chave: str, valor):
        set_key(".env", chave, str(valor))

    # View com botões
    class GrupoView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(emoji="<:Editar_Nome:1437591536463249448>", style=discord.ButtonStyle.secondary, custom_id="grupo_editar_nome")
        async def editar_nome(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Função: Editar Nome.", ephemeral=True)

        @discord.ui.button(emoji="<:Convidar_Jogadores:1437594789800312852>", style=discord.ButtonStyle.secondary, custom_id="grupo_convidar")
        async def convidar(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Função: Convidar Jogadores.", ephemeral=True)

        @discord.ui.button(emoji="<:Remover_Membro:1437599768246222958>", style=discord.ButtonStyle.secondary, custom_id="grupo_remover")
        async def remover_membro(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Função: Remover Membro.", ephemeral=True)

        @discord.ui.button(emoji="<:Trocar_Limite_Membro:1437601993404452874>", style=discord.ButtonStyle.secondary, custom_id="grupo_trocar_limite")
        async def trocar_limite(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Função: Trocar Limite de Membros.", ephemeral=True)

        @discord.ui.button(emoji="<:Deletar_Chamada:1437598183449690204>", style=discord.ButtonStyle.secondary, custom_id="grupo_deletar")
        async def deletar_chamada(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Função: Deletar Chamada.", ephemeral=True)

        @discord.ui.button(emoji="<:Bloquear_Chamada:1437593371869708459>", style=discord.ButtonStyle.secondary, custom_id="grupo_bloquear")
        async def bloquear(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Função: Bloquear Chamada.", ephemeral=True)

        @discord.ui.button(emoji="<:Liberar_Chamada:1437593661285073006>", style=discord.ButtonStyle.secondary, custom_id="grupo_liberar")
        async def liberar_chamada(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Função: Liberar Chamada.", ephemeral=True)

        @discord.ui.button(emoji="<:Assumir_Lideranca:1437592237763723476>", style=discord.ButtonStyle.secondary, custom_id="grupo_assumir")
        async def assumir_lideranca(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Função: Assumir Liderança.", ephemeral=True)

        @discord.ui.button(emoji="<:Transferir_Lideranca:1437625407972315251>", style=discord.ButtonStyle.secondary, custom_id="grupo_transferir_lideranca")
        async def transferir_lideranca(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Função: Transferir Liderança.", ephemeral=True)

        @discord.ui.button(emoji="<:Trocar_Regiao:1437606614910894120>", style=discord.ButtonStyle.secondary, custom_id="grupo_trocar_regiao")
        async def trocar_regiao(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Função: Trocar Região.", ephemeral=True)
        
    @discord.app_commands.command(name="set-menu-editar-sala", description="Define o canal e envia a embed com o menu para editar a sala.")
    async def set_menu_editar_sala(self, interaction: discord.Interaction):
        # Permite apenas o dono do servidor (padronizado com outros cogs)
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)
            return

        canal_id = interaction.channel.id
        # Salva no .env
        self.salvar_no_env("EDITAR_SALAS_CHANNEL_ID", canal_id)

        # Confirmação efêmera
        await interaction.response.send_message(
            f"O menu de edição das salas será exibido em {interaction.channel.mention}.",
            ephemeral=True
        )

        # Embed do menu
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

        # Envia a embed com a view persistente
        await interaction.channel.send(embed=embed, view=CriarGrupos.GrupoView())

    def _proximo_indice(self, categoria: discord.CategoryChannel, prefixo: str) -> int:
        # Coleta índices existentes do tipo "Prefixo #N"
        usados = set()
        for ch in categoria.voice_channels:
            m = re.fullmatch(rf"{re.escape(prefixo)} #(\d+)", ch.name, flags=re.IGNORECASE)
            if m:
                usados.add(int(m.group(1)))
        # Retorna o menor índice livre começando em 1
        i = 1
        while i in usados:
            i += 1
        return i
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # IDs dos canais de criação
        CRIAR_TRIOS_ID = int(os.getenv('CRIAR_TRIOS_CHANNEL_ID'))
        CRIAR_DUOS_ID = int(os.getenv('CRIAR_DUOS_CHANNEL_ID'))
        CATEGORIA_GRUPOS_ID = int(os.getenv('GRUPOS_CRIADOS_CATEGORY_ID'))
        
        # Verificar se o membro entrou em um canal de criação
        if after.channel and after.channel.id in [CRIAR_TRIOS_ID, CRIAR_DUOS_ID]:
            # Determinar o limite de usuários
            if after.channel.id == CRIAR_TRIOS_ID:
                limite_usuarios = 3
                tipo_grupo = "Trio"
            else:
                limite_usuarios = 2
                tipo_grupo = "Duo"
            
            # Obter a categoria
            categoria = self.bot.get_channel(CATEGORIA_GRUPOS_ID)
            
            if categoria is None:
                print(f"Erro: Categoria com ID {CATEGORIA_GRUPOS_ID} não encontrada")
                return
            
            # Criar novo canal de voz com nome sequencial (ex.: "Trio #1", "Duo #2")
            numero = self._proximo_indice(categoria, tipo_grupo)
            nome_canal = f"{tipo_grupo} #{numero}"
            
            try:
                novo_canal = await categoria.create_voice_channel(
                    name=nome_canal,
                    user_limit=limite_usuarios
                )
                
                # Adicionar ao dicionário de canais criados
                self.canais_criados[novo_canal.id] = member.id
                
                # Mover o membro para o novo canal
                await member.move_to(novo_canal)

                # Embed + botões (chat do canal de voz)
                embed = discord.Embed(
                    title=f"{nome_canal}",
                    description="Organize seu grupo usando os botões abaixo.",
                    color=discord.Color.orange()
                )
                embed.set_image(url="https://example.com/sua_imagem.png")  # Troque pela URL da imagem

                try:
                    await novo_canal.send(embed=embed, view=self.GrupoView())
                except Exception as e:
                    print(f"Não foi possível enviar mensagem no canal de voz: {e}")

            except discord.Forbidden:
                print("Erro: Bot não tem permissão para criar canais ou mover membros")
            except discord.HTTPException as e:
                print(f"Erro ao criar canal: {e}")
        
        # Verificar se um canal criado ficou vazio e deletá-lo
        if before.channel and before.channel.id in self.canais_criados:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    del self.canais_criados[before.channel.id]
                except discord.Forbidden:
                    print("Erro: Bot não tem permissão para deletar o canal")
                except discord.HTTPException as e:
                    print(f"Erro ao deletar canal: {e}")

async def setup(bot):
    await bot.add_cog(CriarGrupos(bot))
    # registra a view como persistente (funciona mesmo após reiniciar o bot)
    bot.add_view(CriarGrupos.GrupoView())