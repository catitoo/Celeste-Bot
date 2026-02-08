import re
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands


class CanalMidias(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot
		# tenta carregar o ID do canal de mídias a partir do .env (se existir)
		self.midias_channel_id = None
		midias_env = os.getenv('MIDIAS_CHANNEL_ID')
		if midias_env:
			m = re.search(r"(\d+)", midias_env)
			if m:
				try:
					self.midias_channel_id = int(m.group(1))
				except Exception:
					self.midias_channel_id = None

	@app_commands.command(
		name="set-canal-midias",
		description="Define o canal para ser o canal de midias do servidor."
	)
	async def set_canal_midias(self, interaction: discord.Interaction):
		# Só pode ser usado em servidor
		if interaction.guild is None:
			await interaction.response.send_message("Use este comando em um servidor (canal de texto).", ephemeral=True)
			return

		# Checa se variável ADMINISTRADOR_CARGO_ID está definida no .env
		admin_env = os.getenv('ADMINISTRADOR_CARGO_ID')
		if not admin_env:
			await interaction.response.send_message("A variável de ambiente `ADMINISTRADOR_CARGO_ID` não está configurada.", ephemeral=True)
			return
		m = re.search(r"(\d+)", admin_env)
		if not m:
			await interaction.response.send_message("Valor inválido em `ADMINISTRADOR_CARGO_ID`.", ephemeral=True)
			return
		admin_role_id = int(m.group(1))

		# Recupera o membro no guild para checar os cargos
		member = interaction.guild.get_member(interaction.user.id)
		if member is None:
			try:
				member = await interaction.guild.fetch_member(interaction.user.id)
			except Exception:
				member = interaction.user

		role_obj = interaction.guild.get_role(admin_role_id)
		role_name = role_obj.name if role_obj else f'ID {admin_role_id}'

		if isinstance(member, discord.Member):
			has_role = any(r.id == admin_role_id for r in member.roles)
		else:
			has_role = False

		if not has_role:
			await interaction.response.send_message(f"Você nao tem permissao para fazer isso.", ephemeral=True)
			return

		# Envia confirmação ephemeral ao usuário
		await interaction.response.send_message("**Canal de mídias definido com sucesso**.\nAgora as mídias só poderão ser enviadas neste canal.", ephemeral=True)

		# Envia uma mensagem no canal onde o comando foi usado (opcional)
		channel = interaction.channel
		try:
			# salva o id do canal em runtime na instância e no .env
			self.midias_channel_id = channel.id

			# Atualiza o arquivo .env no diretório raiz do projeto
			try:
				env_path = Path(__file__).resolve().parent.parent / '.env'
				if env_path.exists():
					content = env_path.read_text(encoding='utf-8')
					if re.search(r'^MIDIAS_CHANNEL_ID=.*$', content, flags=re.MULTILINE):
						content = re.sub(r"^MIDIAS_CHANNEL_ID=.*$", f"MIDIAS_CHANNEL_ID='{channel.id}'", content, flags=re.MULTILINE)
					else:
						content = content + f"\nMIDIAS_CHANNEL_ID='{channel.id}'\n"
					env_path.write_text(content, encoding='utf-8')
				else:
					env_path.write_text(f"MIDIAS_CHANNEL_ID='{channel.id}'\n", encoding='utf-8')
			except Exception as e:
				try:
					await interaction.followup.send(f"Erro ao atualizar .env: {e}", ephemeral=True)
				except Exception:
					pass
		except Exception as e:
			# tenta notificar o usuário via followup se houver erro
			try:
				await interaction.followup.send(f"Falha ao enviar mensagem no canal: {e}", ephemeral=True)
			except Exception:
				pass

	@commands.Cog.listener()
	async def on_message(self, message: discord.Message):
		# ignora mensagens de bots
		if message.author.bot:
			return

		# só atua se tivermos um canal configurado
		if not getattr(self, 'midias_channel_id', None):
			return

		# verifica se a mensagem foi enviada no canal de mídias
		if message.channel is None or getattr(message.channel, 'id', None) != self.midias_channel_id:
			return

		# verifica se há attachments e se algum é imagem/video
		if not message.attachments:
			return

		has_media = False
		for att in message.attachments:
			content_type = att.content_type or ''
			fname = (att.filename or '').lower()
			if content_type.startswith('image') or content_type.startswith('video'):
				has_media = True
				break
			if any(fname.endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.mov', '.mkv', '.webm', '.avi')):
				has_media = True
				break

		if not has_media:
			return

		# cria uma thread anexada à mensagem (se possível)
		try:
			# evita tentar criar thread dentro de uma thread
			if isinstance(message.channel, discord.Thread):
				return
			thread_name = f"Discussão Sobre a Mídia:"
			thread = await message.create_thread(name=thread_name, auto_archive_duration=1440)
		except Exception as e:
			print(f"Erro ao criar thread para mensagem {getattr(message, 'id', None)}: {e}")

async def setup(bot: commands.Bot) -> None:
	await bot.add_cog(CanalMidias(bot))

