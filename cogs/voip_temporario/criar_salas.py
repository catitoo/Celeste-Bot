import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
load_dotenv()

MAX_CHANNEL_NAME = 100
PREFIX = "📢・Sala de "

def _sanitize_nick(nick: str, max_len: int) -> str:
    nick = nick.replace("\n", " ").replace("\r", " ")
    nick = " ".join(nick.split())
    if len(nick) > max_len:
        return nick[: max_len - 1] + "…"
    return nick

class CriarGrupos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.canais_criados = {}
        self._recently_moved = set()

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

        categoria = self.bot.get_channel(CATEGORIA_GRUPOS_ID)

        if categoria is None:
            print(f"Erro: Categoria com ID {CATEGORIA_GRUPOS_ID} não encontrada")
            return

        apelido = getattr(member, "display_name", member.name)
        apelido = _sanitize_nick(apelido, MAX_CHANNEL_NAME - len(PREFIX))
        nome_canal = PREFIX + apelido

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

        except discord.Forbidden:
            print("Erro: Bot não tem permissão para criar canais ou mover membros")
        except discord.HTTPException as e:
            print(f"Erro ao criar canal: {e}")
    
async def setup(bot):
    await bot.add_cog(CriarGrupos(bot))