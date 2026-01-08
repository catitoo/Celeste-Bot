import discord
from discord.ext import commands
import os
import re
from dotenv import load_dotenv
import asyncio
load_dotenv()

class CriarGrupos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.canais_criados = {}
        self._recently_moved = set()

    def _proximo_indice(self, categoria: discord.CategoryChannel, prefixo: str) -> int:
        usados = set()
        for ch in categoria.voice_channels:
            m = re.fullmatch(rf"{re.escape(prefixo)} #(\d+)", ch.name, flags=re.IGNORECASE)
            if m:
                usados.add(int(m.group(1)))
        i = 1
        while i in usados:
            i += 1
        return i

    async def _limpar_recentes(self, member_id):
        await asyncio.sleep(1)
        self._recently_moved.discard(member_id)
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id in self._recently_moved:
            return

        if before.channel == after.channel:
            return

        if before.channel and before.channel.id in self.canais_criados:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    del self.canais_criados[before.channel.id]
                except discord.Forbidden:
                    print("Erro: Bot não tem permissão para deletar o canal")
                except discord.HTTPException as e:
                    print(f"Erro ao deletar canal: {e}")

        CRIAR_SALA_ID = int(os.getenv('CRIAR_SALA_CHANNEL_ID') or 0)
        CATEGORIA_GRUPOS_ID = int(os.getenv('GRUPOS_CRIADOS_CATEGORY_ID') or 0)

        if not (after.channel and after.channel.id == CRIAR_SALA_ID and (before.channel is None or before.channel.id != CRIAR_SALA_ID)):
            return

        limite_usuarios = None
        tipo_grupo = "Sala"

        categoria = self.bot.get_channel(CATEGORIA_GRUPOS_ID)

        if categoria is None:
            print(f"Erro: Categoria com ID {CATEGORIA_GRUPOS_ID} não encontrada")
            return

        numero = self._proximo_indice(categoria, tipo_grupo)
        nome_canal = f"{tipo_grupo} #{numero}"

        try:
            novo_canal = await categoria.create_voice_channel(
                name=nome_canal,
                user_limit=limite_usuarios
            )

            self.canais_criados[novo_canal.id] = member.id

            self._recently_moved.add(member.id)
            try:
                await member.move_to(novo_canal)
            except Exception:
                self._recently_moved.discard(member.id)
                raise

            asyncio.create_task(self._limpar_recentes(member.id))

            embed = discord.Embed(
                title=f"{nome_canal}",
                description="Organize seu grupo usando os botões abaixo.",
                color=discord.Color.orange()
            )
            embed.set_image(url="https://example.com/sua_imagem.png")

            # Importa a view dinamicamente (evita import circular)
            try:
                from .editar_salas import GrupoView
            except Exception:
                GrupoView = None

            try:
                await novo_canal.send(embed=embed, view=GrupoView() if GrupoView else None)
            except Exception as e:
                print(f"Não foi possível enviar mensagem no canal de voz: {e}")

        except discord.Forbidden:
            print("Erro: Bot não tem permissão para criar canais ou mover membros")
        except discord.HTTPException as e:
            print(f"Erro ao criar canal: {e}")
    
async def setup(bot):
    await bot.add_cog(CriarGrupos(bot))