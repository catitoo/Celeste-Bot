import os
import re

import discord
from discord import app_commands
from discord.ext import commands

from database.setup_database import (
    COR_LIMITE_POR_USUARIO,
    EMBED_CAMPOS,
    EMBED_LIMITE_POR_USUARIO,
    EMBED_PARTES_POR_SLOT,
    cor_listar,
    cor_remover,
    cor_salvar,
    embed_listar,
    embed_remover,
    embed_salvar_slot,
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
PADRAO_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)
PADRAO_ESQUEMA = re.compile(r"^https?://", re.IGNORECASE)

# Emojis da aplicação por nome, lidos no carregamento da cog. O ID muda a cada
# reupload e some quando o emoji é apagado, então o nome é a única referência
# estável: os IDs escritos nos botões abaixo servem só para dizer qual nome usar.
EMOJIS_APP: dict[str, str] = {}

# Ícones numerados do menu de seleção. A posição na lista é o que vale: o emoji
# acompanha a ordem exibida, não o slot da embed.
EMOJIS_NUMEROS: list[str | None] = [None] * EMBED_LIMITE_POR_USUARIO

# Valor da opção fixa do menu de cores, que não pode ser removida
SEM_COR = "__sem_cor__"
EMOJI_VOLTAR = "<:voltar_embed:1536200612226793482>"


async def carregar_emojis(bot: commands.Bot) -> None:
    """Lê os emojis da aplicação. Um nome ausente vira None e o componente
    correspondente simplesmente aparece sem ícone."""
    try:
        emojis = await bot.fetch_application_emojis()
    except Exception:
        return
    EMOJIS_APP.clear()
    EMOJIS_APP.update({e.name: str(e) for e in emojis})
    for indice in range(EMBED_LIMITE_POR_USUARIO):
        EMOJIS_NUMEROS[indice] = EMOJIS_APP.get(f"num{indice + 1}")


class CriarEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await carregar_emojis(self.bot)

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
            embeds=view.previa(),
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
        # Sem título o Discord ignora a URL
        url=(dados.get("titulo_url") or None) if titulo else None,
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
    """Aceita a URL com ou sem esquema: sem ele, o Discord recusa o link, então
    o `https://` é acrescentado. Quem já digitou http:// ou https:// fica como está."""
    texto = (texto or "").strip()
    if not texto:
        return None
    if not PADRAO_ESQUEMA.match(texto):
        texto = f"https://{texto}"
    if not PADRAO_URL.match(texto):
        raise ValueError(f"{campo} inválida. Verifique o endereço digitado.")
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
        self.painel.rascunhos[slot] = [{
            **EMBED_PADRAO,
            "nome": texto_ou_nada(self.nome.value),
        }]
        self.painel.slot_atual = slot
        self.painel.parte_atual = 1
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
            embeds=self.painel.previa(),
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
        self.url = discord.ui.TextInput(
            label="URL do Título (opcional)",
            placeholder="Deixe vazio para o título não virar link.",
            required=False,
            max_length=512,
            default=dados.get("titulo_url") or "",
        )
        return [self.titulo, self.url]

    def coletar(self):
        return {
            "titulo": texto_ou_nada(self.titulo.value),
            "titulo_url": validar_url(self.url.value, "URL do título"),
        }


class DescricaoModal(CampoModal):
    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(painel, titulo_modal(painel, "Alterar Descrição"))

    def montar_campos(self, dados):
        self.descricao = discord.ui.TextInput(
            label="Nova Descrição",
            placeholder=(
                "Deixe vazio para remover a descrição.\n"
                "Cargo: <@&ID>\n"
                "Canal: <#ID>"
            ),
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=4000,
            default=dados.get("descricao") or "",
        )
        return [self.descricao]

    def coletar(self):
        return {"descricao": texto_ou_nada(self.descricao.value)}


