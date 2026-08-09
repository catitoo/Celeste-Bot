import os
import re

import discord
from discord import app_commands
from discord.ext import commands

from database.setup_database import (
    EMBED_CAMPOS,
    EMBED_LIMITE_POR_USUARIO,
    embed_listar,
    embed_remover,
    embed_salvar,
)

COR_PADRAO = 16722217

# Estado inicial de toda embed recém-criada
EMBED_PADRAO = {
    **{campo: None for campo in EMBED_CAMPOS},
    "titulo": "Título",
    "descricao": "Descrição",
    "rodape": "Use os botões abaixo para montar a sua mensagem.",
    "cor": COR_PADRAO,
}

PADRAO_COR_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")
PADRAO_URL = re.compile(r"^https?://\S+$")


class CriarEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _checa_cargo_admin(self, interaction: discord.Interaction) -> bool:
        """Valida se quem usou o comando possui o cargo de administrador do .env."""
        # Checa se variável ADMINISTRADOR_CARGO_ID está definida no .env
        admin_env = os.getenv('ADMINISTRADOR_CARGO_ID')
        if not admin_env:
            await interaction.response.send_message("A variável de ambiente `ADMINISTRADOR_CARGO_ID` não está configurada.", ephemeral=True)
            return False
        m = re.search(r"(\d+)", admin_env)
        if not m:
            await interaction.response.send_message("Valor inválido em `ADMINISTRADOR_CARGO_ID`.", ephemeral=True)
            return False
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
            await interaction.response.send_message(f"Você precisa do cargo `{role_name}` para usar este comando.", ephemeral=True)
            return False

        return True

    @app_commands.command(
        name="criar-embed",
        description="Abre o painel de criação de embed"
    )
    async def criar_embed(self, interaction: discord.Interaction):
        # Só pode ser usado em servidor
        if interaction.guild is None:
            await interaction.response.send_message("Use este comando em um servidor (canal de texto).", ephemeral=True)
            return

        if not await self._checa_cargo_admin(interaction):
            return

        # Cada usuário abre o painel com as suas próprias embeds (as mesmas em qualquer servidor)
        view = PainelEmbedView(interaction.user.id)
        view.interacao_origem = interaction

        await interaction.response.send_message(
            content=view.conteudo(),
            embed=view.previa(),
            view=view,
            ephemeral=True,
        )


def montar_embed(dados: dict) -> discord.Embed:
    """Converte os dados salvos de uma embed em um discord.Embed exibível."""
    titulo = (dados.get("titulo") or "").strip()
    descricao = (dados.get("descricao") or "").strip()
    cor = dados.get("cor")

    embed = discord.Embed(
        title=titulo or None,
        description=descricao or None,
        # Sem cor a embed fica sem a barra lateral colorida
        colour=discord.Colour(cor) if cor is not None else None,
    )

    if dados.get("imagem"):
        embed.set_image(url=dados["imagem"])
    if dados.get("thumbnail"):
        embed.set_thumbnail(url=dados["thumbnail"])
    # Ícone e link do autor só são aceitos junto de um nome
    if dados.get("autor_nome"):
        embed.set_author(
            name=dados["autor_nome"],
            url=dados.get("autor_url") or None,
            icon_url=dados.get("autor_icone") or None,
        )
    # O mesmo vale para o ícone do rodapé em relação ao texto
    if dados.get("rodape"):
        embed.set_footer(text=dados["rodape"], icon_url=dados.get("rodape_icone") or None)

    # Uma embed sem nenhum conteúdo visível não é aceita pelo Discord
    visiveis = ("titulo", "descricao", "imagem", "thumbnail", "autor_nome", "rodape")
    if not any(dados.get(campo) for campo in visiveis):
        embed.description = "*Embed vazia — use os botões abaixo para preencher.*"

    return embed


def mesmo_conteudo(a: dict, b: dict) -> bool:
    """Compara apenas os campos que são persistidos."""
    return all(a.get(campo) == b.get(campo) for campo in EMBED_CAMPOS)


def texto_ou_nada(valor: str | None) -> str | None:
    return (valor or "").strip() or None


