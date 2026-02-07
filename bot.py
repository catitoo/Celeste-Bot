import discord
from config import bot, TOKEN  # Importa do arquivo config.py
from database.setup_database import voip_list_ativos, voip_remover_canal_ativo
from database.setup_database import SessionLocal, FormulariosDesenvolvedor
# tenta importar a tabela FormulariosAtivos; se não existir, usa fallback
try:
    from database.setup_database import FormulariosAtivos  # type: ignore
except Exception:
    FormulariosAtivos = None
import os
import logging

# Silencia logs informativos do discord
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)

async def carregar_cogs():
    for root, dirs, files in os.walk('./cogs'):
        for file in files:
            if file.endswith('.py'):
                path = os.path.relpath(os.path.join(root, file), '.').replace(os.sep, '.')
                await bot.load_extension(path[:-3])

# bot iniciou
@bot.event
async def on_ready():
    print(f'{bot.user} funcionando!')

    try:
        await carregar_cogs()  # Carrega os cogs
        # Limpa canais VoIP salvos que já estejam vazios no momento do startup
        async def _limpar_voips_vazios():
            ativos = voip_list_ativos()
            for entry in ativos:
                id_voip = int(entry.get('id_voip'))
                try:
                    channel = bot.get_channel(id_voip) or await bot.fetch_channel(id_voip)
                except Exception:
                    channel = None

                # Se o canal não existir mais, remove do DB
                if channel is None:
                    try:
                        voip_remover_canal_ativo(id_voip)
                    except Exception:
                        pass
                    continue

                # Se não houver membros, deleta o canal e remove do DB
                try:
                    if len(channel.members) == 0:
                        await channel.delete(reason="VoIP vazio no startup - limpeza automática")
                        voip_remover_canal_ativo(id_voip)
                except Exception:
                    # falha ao deletar ou acessar membros, ignora
                    pass

        await _limpar_voips_vazios()

        # Limpa entradas de formulários cujo message_id não exista mais no canal configurado
        async def _limpar_formularios_deletados():
            canal_env = os.getenv("FORMULARIO_PENDENTE_DESENVOLVEDOR_CHANNEL_ID")
            if not canal_env:
                return
            try:
                canal_id = int(canal_env)
            except ValueError:
                return

            try:
                channel = bot.get_channel(canal_id) or await bot.fetch_channel(canal_id)
            except Exception:
                channel = None

            if channel is None:
                return

            # decide qual modelo usar: FormulariosAtivos se existir, senão FormulariosDesenvolvedor
            model = FormulariosAtivos if FormulariosAtivos is not None else FormulariosDesenvolvedor

            session = SessionLocal()
            try:
                rows = session.query(model).all()
                removed = 0
                for r in rows:
                    msg_id = getattr(r, "id_mensagem", None)
                    if not msg_id:
                        # se não houver id de mensagem, não tentamos deletar aqui
                        continue
                    # tenta buscar a mensagem especificamente no canal configurado
                    try:
                        try:
                            await channel.fetch_message(int(msg_id))
                            # se foi encontrada, mantém o registro
                            continue
                        except discord.NotFound:
                            # mensagem não existe no canal: apagar do DB
                            session.query(model).filter_by(id_mensagem=str(msg_id)).delete(synchronize_session=False)
                            removed += 1
                        except Exception:
                            # outro erro ao buscar a mensagem: pula esse registro para evitar remoção indevida
                            continue
                    except Exception:
                        # erros inesperados no delete/fetch: pula
                        continue

                if removed:
                    try:
                        session.commit()
                        print(f"Removidas {removed} entradas de formulários com mensagens ausentes no canal {canal_id}.")
                    except Exception:
                        session.rollback()
            finally:
                session.close()

        await _limpar_formularios_deletados()
        await bot.tree.sync()  # Sincroniza comandos de barra
        print("Todos os comandos foram sincronizados com sucesso!")

    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")

bot.run(TOKEN)