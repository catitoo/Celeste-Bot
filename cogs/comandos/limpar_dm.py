import asyncio
import discord
from discord import app_commands
from discord.ext import commands


class LimparDM(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # comando /limpar-dm (comando para apagar mensagens do bot na DM)
    @app_commands.command(
        name="limpar-dm",
        description="Apaga todas as mensagens enviadas pelo bot na DM."
    )
    async def limpar_chat(self, interaction: discord.Interaction):
        # Só permitir na DM com o bot
        if interaction.guild is not None:
            await interaction.response.send_message("Use este comando na DM com o bot.", ephemeral=True)
            return

        class ConfirmarLimparDMView(discord.ui.View):
            def __init__(self, bot: commands.Bot, requester_id: int):
                super().__init__(timeout=60)
                self.bot = bot
                self.requester_id = requester_id

            async def interaction_check(self, i: discord.Interaction) -> bool:
                # Só quem executou o comando pode clicar
                if i.user.id != self.requester_id:
                    await i.response.send_message("Só você pode usar estes botões.", ephemeral=True)
                    return False
                return True

            @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.success)
            async def confirmar(self, i: discord.Interaction, _: discord.ui.Button):
                for item in self.children:
                    item.disabled = True

                embed_andamento = discord.Embed(
                    title="Limpando DM…",
                    description="Apagando minhas mensagens nesta conversa. Isso pode levar um tempo.",
                    color=discord.Color.orange(),
                )
                await i.response.edit_message(embed=embed_andamento, view=self)

                channel = i.channel
                apagadas = 0

                # DM não suporta bulk delete. Se deletarmos muito rápido,
                # o Discord retorna 429 e o discord.py loga warnings.
                # Um pequeno delay fixo evita estourar o rate limit.
                delete_delay_seconds = 0.75

                async for msg in channel.history(limit=None, oldest_first=False):
                    if msg.author and msg.author.id == self.bot.user.id:
                        try:
                            await msg.delete()
                            apagadas += 1
                            await asyncio.sleep(delete_delay_seconds)
                        except (discord.NotFound, discord.Forbidden):
                            # Mensagem já foi apagada ou não temos permissão.
                            await asyncio.sleep(delete_delay_seconds)
                        except discord.HTTPException:
                            # Em caso de falha (incluindo rate limit), desacelera um pouco mais.
                            await asyncio.sleep(max(1.25, delete_delay_seconds))

                embed_final = discord.Embed(
                    title="Pronto.",
                    description=f"Apaguei **{apagadas}** mensagens minhas nesta DM.",
                    color=discord.Color.from_rgb(0, 255, 0),
                )
                await i.edit_original_response(embed=embed_final, view=None)

            @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.danger)
            async def cancelar(self, i: discord.Interaction, _: discord.ui.Button):
                for item in self.children:
                    item.disabled = True

                embed_cancelado = discord.Embed(
                    title="Cancelado.",
                    description="Nada foi apagado.",
                    color=discord.Color.from_rgb(255, 0, 0),
                )
                await i.response.edit_message(embed=embed_cancelado, view=self)

        embed = discord.Embed(
            title="Confirmar limpeza do chat?",
            description="Isso vai apagar **todas as mensagens que EU enviei** nesta DM.\n"
                        "Eu não consigo apagar mensagens enviadas por você.",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(
            embed=embed,
            view=ConfirmarLimparDMView(self.bot, interaction.user.id),
            ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LimparDM(bot))