def converter_cor(texto: str | None) -> int | None:
    """Aceita cor em hex (#FF3629 / FF3629). Vazio deixa a embed sem cor."""
    texto = (texto or "").strip()
    if not texto:
        return None
    m = PADRAO_COR_HEX.match(texto)
    if not m:
        raise ValueError("Cor inválida. Use o formato hexadecimal, por exemplo `#FF3629`.")
    return int(m.group(1), 16)


def validar_url(texto: str | None, campo: str) -> str | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    if not PADRAO_URL.match(texto):
        raise ValueError(f"{campo} inválida. A URL precisa começar com `http://` ou `https://`.")
    return texto


def titulo_modal(painel: "PainelEmbedView", prefixo: str) -> str:
    """Título de modal, cortado no limite de 45 caracteres do Discord."""
    return f"{prefixo} - {painel.rotulo_do_slot(painel.slot_atual)}"[:45]


class NovaEmbedModal(discord.ui.Modal, title="Nova Embed"):
    """Pergunta o nome antes de criar a embed. Nome em branco usa 'Embed N'."""

    nome = discord.ui.TextInput(
        label="Nome da embed (opcional)",
        required=False,
        max_length=80,
    )

    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(timeout=600)
        self.painel = painel
        # O slot livre é consultado só para compor o nome padrão exibido
        slot = painel.proximo_slot_livre()
        self.nome.placeholder = (
            f"Nome padrão: Embed {slot}" if slot else "Aparece no menu do painel"
        )

    async def on_submit(self, interaction: discord.Interaction):
        slot = self.painel.proximo_slot_livre()
        if slot is None:
            await interaction.response.send_message(
                f"Você já atingiu o limite de {EMBED_LIMITE_POR_USUARIO} embeds.", ephemeral=True
            )
            return

        # A embed nasce como rascunho: só vai para o banco quando o usuário salvar
        self.painel.rascunhos[slot] = {
            **EMBED_PADRAO,
            "nome": texto_ou_nada(self.nome.value),
            "slot": slot,
        }
        self.painel.slot_atual = slot
        self.painel.recarregar()
        await self.painel.atualizar(interaction)


class ExcluirEmbedModal(discord.ui.Modal):
    """Exige a palavra de confirmação digitada antes de apagar a embed."""

    PALAVRA = "CONFIRMAR"

    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(title=titulo_modal(painel, "Excluir Embed"), timeout=600)
        self.painel = painel
        # O slot é fixado agora: o painel pode mudar de seleção enquanto o modal está aberto
        self.slot = painel.slot_atual
        self.confirmacao = discord.ui.TextInput(
            label=f"Digite {self.PALAVRA} para excluir",
            placeholder=self.PALAVRA,
            required=True,
            max_length=len(self.PALAVRA) + 5,
        )
        self.add_item(self.confirmacao)

    async def on_submit(self, interaction: discord.Interaction):
        if self.confirmacao.value.strip().upper() != self.PALAVRA:
            await interaction.response.send_message(
                f"Exclusão cancelada. é preciso digitar `{self.PALAVRA}` para confirmar.",
                ephemeral=True,
            )
            return

        await self.painel.excluir(interaction, self.slot)


class CampoModal(discord.ui.Modal):
    """Base dos formulários de campo: o resultado vira rascunho, não gravação."""

    def __init__(self, painel: "PainelEmbedView", titulo: str):
        super().__init__(title=titulo, timeout=600)
        self.painel = painel
        for item in self.montar_campos(painel.dados_atuais):
            self.add_item(item)

    def montar_campos(self, dados: dict) -> list[discord.ui.TextInput]:
        raise NotImplementedError

    def coletar(self) -> dict:
        """Devolve só os campos que este formulário edita. Pode levantar ValueError."""
        raise NotImplementedError

    async def on_submit(self, interaction: discord.Interaction):
        try:
            alteracoes = self.coletar()
        except ValueError as erro:
            await interaction.response.send_message(str(erro), ephemeral=True)
            return

        self.painel.aplicar_alteracoes(alteracoes)
        self.painel.recarregar()
        await interaction.response.edit_message(
            content=self.painel.conteudo(),
            embed=self.painel.previa(),
            view=self.painel,
        )


