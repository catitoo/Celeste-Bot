import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
from database.setup_database import (
    voip_salvar_canal_ativo,
    voip_remover_canal_ativo,
    SessionLocal,
    VoipAtivo,
)
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
        self._startup_done = False

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
                    # remover do registro local
                    del self.canais_criados[before.channel.id]
                    # remover do banco de dados
                    try:
                        voip_remover_canal_ativo(int(before.channel.id))
                    except Exception as e:
                        print(f"Erro ao remover VoipAtivo do DB: {e}")
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

            # salvar no banco de dados
            try:
                voip_salvar_canal_ativo(int(member.guild.id), int(novo_canal.id), int(member.id))
            except Exception as e:
                print(f"Erro ao salvar VoipAtivo no DB: {e}")

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

    @commands.Cog.listener()
    async def on_ready(self):
        # executar limpeza apenas uma vez
        if self._startup_done:
            return
        self._startup_done = True

        await asyncio.sleep(1)
        # procurar voips cadastrados no banco que estejam vazios ou inexistentes
        session = SessionLocal()
        try:
            rows = session.query(VoipAtivo).all()
        except Exception:
            rows = []
        finally:
            session.close()

        for row in rows:
            try:
                channel = self.bot.get_channel(int(row.id_voip))
                if channel is None:
                    try:
                        voip_remover_canal_ativo(int(row.id_voip))
                    except Exception as e:
                        print(f"Erro ao remover VoipAtivo (canal inexistente) do DB: {e}")
                    continue

                if not hasattr(channel, "members"):
                    continue

                # canal vazio -> deletar + remover do DB
                if len(channel.members) == 0:
                    try:
                        await channel.delete()
                    except Exception as e:
                        print(f"Erro ao deletar canal vazio no startup: {e}")
                        continue
                    try:
                        voip_remover_canal_ativo(int(row.id_voip))
                    except Exception as e:
                        print(f"Erro ao remover VoipAtivo do DB após deletar canal no startup: {e}")
                    continue

                # canal tem membros -> garantir líder válido
                saved_leader_id = int(row.id_lider) if getattr(row, "id_lider", None) is not None else None
                present_leader = None
                if saved_leader_id:
                    for m in channel.members:
                        try:
                            if m.id == saved_leader_id:
                                present_leader = saved_leader_id
                                break
                        except Exception:
                            continue

                if present_leader:
                    # líder do DB está presente: registrar no cache
                    self.canais_criados[int(row.id_voip)] = present_leader
                else:
                    # escolher novo líder automático (primeiro membro humano não-bot)
                    new_leader = None
                    for m in channel.members:
                        if not m.bot:
                            new_leader = m
                            break
                    if new_leader:
                        try:
                            voip_salvar_canal_ativo(int(channel.guild.id), int(channel.id), int(new_leader.id))
                            self.canais_criados[int(row.id_voip)] = int(new_leader.id)
                        except Exception as e:
                            print(f"Erro ao atualizar líder no DB/startup: {e}")
                    else:
                        # só bots na chamada: não registra, deixará ser lido novamente depois
                        continue
            except Exception:
                continue
    
async def setup(bot):
    await bot.add_cog(CriarGrupos(bot))