class NovaCorModal(discord.ui.Modal, title="Nova Cor"):
    """Salva uma cor na paleta do usuário e já a aplica na embed em edição."""

    nome = discord.ui.TextInput(
        label="Nome da cor",
        placeholder="Aparece no menu de cores. Ex.: Vermelho Celeste",
        required=True,
        max_length=80,
    )
    codigo = discord.ui.TextInput(
        label="Cor (hexadecimal)",
        placeholder="Ex.: #FF3629",
        required=True,
        # O Discord bloqueia o envio fora dessa faixa: só passa FF3629 ou #FF3629
        min_length=6,
        max_length=7,
    )

    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(timeout=600)
        self.painel = painel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cor = converter_cor(self.codigo.value)
        except ValueError as erro:
            await interaction.response.send_message(str(erro), ephemeral=True)
            return
        if cor is None:
            await interaction.response.send_message(
                "Informe um código hexadecimal. Para deixar a embed sem cor, use a opção **Sem cor** do menu.",
                ephemeral=True,
            )
            return

        nome = texto_ou_nada(self.nome.value)
        if nome is None:
            await interaction.response.send_message("Dê um nome para a cor.", ephemeral=True)
            return

        salvas = {c["nome"] for c in self.painel.cores}
        if nome not in salvas and len(salvas) >= COR_LIMITE_POR_USUARIO:
            await interaction.response.send_message(
                f"Você já atingiu o limite de {COR_LIMITE_POR_USUARIO} cores salvas.", ephemeral=True
            )
            return

        cor_salvar(self.painel.id_usuario, nome, cor)
        # Criar uma cor durante a edição é sinal de que ela é a escolhida agora
        self.painel.aplicar_alteracoes({"cor": cor})
        self.painel.recarregar()
        await self.painel.atualizar(interaction)


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
        # Qual das embeds empilhadas do slot está sendo editada (1..N)
        self.parte_atual: int = 1
        self.embeds: list[dict] = []
        # Edições ainda não gravadas no banco, por slot. O rascunho guarda a lista
        # completa de partes do slot — a posição na lista é a ordem na mensagem.
        # Uma embed recém-criada também vive aqui: ela só existe na conta do
        # usuário depois do salvar.
        self.rascunhos: dict[int, list[dict]] = {}
        # Terceiro modo do painel, aberto pelo botão Cor dentro da edição
        self.modo_cores: bool = False
        self.cores: list[dict] = []
        # Criado na mão, e não por decorator: o discord.ui só aceita 5 de largura
        # por linha e o menu de slots já ocupa a linha 0 inteira na declaração.
        self.selecionar_parte = discord.ui.Select(placeholder="Selecione a embed da mensagem", row=0)
        self.selecionar_parte.callback = self._trocar_parte
        # Componentes do modo cores, também na mão: os declarados já lotam a view
        self.selecionar_cor = discord.ui.Select(placeholder="Selecione uma cor", row=0)
        self.selecionar_cor.callback = self._escolher_cor
        self.voltar_cores = discord.ui.Button(
            emoji=EMOJI_VOLTAR, style=discord.ButtonStyle.secondary, row=1)
        self.voltar_cores.callback = self._sair_das_cores
        self.adicionar_cor = discord.ui.Button(
            label="Adicionar Cor", style=discord.ButtonStyle.success, row=1)
        self.adicionar_cor.callback = self._abrir_nova_cor
        self.remover_cor = discord.ui.Button(
            label="Remover Cor", style=discord.ButtonStyle.danger, row=1)
        self.remover_cor.callback = self._remover_cor
        # Botão de link não tem callback: o Discord só abre a URL
        self.encontrar_cores = discord.ui.Button(
            label="Encontrar Cores", url="https://htmlcolorcodes.com", row=1)
        self._sanear_emojis()
        self.recarregar()

    # ---------------------------------------------------------------- cores

    async def _escolher_cor(self, interaction: discord.Interaction):
        escolha = self.selecionar_cor.values[0]
        cor = None if escolha == SEM_COR else self._cor_por_nome(escolha)
        self.aplicar_alteracoes({"cor": cor})
        self.recarregar()
        await self.atualizar(interaction)

    async def _sair_das_cores(self, interaction: discord.Interaction):
        self.modo_cores = False
        self.recarregar()
        await self.atualizar(interaction)

    async def _abrir_nova_cor(self, interaction: discord.Interaction):
        await interaction.response.send_modal(NovaCorModal(self))

    async def _remover_cor(self, interaction: discord.Interaction):
        nome = self.nome_da_cor_atual
        if nome is None:
            await interaction.response.send_message(
                "Selecione no menu a cor que quer remover. A opção **Sem cor** não pode ser removida.",
                ephemeral=True,
            )
            return

        cor_remover(self.id_usuario, nome)
        # A embed fica sem cor: a que ela usava não existe mais na paleta
        self.aplicar_alteracoes({"cor": None})
        self.recarregar()
        await self.atualizar(interaction)

    def _cor_por_nome(self, nome: str) -> int | None:
        return next((c["cor"] for c in self.cores if c["nome"] == nome), None)

    @property
    def nome_da_cor_atual(self) -> str | None:
        """Nome da cor salva que a embed está usando, se ela veio da paleta."""
        cor = self.dados_atuais.get("cor")
        if cor is None:
            return None
        return next((c["nome"] for c in self.cores if c["cor"] == cor), None)

    def _sanear_emojis(self):
        """Reaponta os emojis dos botões para os IDs atuais da aplicação, usando o
        nome como chave. Um emoji apagado sai do botão em vez de derrubar o painel
        inteiro com 'Invalid emoji' na hora de renderizar."""
        if not EMOJIS_APP:
            return
        for item in [*self.children, self.voltar_cores]:
            emoji = getattr(item, "emoji", None)
            # Emoji unicode (sem id) não depende da aplicação
            if emoji is None or emoji.id is None:
                continue
            item.emoji = EMOJIS_APP.get(emoji.name)

    async def _trocar_parte(self, interaction: discord.Interaction):
        self.parte_atual = int(self.selecionar_parte.values[0])
        self.recarregar()
        await self.atualizar(interaction)

    # ---------------------------------------------------------------- estado

    def recarregar(self):
        """Relê as embeds do usuário no banco e sincroniza os componentes do painel."""
        self.embeds = embed_listar(self.id_usuario)
        self.cores = cor_listar(self.id_usuario)

        slots = sorted(self.slots_ocupados)
        if self.slot_atual not in slots:
            self.slot_atual = None
            self.parte_atual = 1

        if slots:
            self.selecionar_embed.disabled = False
            self.selecionar_embed.placeholder = "Selecione um Embed para editar"
            self.selecionar_embed.options = [
                discord.SelectOption(
                    label=self.rotulo_do_slot(slot)[:100],
                    value=str(slot),
                    description=self._resumo(self.dados_do_slot(slot), len(self.partes_do_slot(slot))),
                    emoji=EMOJIS_NUMEROS[posicao],
                    default=slot == self.slot_atual,
                )
                for posicao, slot in enumerate(slots)
            ]
        else:
            # O Discord exige ao menos uma opção mesmo em um menu desabilitado
            self.selecionar_embed.disabled = True
            self.selecionar_embed.placeholder = "Nenhuma embed criada — use Adicionar Embed"
            self.selecionar_embed.options = [
                discord.SelectOption(label="Nenhuma embed criada", value="0")
            ]

        self.adicionar_embed.disabled = len(slots) >= EMBED_LIMITE_POR_USUARIO

        if self.slot_atual is not None:
            partes = self.partes_do_slot(self.slot_atual)
            self.parte_atual = min(max(self.parte_atual, 1), len(partes))
            self.selecionar_parte.placeholder = f"Editando a embed {self.parte_atual} de {len(partes)}"
            self.selecionar_parte.options = [
                discord.SelectOption(
                    label=f"Embed {numero}",
                    value=str(numero),
                    description=self._resumo(dados),
                    emoji=EMOJIS_NUMEROS[numero - 1],
                    default=numero == self.parte_atual,
                )
                for numero, dados in enumerate(partes, start=1)
            ]
            self.adicionar_parte.disabled = len(partes) >= EMBED_PARTES_POR_SLOT
            self.remover_parte.disabled = len(partes) <= 1
            self._montar_menu_de_cores()

        self._sincronizar_componentes()

    def _montar_menu_de_cores(self):
        """Sem cor sempre encabeça o menu; abaixo dela vem a paleta do usuário."""
        nome_atual = self.nome_da_cor_atual
        sem_cor = self.dados_atuais.get("cor") is None
        opcoes = [
            discord.SelectOption(
                label="Sem cor",
                value=SEM_COR,
                description="A embed fica sem a barra lateral colorida",
                default=sem_cor,
            ),
            *(
                discord.SelectOption(
                    label=c["nome"][:100],
                    value=c["nome"],
                    description=f"#{c['cor']:06X}",
                    default=c["nome"] == nome_atual,
                )
                for c in self.cores
            ),
        ]
        # O ícone segue a posição no menu, como no seletor de embeds
        for posicao, opcao in enumerate(opcoes):
            opcao.emoji = EMOJIS_NUMEROS[posicao]
        self.selecionar_cor.options = opcoes
        self.adicionar_cor.disabled = len(self.cores) >= COR_LIMITE_POR_USUARIO
        self.remover_cor.disabled = nome_atual is None

    @staticmethod
    def _resumo(dados: dict, total_partes: int = 1) -> str:
        """Texto de apoio das opções: o título da embed, ou um aviso de vazia."""
        titulo = (dados.get("titulo") or "").strip() or "Sem título"
        if total_partes > 1:
            titulo = f"{titulo} (+{total_partes - 1})"
        return titulo[:100]

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

        # O menu de slots só existe no modo lista; na edição a volta é pelo botão ↩️
        if self.slot_atual is None:
            self.add_item(self.selecionar_embed)
            self.add_item(self.adicionar_embed)
            return

        if self.modo_cores:
            self.add_item(self.selecionar_cor)
            for item in (self.voltar_cores, self.encontrar_cores,
                         self.adicionar_cor, self.remover_cor):
                self.add_item(item)
            return

        # Com uma embed só na mensagem não há o que escolher
        if len(self.partes_do_slot(self.slot_atual)) > 1:
            self.add_item(self.selecionar_parte)
        for item in (self.editar_titulo, self.editar_descricao, self.editar_cor,
                     self.editar_autor, self.editar_rodape):
            self.add_item(item)
        for item in (self.editar_imagem, self.editar_campos, self.adicionar_botao,
                     self.remover_botao, self.renomear):
            self.add_item(item)
        for item in (self.voltar, self.adicionar_parte, self.remover_parte,
                     self.importar_json, self.exportar_json):
            self.add_item(item)
        # O botão de salvar só existe enquanto houver alteração pendente
        if self.tem_alteracoes:
            self.add_item(self.salvar)
        for item in (self.excluir_embed, self.enviar_personalizado, self.enviar):
            self.add_item(item)

    @property
    def tem_alteracoes(self) -> bool:
        return self.slot_atual is not None and self.slot_atual in self.rascunhos

    def rotulo_do_slot(self, slot: int | None) -> str:
        """Nome escolhido pelo usuário, ou 'Embed N' quando ele não deu nome."""
        if slot is None:
            return "Embed"
        return (self.dados_do_slot(slot).get("nome") or "").strip() or f"Embed {slot}"

    def partes_do_slot(self, slot: int) -> list[dict]:
        """As embeds empilhadas do slot: o rascunho pendente, se houver; senão o salvo."""
        if slot in self.rascunhos:
            return self.rascunhos[slot]
        salvas = [e for e in self.embeds if e["slot"] == slot]
        return salvas or [dict(EMBED_PADRAO)]

    def dados_do_slot(self, slot: int) -> dict:
        """Primeira embed do slot — é dela que saem o nome e o resumo do menu."""
        return self.partes_do_slot(slot)[0]

    @property
    def dados_atuais(self) -> dict:
        """Dados da embed selecionada; sem seleção, o template de exemplo."""
        if self.slot_atual is None:
            return dict(EMBED_PADRAO)
        partes = self.partes_do_slot(self.slot_atual)
        return partes[min(self.parte_atual, len(partes)) - 1]

    def previa(self) -> list[discord.Embed]:
        """A prévia só existe no modo edição: a lista não mostra embed nenhuma."""
        if self.slot_atual is None:
            return []
        return [montar_embed(dados) for dados in self.partes_do_slot(self.slot_atual)]

    def aplicar_alteracoes(self, alteracoes: dict):
        """Mescla a edição de um campo à embed selecionada dentro do slot."""
        partes = [dict(p) for p in self.partes_do_slot(self.slot_atual)]
        partes[self.parte_atual - 1].update(alteracoes)
        # O nome identifica o slot inteiro, então acompanha todas as partes
        if "nome" in alteracoes:
            for parte in partes:
                parte["nome"] = alteracoes["nome"]
        self.registrar_rascunho(self.slot_atual, partes)

    def registrar_rascunho(self, slot: int, partes: list[dict]):
        """Guarda a edição pendente, ou a descarta se ela for igual ao que já está salvo."""
        salvas = [e for e in self.embeds if e["slot"] == slot]
        igual = (
            len(salvas) == len(partes)
            and all(mesmo_conteudo(a, b) for a, b in zip(partes, salvas))
        )
        if salvas and igual:
            self.rascunhos.pop(slot, None)
        else:
            self.rascunhos[slot] = partes

    def conteudo(self) -> str:
        ocupados = self.slots_ocupados
        total = f"({len(ocupados)}/{EMBED_LIMITE_POR_USUARIO})"
        if not ocupados:
            linha = "**Painel de Criação de Embed**"
        elif self.slot_atual is None:
            linha = f"**Painel de Criação e Seleção de Embed** - {total}"
        else:
            nome_embed = self.rotulo_do_slot(self.slot_atual)
            if self.modo_cores:
                cabecalho = f'**Painel de Cores** - Editando "{nome_embed}"'
            else:
                cabecalho = f'**Painel de Edição de Embed** - Editando "{nome_embed}"'
            quantidade = len(self.partes_do_slot(self.slot_atual))
            if quantidade > 1:
                cabecalho += f" - embed {self.parte_atual} de {quantidade}"
            partes = [cabecalho]
            if self.slot_atual in self.slots_novos:
                partes.append("⚠️ Esta embed ainda não esta salva na sua conta ⚠️")
            elif self.tem_alteracoes:
                partes.append("⚠️ Alterações não salvas — clique em **Salvar Alterações** para gravá-las.")
            linha = "\n\n".join(partes)
        # O Discord corta espaços no fim da mensagem: o caractere invisível
        # segura a linha em branco entre o texto e a embed
        return linha + "\n\u200b"

    async def excluir(self, interaction: discord.Interaction, slot: int):
        """Apaga a embed do slot (com todas as suas partes) e volta para a lista."""
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
            embeds=self.previa(),
            view=self,
        )

    async def on_timeout(self):
        self.clear_items()
        if self.interacao_origem:
            try:
                await self.interacao_origem.edit_original_response(
                    content=(
                        "**Painel expirado.**\n"
                        "Use `/criar-embed` novamente. As alterações que foram salvas ainda continuam na sua conta.\n"
                        # Espaçador: separa o aviso da embed em uma linha própria
                        "\u200b"
                    ),
                    view=None,
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
        self.parte_atual = 1
        self.modo_cores = False
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Adicionar Embed", emoji="<:new_embed:1536200609827524658>", style=discord.ButtonStyle.success, row=4)
    async def adicionar_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NovaEmbedModal(self))

    # ----------------------------------------------------------- modo edição

    @discord.ui.button(label="Título", emoji="<:title_embed:1536201573200564315>", style=discord.ButtonStyle.secondary, row=1)
    async def editar_titulo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TituloModal(self))

    @discord.ui.button(label="Descrição", emoji="<:description_embed:1536155252498104340>", style=discord.ButtonStyle.secondary, row=1)
    async def editar_descricao(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DescricaoModal(self))

    @discord.ui.button(label="Cor", emoji="<:color_embed:1536200617217761350>", style=discord.ButtonStyle.secondary, row=1)
    async def editar_cor(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.modo_cores = True
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Autor", emoji="<:author_embed:1536155249096785980>", style=discord.ButtonStyle.secondary, row=1)
    async def editar_autor(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AutorModal(self))

    @discord.ui.button(label="Rodapé", emoji="<:rodape_embed:1536200607155888139>", style=discord.ButtonStyle.secondary, row=1)
    async def editar_rodape(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RodapeModal(self))

    @discord.ui.button(label="Imagem e Thumbnail", emoji="<:image_embed:1536155250149564437>", style=discord.ButtonStyle.secondary, row=2)
    async def editar_imagem(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ImagemModal(self))

    @discord.ui.button(label="Editar Campos", emoji="<:editar_campos_embed:1536200613346672760>", style=discord.ButtonStyle.secondary, row=2)
    async def editar_campos(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: gerenciar os fields da embed (adicionar, editar, remover, reordenar)
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Adicionar Botão", emoji="<:add_button_embed:1536155254272557197>", style=discord.ButtonStyle.secondary, row=2)
    async def adicionar_botao(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: adicionar um botão de link à mensagem final
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Remover Botão", emoji="<:remove_button_embed:1536155255639646268>", style=discord.ButtonStyle.secondary, row=2)
    async def remover_botao(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: remover um dos botões de link da mensagem final
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Renomear", emoji="<:renomear_embed:1536200611006259270>", style=discord.ButtonStyle.secondary, row=2)
    async def renomear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenomearModal(self))

    @discord.ui.button(emoji="<:voltar_embed:1536200612226793482>", style=discord.ButtonStyle.secondary, row=3)
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Os rascunhos são guardados por slot, então voltar não descarta nada
        self.slot_atual = None
        self.parte_atual = 1
        self.modo_cores = False
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Adicionar Embed", emoji="<:add_embed:1536155247368605836>", style=discord.ButtonStyle.secondary, row=3)
    async def adicionar_parte(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Empilha mais uma embed na mesma mensagem (o Discord aceita até 10)."""
        partes = [dict(p) for p in self.partes_do_slot(self.slot_atual)]
        if len(partes) >= EMBED_PARTES_POR_SLOT:
            await interaction.response.send_message(
                f"Uma mensagem aceita no máximo {EMBED_PARTES_POR_SLOT} embeds.", ephemeral=True
            )
            return

        # A nova parte herda só o nome: ele identifica o slot, não a embed
        partes.append({**EMBED_PADRAO, "nome": partes[0].get("nome")})
        self.registrar_rascunho(self.slot_atual, partes)
        self.parte_atual = len(partes)
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Remover Embed", emoji="<:remove_embed:1536155257363628193>", style=discord.ButtonStyle.secondary, row=3)
    async def remover_parte(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Tira a embed selecionada da mensagem. Para apagar o slot inteiro é o Excluir Embed."""
        partes = [dict(p) for p in self.partes_do_slot(self.slot_atual)]
        if len(partes) <= 1:
            await interaction.response.send_message(
                "A mensagem precisa de pelo menos uma embed. Use **Excluir Embed** para apagar tudo.",
                ephemeral=True,
            )
            return

        partes.pop(self.parte_atual - 1)
        self.registrar_rascunho(self.slot_atual, partes)
        self.parte_atual = min(self.parte_atual, len(partes))
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Importar JSON", emoji="<:import_embed:1536154668906979358>", style=discord.ButtonStyle.primary, row=3)
    async def importar_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: carregar uma embed a partir de um JSON colado pelo usuário
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Exportar JSON", emoji="<:export_embed:1536154667359408221>", style=discord.ButtonStyle.primary, row=3)
    async def exportar_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: devolver a embed atual serializada em JSON
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Salvar Alterações", emoji="<:save_embed:1536200608510648381>", style=discord.ButtonStyle.success, row=4)
    async def salvar(self, interaction: discord.Interaction, button: discord.ui.Button):
        slot = self.slot_atual
        rascunho = self.rascunhos.get(slot)
        if rascunho is None:
            await interaction.response.send_message("Não há alterações pendentes.", ephemeral=True)
            return

        # O limite é conferido de novo aqui: o painel pode estar aberto há tempo
        if slot not in self.slots_salvos and len(self.slots_salvos) >= EMBED_LIMITE_POR_USUARIO:
            await interaction.response.send_message(
                f"Você já atingiu o limite de {EMBED_LIMITE_POR_USUARIO} embeds.", ephemeral=True
            )
            return

        self.rascunhos.pop(slot, None)
        embed_salvar_slot(self.id_usuario, slot, rascunho)

        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Excluir Embed", emoji="<:deletar_embed:1536192015010766878>", style=discord.ButtonStyle.danger, row=4)
    async def excluir_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ExcluirEmbedModal(self))

    @discord.ui.button(label="Enviar Personalizado", emoji="<:enviar_personalizado_embed:1536203707052462120>", style=discord.ButtonStyle.success, row=4)
    async def enviar_personalizado(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: enviar a mensagem via webhook com nome/avatar personalizados
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Enviar", emoji="<:enviar_embed:1536200615422853161>", style=discord.ButtonStyle.success, row=4)
    async def enviar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: enviar a embed montada no canal escolhido
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CriarEmbed(bot))