class RenomearModal(CampoModal):
    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(painel, titulo_modal(painel, "Renomear Embed"))

    def montar_campos(self, dados):
        self.nome = discord.ui.TextInput(
            label="Nome da embed (opcional)",
            placeholder=f"Nome padrão: Embed {self.painel.slot_atual}",
            required=False,
            max_length=80,
            default=dados.get("nome") or "",
        )
        return [self.nome]

    def coletar(self):
        return {"nome": texto_ou_nada(self.nome.value)}


class TituloModal(CampoModal):
    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(painel, titulo_modal(painel, "Alterar Título"))

    def montar_campos(self, dados):
        self.titulo = discord.ui.TextInput(
            label="Novo Título",
            placeholder="Deixe vazio para remover o título.",
            required=False,
            max_length=256,
            default=dados.get("titulo") or "",
        )
        return [self.titulo]

    def coletar(self):
        return {"titulo": texto_ou_nada(self.titulo.value)}


class DescricaoModal(CampoModal):
    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(painel, titulo_modal(painel, "Alterar Descrição"))

    def montar_campos(self, dados):
        self.descricao = discord.ui.TextInput(
            label="Nova Descrição",
            placeholder="Deixe vazio para remover a descrição.",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=4000,
            default=dados.get("descricao") or "",
        )
        return [self.descricao]

    def coletar(self):
        return {"descricao": texto_ou_nada(self.descricao.value)}


class CorModal(CampoModal):
    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(painel, titulo_modal(painel, "Alterar Cor"))

    def montar_campos(self, dados):
        cor = dados.get("cor")
        self.cor = discord.ui.TextInput(
            label="Nova Cor (hexadecimal)",
            placeholder="Deixe vazio para remover a cor.",
            required=False,
            # O Discord bloqueia o envio fora dessa faixa: só passa vazio, FF3629 ou #FF3629
            min_length=6,
            max_length=7,
            default=f"#{cor:06X}" if cor is not None else "",
        )
        return [self.cor]

    def coletar(self):
        return {"cor": converter_cor(self.cor.value)}


class AutorModal(CampoModal):
    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(painel, titulo_modal(painel, "Alterar Autor"))

    def montar_campos(self, dados):
        self.nome = discord.ui.TextInput(
            label="Novo Nome do Autor",
            placeholder="Deixe vazio para remover o autor.",
            required=False,
            max_length=256,
            default=dados.get("autor_nome") or "",
        )
        self.icone = discord.ui.TextInput(
            label="Nova URL do Ícone",
            placeholder="https://... — deixe vazio para remover o ícone.",
            required=False,
            default=dados.get("autor_icone") or "",
        )
        self.url = discord.ui.TextInput(
            label="Novo Link do Nome",
            placeholder="https://... — deixe vazio para remover o link.",
            required=False,
            default=dados.get("autor_url") or "",
        )
        return [self.nome, self.icone, self.url]

    def coletar(self):
        return {
            "autor_nome": texto_ou_nada(self.nome.value),
            "autor_icone": validar_url(self.icone.value, "URL do ícone do autor"),
            "autor_url": validar_url(self.url.value, "URL do link do autor"),
        }


class ImagemModal(CampoModal):
    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(painel, titulo_modal(painel, "Alterar Imagem"))

    def montar_campos(self, dados):
        self.imagem = discord.ui.TextInput(
            label="Nova URL da Imagem (rodapé da embed)",
            placeholder="https://... — deixe vazio para remover a imagem.",
            required=False,
            default=dados.get("imagem") or "",
        )
        self.thumbnail = discord.ui.TextInput(
            label="Nova URL do Thumbnail (canto superior)",
            placeholder="https://... — deixe vazio para remover o thumbnail.",
            required=False,
            default=dados.get("thumbnail") or "",
        )
        return [self.imagem, self.thumbnail]

    def coletar(self):
        return {
            "imagem": validar_url(self.imagem.value, "URL da imagem"),
            "thumbnail": validar_url(self.thumbnail.value, "URL do thumbnail"),
        }


