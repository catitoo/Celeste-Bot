import os
import aiohttp
import discord
from discord.ext import commands
from datetime import timedelta, datetime

IMGBB_MAX_MB = 32

class ImagemParaURL(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.wrong_attempts = {}  # Dicionário para rastrear tentativas erradas {user_id: {'count': int, 'first_attempt': datetime}}

    async def _upload_to_imgbb(self, *, image_bytes: bytes | None = None, image_url: str | None = None, name: str | None = None, expiration: int | None = None):
        api_key = os.getenv("IMGBB_API_KEY")
        if not api_key:
            raise RuntimeError("Defina a variável de ambiente IMGBB_API_KEY com sua chave do imgbb.")

        endpoint = "https://api.imgbb.com/1/upload"
        params = {"key": api_key}
        if expiration:
            params["expiration"] = str(expiration)

        form = aiohttp.FormData()
        if image_bytes is not None:
            form.add_field("image", image_bytes, filename=name or "upload", content_type="application/octet-stream")
            if name:
                form.add_field("name", name)
        elif image_url:
            form.add_field("image", image_url)
            if name:
                form.add_field("name", name)
        else:
            raise ValueError("Nenhum conteúdo de imagem fornecido.")

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, params=params, data=form) as resp:
                data = await resp.json(content_type=None)
                return resp.status, data

    async def _track_wrong_attempt(self, message: discord.Message):
        """Rastreia tentativas erradas com janela de 2 minutos e coloca timeout se atingir 5 tentativas"""
        user_id = message.author.id
        now = datetime.now()
        
        # Se o usuário não está no dicionário, adiciona com a primeira tentativa
        if user_id not in self.wrong_attempts:
            self.wrong_attempts[user_id] = {
                'count': 1,
                'first_attempt': now
            }
            return False
        
        # Verifica se já passaram 2 minutos desde a primeira tentativa
        time_diff = now - self.wrong_attempts[user_id]['first_attempt']
        
        if time_diff > timedelta(minutes=2):
            # Reseta o contador se passaram mais de 2 minutos
            self.wrong_attempts[user_id] = {
                'count': 1,
                'first_attempt': now
            }
            return False
        
        # Incrementa o contador
        self.wrong_attempts[user_id]['count'] += 1
        
        # Verifica se atingiu 5 tentativas dentro dos 2 minutos
        if self.wrong_attempts[user_id]['count'] >= 5:
            # Coloca o usuário em timeout por 1 hora
            try:
                await message.author.timeout(timedelta(hours=1), reason="5 tentativas erradas em 2 minutos no canal de imagens")
                # Reseta as tentativas
                del self.wrong_attempts[user_id]
                # Retorna True para indicar que o usuário foi silenciado
                return True
            except discord.Forbidden:
                await message.channel.send("❌ Não tenho permissão para colocar este usuário em timeout.", delete_after=30)
            except Exception as e:
                await message.channel.send(f"❌ Erro ao colocar usuário em timeout: {e}", delete_after=30)
        
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignora mensagens do próprio bot
        if message.author.bot:
            return

        # Verifica se é o canal correto
        channel_id_str = os.getenv("IMAGEM_PARA_URL_CHANNEL_ID")
        if not channel_id_str:
            return
        
        try:
            channel_id = int(channel_id_str)
        except ValueError:
            return
        
        if message.channel.id != channel_id:
            return

        # Verifica se há anexos de imagem
        if message.attachments:
            # Verifica se o usuário enviou uma mensagem junto com a imagem
            if message.content.strip():
                await message.delete()  # Remove a mensagem
                was_timed_out = await self._track_wrong_attempt(message)
                
                embed = discord.Embed(title="❌ Apenas imagens são permitidas neste canal.", color=discord.Color.from_rgb(255, 0, 0))
                msg = await message.channel.send(embed=embed)
                await msg.delete(delay=30)
                
                if was_timed_out:
                    embed_timeout = discord.Embed(
                        title="🔇 Você foi colocado de castigo!",
                        description=f"{message.author.mention}, você foi colocado de castigo por 1 hora devido a 5 tentativas erradas em 2 minutos.",
                        color=discord.Color.from_rgb(255, 165, 0)
                    )
                    await message.channel.send(embed=embed_timeout, delete_after=60)
                return
            
            att: discord.Attachment = message.attachments[0]
            
            # Verifica se é uma imagem
            if att.content_type and att.content_type.startswith("image/"):
                # Reseta as tentativas erradas se o usuário enviar uma imagem válida
                if message.author.id in self.wrong_attempts:
                    del self.wrong_attempts[message.author.id]
                
                try:
                    # Verifica o tamanho
                    if att.size > IMGBB_MAX_MB * 1024 * 1024:
                        await message.reply(f"❌ Imagem maior que {IMGBB_MAX_MB} MB (limite do imgbb).", delete_after=30)
                        return

                    # Faz o upload
                    image_bytes = await att.read()
                    status, payload = await self._upload_to_imgbb(image_bytes=image_bytes, name=att.filename, expiration=604800)  # 7 dias em segundos

                    if status != 200 or not payload.get("success"):
                        detalhe = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
                        await message.reply(f"❌ Falha ao enviar para o imgbb. Status {status}. {detalhe or ''}".strip(), delete_after=30)
                        return

                    data = payload["data"]
                    final_url = data.get("url") or data.get("display_url") or data.get("url_viewer")
                    
                    if not final_url:
                        await message.reply("❌ Envio concluído, mas não foi possível obter a URL da imagem.", delete_after=30)
                        return

                    # Responde com o link da imagem
                    embed = discord.Embed(title="✅ Imagem Enviada!", description=f"Aqui está o link da sua imagem: {final_url}", color=discord.Color.from_rgb(0, 255, 0))
                    await message.channel.send(embed=embed, reference=message)

                except Exception as e:
                    embed = discord.Embed(title="❌ Ocorreu um erro", description=str(e), color=discord.Color.from_rgb(255, 0, 0))
                    msg = await message.channel.send(embed=embed)
                    await msg.delete(delay=30)
            else:
                await message.delete()
                was_timed_out = await self._track_wrong_attempt(message)
                
                embed = discord.Embed(title="❌ Apenas imagens são permitidas neste canal.", color=discord.Color.from_rgb(255, 0, 0))
                msg = await message.channel.send(embed=embed)
                await msg.delete(delay=30)
                
                if was_timed_out:
                    embed_timeout = discord.Embed(
                        title="🔇 Você foi colocado de castigo!",
                        description=f"{message.author.mention}, você foi colocado de castigo por 1 hora devido a 5 tentativas erradas em 2 minutos.",
                        color=discord.Color.from_rgb(255, 165, 0)
                    )
                    await message.channel.send(embed=embed_timeout, delete_after=60)
        else:
            await message.delete()
            was_timed_out = await self._track_wrong_attempt(message)
            
            embed = discord.Embed(title="❌ Apenas imagens são permitidas neste canal.", color=discord.Color.from_rgb(255, 0, 0))
            msg = await message.channel.send(embed=embed)
            await msg.delete(delay=30)
            
            if was_timed_out:
                embed_timeout = discord.Embed(
                    title="🔇 Você foi colocado em timeout!",
                    description=f"{message.author.mention}, você foi colocado em timeout por 1 hora devido a 5 tentativas erradas em 2 minutos.",
                    color=discord.Color.from_rgb(255, 165, 0)
                )
                await message.channel.send(embed=embed_timeout, delete_after=60)

async def setup(bot: commands.Bot):
    await bot.add_cog(ImagemParaURL(bot))