class RodapeModal(CampoModal):
    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(painel, titulo_modal(painel, "Alterar Rodapé"))

    def montar_campos(self, dados):
        self.rodape = discord.ui.TextInput(
            label="Novo Texto do Rodapé",
            placeholder="Deixe vazio para remover o rodapé.",
            required=False,
            max_length=2048,
            default=dados.get("rodape") or "",
        )
        self.icone = discord.ui.TextInput(
            label="Nova URL do Ícone (precisa de um texto)",
            placeholder="https://... — deixe vazio para remover o ícone.",
            required=False,
            default=dados.get("rodape_icone") or "",
        )
        return [self.rodape, self.icone]

    def coletar(self):
        return {
            "rodape": texto_ou_nada(self.rodape.value),
            "rodape_icone": validar_url(self.icone.value, "URL do ícone do rodapé"),
        }


class PainelEmbedView(discord.ui.View):
    def __init__(self, id_usuario: int):
        super().__init__(timeout=600)
        self.id_usuario = int(id_usuario)
        self.interacao_origem: discord.Interaction | None = None
        # Nenhuma embed vem selecionada: o painel abre no modo lista, exibindo o template
        self.slot_atual: int | None = None
        self.embeds: list[dict] = []
        # Edições ainda não gravadas no banco, por slot. Uma embed recém-criada
        # também vive aqui: ela só existe na conta do usuário depois do salvar.
        self.rascunhos: dict[int, dict] = {}
        self.recarregar()

    # ---------------------------------------------------------------- estado

    def recarregar(self):
        """Relê as embeds do usuário no banco e sincroniza os componentes do painel."""
        self.embeds = embed_listar(self.id_usuario)

        slots = sorted(self.slots_ocupados)
        if self.slot_atual not in slots:
            self.slot_atual = None

        if slots:
            self.selecionar_embed.disabled = False
            self.selecionar_embed.placeholder = "Selecione um Embed para editar"
            self.selecionar_embed.options = [
                discord.SelectOption(
                    label=self.rotulo_do_slot(slot)[:100],
                    value=str(slot),
                    description=((self.dados_do_slot(slot).get("titulo") or "Sem título").strip() or "Sem título")[:100],
                    default=slot == self.slot_atual,
                )
                for slot in slots
            ]
        else:
            # O Discord exige ao menos uma opção mesmo em um menu desabilitado
            self.selecionar_embed.disabled = True
            self.selecionar_embed.placeholder = "Nenhuma embed criada — use Adicionar Embed"
            self.selecionar_embed.options = [
                discord.SelectOption(label="Nenhuma embed criada", value="0")
            ]

        self.adicionar_embed.disabled = len(slots) >= EMBED_LIMITE_POR_USUARIO
        self._sincronizar_componentes()

    @property
    def slots_salvos(self) -> set[int]:
        return {e["slot"] for e in self.embeds}

    @property
    def slots_ocupados(self) -> set[int]:
        """Slots já no banco somados aos que existem só como rascunho."""
        return self.slots_salvos | set(self.rascunhos)

    @property
    def slots_novos(self) -> set[int]:
        """Embeds criadas no painel que ainda não foram gravadas no banco."""
        return set(self.rascunhos) - self.slots_salvos

    def proximo_slot_livre(self) -> int | None:
        """Primeiro slot disponível, ou None se o limite já foi atingido."""
        ocupados = self.slots_ocupados
        return next(
            (n for n in range(1, EMBED_LIMITE_POR_USUARIO + 1) if n not in ocupados),
            None,
        )

    def _sincronizar_componentes(self):
        """Monta o painel conforme o modo: lista (sem seleção) ou edição."""
        self.clear_items()

        # O menu só existe no modo lista; na edição a volta é pelo botão ↩️
        if self.slot_atual is None:
            self.add_item(self.selecionar_embed)
            self.add_item(self.adicionar_embed)
            return

        for item in (self.editar_titulo, self.editar_descricao, self.editar_cor, self.editar_autor):
            self.add_item(item)
        for item in (self.editar_campos, self.editar_imagem, self.editar_rodape):
            self.add_item(item)
        for item in (self.voltar, self.renomear, self.importar_json, self.exportar_json):
            self.add_item(item)
        # O botão de salvar só existe enquanto houver alteração pendente
        if self.tem_alteracoes:
            self.add_item(self.salvar)
        for item in (self.excluir_embed, self.adicionar_botao, self.enviar_personalizado, self.enviar):
            self.add_item(item)

    @property
    def tem_alteracoes(self) -> bool:
        return self.slot_atual is not None and self.slot_atual in self.rascunhos

    def rotulo_do_slot(self, slot: int | None) -> str:
        """Nome escolhido pelo usuário, ou 'Embed N' quando ele não deu nome."""
        if slot is None:
            return "Embed"
        return (self.dados_do_slot(slot).get("nome") or "").strip() or f"Embed {slot}"

    def dados_do_slot(self, slot: int) -> dict:
        """Rascunho pendente do slot, se houver; caso contrário o que está salvo."""
        if slot in self.rascunhos:
            return self.rascunhos[slot]
        for e in self.embeds:
            if e["slot"] == slot:
                return e
        return dict(EMBED_PADRAO)

    @property
    def dados_atuais(self) -> dict:
        """Dados da embed selecionada; sem seleção, o template de exemplo."""
        if self.slot_atual is None:
            return dict(EMBED_PADRAO)
        return self.dados_do_slot(self.slot_atual)

    def previa(self) -> discord.Embed | None:
        """A prévia só existe no modo edição: a lista não mostra embed nenhuma."""
        if self.slot_atual is None:
            return None
        return montar_embed(self.dados_atuais)

    def aplicar_alteracoes(self, alteracoes: dict):
        """Mescla a edição de um campo ao estado atual da embed selecionada."""
        dados = dict(self.dados_atuais)
        dados.update(alteracoes)
        dados["slot"] = self.slot_atual
        self.registrar_rascunho(dados)

    def registrar_rascunho(self, dados: dict):
        """Guarda a edição pendente, ou a descarta se ela for igual ao que já está salvo."""
        slot = dados["slot"]
        salvo = next((e for e in self.embeds if e["slot"] == slot), None)
        if salvo is not None and mesmo_conteudo(dados, salvo):
            self.rascunhos.pop(slot, None)
        else:
            self.rascunhos[slot] = dados

    def conteudo(self) -> str:
        ocupados = self.slots_ocupados
        total = f"({len(ocupados)}/{EMBED_LIMITE_POR_USUARIO})"
        if not ocupados:
            linha = "**Painel de Criação de Embed**"
        elif self.slot_atual is None:
            linha = f"**Painel de Criação e Seleção de Embed** - {total}"
        else:
            partes = [f'**Painel de Edição de Embed** - Editando "{self.rotulo_do_slot(self.slot_atual)}"']
            if self.slot_atual in self.slots_novos:
                partes.append("⚠️ Esta embed ainda não esta salva na sua conta ⚠️")
            elif self.tem_alteracoes:
                partes.append("⚠️ Alterações não salvas — clique em **Salvar Alterações** para gravá-las.")
            linha = "\n\n".join(partes)
        # O Discord corta espaços no fim da mensagem: o caractere invisível
        # segura a linha em branco entre o texto e a embed
        return linha + "\n​"

    async def excluir(self, interaction: discord.Interaction, slot: int):
        """Apaga a embed do slot e volta para a lista."""
        # Uma embed que nunca foi salva não tem nada a apagar no banco
        if slot not in self.slots_novos:
            embed_remover(self.id_usuario, slot)
        self.rascunhos.pop(slot, None)
        self.slot_atual = None
        self.recarregar()
        await self.atualizar(interaction)

    async def atualizar(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content=self.conteudo(),
            embed=self.previa(),
            view=self,
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.interacao_origem:
            try:
                await self.interacao_origem.edit_original_response(
                    content=(
                        "**Painel expirado.**\n"
                        "Use `/criar-embed` novamente. As alterações que foram salvas ainda continuam na sua conta."
                    ),
                    view=self,
                )
            except Exception:
                pass

    # ------------------------------------------------------------ modo lista

    @discord.ui.select(
        placeholder="Selecione um Embed para editar",
        row=0,
        options=[
            discord.SelectOption(label="Embed 1", value="1", description="Embed padrão do painel"),
        ],
    )
    async def selecionar_embed(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.slot_atual = int(select.values[0])
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Adicionar Embed", emoji="➕", style=discord.ButtonStyle.success, row=1)
    async def adicionar_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NovaEmbedModal(self))

    # ----------------------------------------------------------- modo edição

    @discord.ui.button(label="Título", emoji="📄", style=discord.ButtonStyle.secondary, row=1)
    async def editar_titulo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TituloModal(self))

    @discord.ui.button(label="Descrição", emoji="📝", style=discord.ButtonStyle.secondary, row=1)
    async def editar_descricao(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DescricaoModal(self))

    @discord.ui.button(label="Cor", emoji="🎨", style=discord.ButtonStyle.secondary, row=1)
    async def editar_cor(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CorModal(self))

    @discord.ui.button(label="Autor", emoji="👤", style=discord.ButtonStyle.secondary, row=1)
    async def editar_autor(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AutorModal(self))

    @discord.ui.button(label="Editar Campos", emoji="✏️", style=discord.ButtonStyle.secondary, row=2)
    async def editar_campos(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: gerenciar os fields da embed (adicionar, editar, remover, reordenar)
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Imagem e Thumbnail", emoji="🖼️", style=discord.ButtonStyle.secondary, row=2)
    async def editar_imagem(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ImagemModal(self))

    @discord.ui.button(label="Rodapé", emoji="🚩", style=discord.ButtonStyle.secondary, row=2)
    async def editar_rodape(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RodapeModal(self))

    @discord.ui.button(emoji="↩️", style=discord.ButtonStyle.secondary, row=3)
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Os rascunhos são guardados por slot, então voltar não descarta nada
        self.slot_atual = None
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Renomear", emoji="🏷️", style=discord.ButtonStyle.secondary, row=3)
    async def renomear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenomearModal(self))

    @discord.ui.button(label="Importar JSON", emoji="⬆️", style=discord.ButtonStyle.primary, row=3)
    async def importar_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: carregar uma embed a partir de um JSON colado pelo usuário
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Exportar JSON", emoji="⬇️", style=discord.ButtonStyle.primary, row=3)
    async def exportar_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: devolver a embed atual serializada em JSON
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Salvar Alterações", emoji="💾", style=discord.ButtonStyle.success, row=4)
    async def salvar(self, interaction: discord.Interaction, button: discord.ui.Button):
        slot = self.slot_atual
        rascunho = self.rascunhos.get(slot)
        if rascunho is None:
            await interaction.response.send_message("Não há alterações pendentes.", ephemeral=True)
            return

        # O limite é conferido de novo aqui: o painel pode estar aberto há tempo
        if slot not in self.slots_salvos and len(self.embeds) >= EMBED_LIMITE_POR_USUARIO:
            await interaction.response.send_message(
                f"Você já atingiu o limite de {EMBED_LIMITE_POR_USUARIO} embeds.", ephemeral=True
            )
            return

        self.rascunhos.pop(slot, None)
        embed_salvar(self.id_usuario, slot, **{campo: rascunho.get(campo) for campo in EMBED_CAMPOS})

        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Excluir Embed", emoji="🗑️", style=discord.ButtonStyle.danger, row=4)
    async def excluir_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ExcluirEmbedModal(self))

    @discord.ui.button(label="Adicionar Botão", emoji="🔗", style=discord.ButtonStyle.secondary, row=4)
    async def adicionar_botao(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: adicionar um botão de link à mensagem final
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Enviar Personalizado", emoji="📡", style=discord.ButtonStyle.success, row=4)
    async def enviar_personalizado(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: enviar a mensagem via webhook com nome/avatar personalizados
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Enviar", emoji="📤", style=discord.ButtonStyle.success, row=4)
    async def enviar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: enviar a embed montada no canal escolhido
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CriarEmbed(bot))
