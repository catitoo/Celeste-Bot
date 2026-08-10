import os
import re

import discord
from discord import app_commands
from discord.ext import commands

from database.setup_database import (
    BOTAO_CAMPOS,
    BOTAO_LIMITE_POR_SLOT,
    CAMPO_CAMPOS,
    CAMPO_LIMITE_POR_EMBED,
    COR_LIMITE_POR_USUARIO,
    EMBED_CAMPOS,
    EMBED_LIMITE_POR_USUARIO,
    EMBED_PARTES_POR_SLOT,
    botao_listar,
    botao_remover,
    botao_salvar_slot,
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


def embed_padrao() -> dict:
    """Cópia nova do template, com a lista de campos própria: um dict compartilhado
    deixaria as partes editando a mesma lista."""
    return {**EMBED_PADRAO, "campos": []}


PADRAO_COR_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")
PADRAO_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)
PADRAO_ESQUEMA = re.compile(r"^https?://", re.IGNORECASE)
PADRAO_EMOJI_CUSTOM = re.compile(r"^<a?:\w{2,32}:\d{15,25}>$")

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

# Ações que moram no seletor de partes junto das embeds da mensagem
PARTE_ADICIONAR = "__adicionar_parte__"
PARTE_REMOVER = "__remover_parte__"

# Submodos do painel de edição. Cada um troca as linhas de componentes por um
# conjunto próprio, porque a mensagem só aceita 5 linhas no total.
MODO_CORES = "cores"
MODO_BOTOES = "botoes"
MODO_CAMPOS = "campos"
MODO_JSON = "json"
MODO_ENVIAR = "enviar"

CABECALHO_POR_MODO = {
    MODO_CORES: "Painel de Cores",
    MODO_BOTOES: "Remover Botão",
    MODO_CAMPOS: "Painel de Campos",
    MODO_JSON: "Importar e Exportar JSON",
    MODO_ENVIAR: "Enviar Mensagem",
}

# Respostas aceitas na pergunta "Em Linha" do formulário de campo
RESPOSTAS_SIM = {"sim", "s", "yes", "y", "true", "1", "v", "verdadeiro"}
RESPOSTAS_NAO = {"nao", "não", "n", "no", "false", "0", "f", "falso"}

# A prévia dos botões de link ocupa uma linha só, e uma linha comporta 5 botões
BOTAO_POR_LINHA = 5


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

    for campo in (dados.get("campos") or [])[:CAMPO_LIMITE_POR_EMBED]:
        # O Discord recusa nome ou valor vazio: o caractere invisível preenche o
        # que ficou em branco, que é como se monta campo só com valor ou só com nome
        embed.add_field(
            name=(campo.get("nome") or "").strip() or "\u200b",
            value=(campo.get("valor") or "").strip() or "\u200b",
            inline=bool(campo.get("em_linha")),
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
    if not embed.fields and not any(dados.get(campo) for campo in visiveis):
        embed.description = "*Embed vazia — use os botões abaixo para preencher.*"

    return embed


def mesmos_campos(a: list[dict], b: list[dict]) -> bool:
    """Compara duas listas de campos posição por posição."""
    return len(a) == len(b) and all(
        all(x.get(chave) == y.get(chave) for chave in CAMPO_CAMPOS)
        for x, y in zip(a, b)
    )


def mesmo_conteudo(a: dict, b: dict) -> bool:
    """Compara apenas os campos que são persistidos."""
    if not all(a.get(campo) == b.get(campo) for campo in EMBED_CAMPOS):
        return False
    return mesmos_campos(a.get("campos") or [], b.get("campos") or [])


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


def converter_em_linha(texto: str | None) -> bool:
    """Lê a resposta Sim/Não da pergunta "Em Linha" do formulário de campo."""
    valor = (texto or "").strip().lower()
    if valor in RESPOSTAS_SIM:
        return True
    if valor in RESPOSTAS_NAO:
        return False
    raise ValueError("Responda **Sim** ou **Não** em *Em Linha*.")


def validar_emoji(texto: str | None) -> str | None:
    """Aceita emoji do teclado ou emoji de servidor no formato `<:nome:id>`. O que
    não parece emoji é recusado aqui para não derrubar a mensagem no envio."""
    texto = (texto or "").strip()
    if not texto:
        return None
    if PADRAO_EMOJI_CUSTOM.match(texto):
        return texto
    # Emoji unicode: curto e com ao menos um caractere fora da tabela ASCII
    if len(texto) <= 16 and any(ord(c) > 127 for c in texto):
        return texto
    raise ValueError(
        "Emoji inválido. Use um emoji do teclado ou o formato `<:nome:id>` de um emoji de servidor."
    )


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
            **embed_padrao(),
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


class BotaoLinkModal(discord.ui.Modal, title="Crie seu Botão de Link"):
    """Acrescenta um botão de link à mensagem. Como o resto do painel, o botão
    fica em rascunho e só vai para a conta do usuário no salvar."""

    rotulo = discord.ui.TextInput(
        label="Texto do botão",
        placeholder="Clique aqui para visitar meu site",
        required=True,
        max_length=80,
    )
    url = discord.ui.TextInput(
        label="URL do botão",
        placeholder="https://discord.gg/vfCMEWfSQ6",
        required=True,
        max_length=512,
    )
    emoji = discord.ui.TextInput(
        label="Emoji do botão (opcional)",
        placeholder="😎",
        required=False,
        max_length=32,
    )

    def __init__(self, painel: "PainelEmbedView"):
        super().__init__(timeout=600)
        self.painel = painel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            url = validar_url(self.url.value, "URL do botão")
            emoji = validar_emoji(self.emoji.value)
        except ValueError as erro:
            await interaction.response.send_message(str(erro), ephemeral=True)
            return

        rotulo = texto_ou_nada(self.rotulo.value)
        if rotulo is None or url is None:
            await interaction.response.send_message(
                "O botão precisa de um texto e de uma URL.", ephemeral=True
            )
            return

        # O slot pode ter mudado enquanto o modal estava aberto
        slot = self.painel.slot_atual
        if slot is None:
            await interaction.response.send_message(
                "Selecione uma embed antes de adicionar o botão.", ephemeral=True
            )
            return

        botoes = [dict(b) for b in self.painel.botoes_do_slot(slot)]
        if len(botoes) >= BOTAO_LIMITE_POR_SLOT:
            await interaction.response.send_message(
                f"Uma mensagem aceita no máximo {BOTAO_LIMITE_POR_SLOT} botões.", ephemeral=True
            )
            return

        botoes.append({"rotulo": rotulo, "url": url, "emoji": emoji})
        self.painel.registrar_rascunho_botoes(slot, botoes)
        self.painel.recarregar()
        await self.painel.atualizar(interaction)


class CampoEmbedModal(discord.ui.Modal, title="Configure um campo"):
    """Formulário de um campo (field) da embed. Serve para criar e para editar: o
    índice diz qual campo está sendo alterado, e None cria um novo."""

    def __init__(self, painel: "PainelEmbedView", indice: int | None = None):
        super().__init__(timeout=600)
        self.painel = painel
        self.indice = indice
        atual = painel.campos_atuais[indice] if indice is not None else {}

        self.nome = discord.ui.TextInput(
            label="Título",
            placeholder="Vazio deixa o título invisível, permitidas certas formatações.",
            required=False,
            max_length=256,
            default=atual.get("nome") or "",
        )
        self.valor = discord.ui.TextInput(
            label="Parágrafo",
            placeholder="Vazio deixa o parágrafo invisível, permitido formatação.",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1024,
            default=atual.get("valor") or "",
        )
        self.em_linha = discord.ui.TextInput(
            label="Em Linha",
            placeholder="O campo deve continuar na mesma linha? (Sim ou Não)",
            required=True,
            max_length=16,
            default=("Sim" if atual.get("em_linha") else "Não") if indice is not None else "",
        )
        for item in (self.nome, self.valor, self.em_linha):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            em_linha = converter_em_linha(self.em_linha.value)
        except ValueError as erro:
            await interaction.response.send_message(str(erro), ephemeral=True)
            return

        nome = texto_ou_nada(self.nome.value)
        valor = texto_ou_nada(self.valor.value)
        # Um dos dois em branco fica invisível; os dois deixariam um campo que
        # ocupa espaço na embed sem mostrar nada
        if nome is None and valor is None:
            await interaction.response.send_message(
                "Preencha o título ou o parágrafo do campo — os dois em branco deixariam o campo invisível.",
                ephemeral=True,
            )
            return

        campo = {"nome": nome, "valor": valor, "em_linha": em_linha}
        campos = [dict(c) for c in self.painel.campos_atuais]

        if self.indice is None:
            if len(campos) >= CAMPO_LIMITE_POR_EMBED:
                await interaction.response.send_message(
                    f"Uma embed aceita no máximo {CAMPO_LIMITE_POR_EMBED} campos.", ephemeral=True
                )
                return
            campos.append(campo)
            self.painel.campo_atual = len(campos) - 1
        elif self.indice < len(campos):
            campos[self.indice] = campo
            self.painel.campo_atual = self.indice
        else:
            # O campo saiu do painel enquanto o formulário estava aberto
            await interaction.response.send_message(
                "Este campo não existe mais. Use **Adicionar Campo** para criá-lo de novo.",
                ephemeral=True,
            )
            return

        self.painel.aplicar_alteracoes({"campos": campos})
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
        # Botões de link da mensagem, com o mesmo esquema de rascunho por slot.
        # Ficam separados das embeds porque pertencem à mensagem, não a uma embed.
        self.botoes: list[dict] = []
        self.rascunhos_botoes: dict[int, list[dict]] = {}
        # Submodo aberto por Cor, Campos, Remover Botão, JSON ou Enviar; None é a edição
        self.modo: str | None = None
        # Campo selecionado no modo campos, por posição na embed em edição
        self.campo_atual: int | None = None
        self.cores: list[dict] = []
        # Criado na mão, e não por decorator: a linha 0 do painel de edição é da
        # prévia dos botões de link, montada a cada render.
        self.selecionar_parte = discord.ui.Select(placeholder="Selecione a embed da mensagem", row=1)
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
        # Componentes do modo campos: o menu escolhe o campo em que Editar e
        # Remover agem, do mesmo jeito que o menu de cores
        self.selecionar_campo = discord.ui.Select(
            placeholder="Selecione um campo", row=0)
        self.selecionar_campo.callback = self._escolher_campo
        self.voltar_campos = discord.ui.Button(
            emoji=EMOJI_VOLTAR, style=discord.ButtonStyle.secondary, row=1)
        self.voltar_campos.callback = self._sair_dos_campos
        self.adicionar_campo = discord.ui.Button(
            label="Adicionar Campo",
            emoji=EMOJIS_APP.get("add_embed"),
            style=discord.ButtonStyle.success,
            row=1,
        )
        self.adicionar_campo.callback = self._abrir_novo_campo
        self.editar_campo = discord.ui.Button(
            label="Editar Campo",
            emoji=EMOJIS_APP.get("editar_campos_embed"),
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.editar_campo.callback = self._abrir_edicao_de_campo
        self.remover_campo = discord.ui.Button(
            label="Remover Campo",
            emoji=EMOJIS_APP.get("remove_embed"),
            style=discord.ButtonStyle.danger,
            row=1,
        )
        self.remover_campo.callback = self._remover_campo
        # Componentes do modo de remoção de botões, pelo mesmo motivo
        self.selecionar_botao = discord.ui.Select(
            placeholder="Selecione o botão que quer remover", row=0)
        self.selecionar_botao.callback = self._remover_botao_escolhido
        self.voltar_botoes = discord.ui.Button(
            emoji=EMOJI_VOLTAR, style=discord.ButtonStyle.secondary, row=1)
        self.voltar_botoes.callback = self._sair_dos_botoes
        # Volta dos submodos que reaproveitam os botões já declarados (JSON e Enviar).
        # Fica na mesma linha deles para os três saírem lado a lado.
        self.voltar_acoes = discord.ui.Button(
            emoji=EMOJI_VOLTAR, style=discord.ButtonStyle.secondary, row=1)
        self.voltar_acoes.callback = self._sair_do_submodo
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
        self.modo = None
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

    # --------------------------------------------------------------- campos

    async def _escolher_campo(self, interaction: discord.Interaction):
        """A escolha no menu só marca em qual campo Editar e Remover vão agir."""
        self.campo_atual = int(self.selecionar_campo.values[0])
        self.recarregar()
        await self.atualizar(interaction)

    async def _sair_dos_campos(self, interaction: discord.Interaction):
        self.modo = None
        self.recarregar()
        await self.atualizar(interaction)

    async def _abrir_novo_campo(self, interaction: discord.Interaction):
        if len(self.campos_atuais) >= CAMPO_LIMITE_POR_EMBED:
            await interaction.response.send_message(
                f"Uma embed aceita no máximo {CAMPO_LIMITE_POR_EMBED} campos.", ephemeral=True
            )
            return
        await interaction.response.send_modal(CampoEmbedModal(self))

    async def _abrir_edicao_de_campo(self, interaction: discord.Interaction):
        if self.campo_atual is None:
            await interaction.response.send_message(
                "Selecione no menu o campo que quer editar.", ephemeral=True
            )
            return
        await interaction.response.send_modal(CampoEmbedModal(self, self.campo_atual))

    async def _remover_campo(self, interaction: discord.Interaction):
        if self.campo_atual is None:
            await interaction.response.send_message(
                "Selecione no menu o campo que quer remover.", ephemeral=True
            )
            return

        campos = [dict(c) for c in self.campos_atuais]
        campos.pop(self.campo_atual)
        self.campo_atual = None
        self.aplicar_alteracoes({"campos": campos})
        self.recarregar()
        await self.atualizar(interaction)

    # --------------------------------------------------------------- botões

    async def _remover_botao_escolhido(self, interaction: discord.Interaction):
        """A escolha no menu já remove: não há um segundo clique para confirmar."""
        botoes = [dict(b) for b in self.botoes_do_slot(self.slot_atual)]
        indice = int(self.selecionar_botao.values[0])
        if 0 <= indice < len(botoes):
            botoes.pop(indice)
        self.registrar_rascunho_botoes(self.slot_atual, botoes)
        # Sem botões não sobra o que escolher: o painel volta para a edição
        if not botoes:
            self.modo = None
        self.recarregar()
        await self.atualizar(interaction)

    async def _sair_dos_botoes(self, interaction: discord.Interaction):
        self.modo = None
        self.recarregar()
        await self.atualizar(interaction)

    async def _sair_do_submodo(self, interaction: discord.Interaction):
        self.modo = None
        self.recarregar()
        await self.atualizar(interaction)

    def _montar_botoes_de_link(self) -> list[discord.ui.Button]:
        """Os botões de link como eles vão sair na mensagem final. Só cabe uma
        linha no painel, então o excedente aparece apenas na lista do texto."""
        itens = []
        for dados in self.botoes_do_slot(self.slot_atual)[:BOTAO_POR_LINHA]:
            try:
                itens.append(discord.ui.Button(
                    label=(dados["rotulo"] or "")[:80],
                    url=dados["url"],
                    emoji=dados.get("emoji") or None,
                    row=0,
                ))
            except Exception:
                # Botão gravado com dado que o Discord recusa: some da prévia em
                # vez de derrubar o painel inteiro na hora de renderizar
                continue
        return itens

    def _sanear_emojis(self):
        """Reaponta os emojis dos botões para os IDs atuais da aplicação, usando o
        nome como chave. Um emoji apagado sai do botão em vez de derrubar o painel
        inteiro com 'Invalid emoji' na hora de renderizar."""
        if not EMOJIS_APP:
            return
        manuais = (self.voltar_cores, self.voltar_botoes, self.voltar_acoes,
                   self.voltar_campos, self.editar_campo,
                   self.adicionar_campo, self.remover_campo)
        for item in [*self.children, *manuais]:
            emoji = getattr(item, "emoji", None)
            # Emoji unicode (sem id) não depende da aplicação
            if emoji is None or emoji.id is None:
                continue
            item.emoji = EMOJIS_APP.get(emoji.name)

    async def _trocar_parte(self, interaction: discord.Interaction):
        """O menu troca de embed e também empilha ou tira uma: as duas ações
        moram aqui porque não sobra espaço para botões próprios no painel."""
        escolha = self.selecionar_parte.values[0]
        # A seleção de campo é por embed: outra embed tem outra lista de campos
        self.campo_atual = None
        if escolha == PARTE_ADICIONAR:
            await self._adicionar_parte(interaction)
            return
        if escolha == PARTE_REMOVER:
            await self._remover_parte(interaction)
            return

        self.parte_atual = int(escolha)
        self.recarregar()
        await self.atualizar(interaction)

    async def _adicionar_parte(self, interaction: discord.Interaction):
        """Empilha mais uma embed na mesma mensagem (o Discord aceita até 10)."""
        partes = [dict(p) for p in self.partes_do_slot(self.slot_atual)]
        if len(partes) >= EMBED_PARTES_POR_SLOT:
            await interaction.response.send_message(
                f"Uma mensagem aceita no máximo {EMBED_PARTES_POR_SLOT} embeds.", ephemeral=True
            )
            return

        # A nova parte herda só o nome: ele identifica o slot, não a embed
        partes.append({**embed_padrao(), "nome": partes[0].get("nome")})
        self.registrar_rascunho(self.slot_atual, partes)
        self.parte_atual = len(partes)
        self.recarregar()
        await self.atualizar(interaction)

    async def _remover_parte(self, interaction: discord.Interaction):
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

    # ---------------------------------------------------------------- estado

    def recarregar(self):
        """Relê as embeds do usuário no banco e sincroniza os componentes do painel."""
        self.embeds = embed_listar(self.id_usuario)
        self.botoes = botao_listar(self.id_usuario)
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
            self._montar_menu_de_partes()
            self._montar_menu_de_botoes()
            self._montar_menu_de_campos()
            self._montar_menu_de_cores()

        self._sincronizar_componentes()

    def _montar_menu_de_partes(self):
        """As embeds empilhadas na mensagem, seguidas das ações de empilhar e tirar."""
        partes = self.partes_do_slot(self.slot_atual)
        self.parte_atual = min(max(self.parte_atual, 1), len(partes))
        self.selecionar_parte.placeholder = f"Editando a embed {self.parte_atual} de {len(partes)}"

        opcoes = [
            discord.SelectOption(
                label=f"Embed {numero}",
                value=str(numero),
                description=self._resumo(dados),
                emoji=EMOJIS_NUMEROS[numero - 1],
                default=numero == self.parte_atual,
            )
            for numero, dados in enumerate(partes, start=1)
        ]
        if len(partes) < EMBED_PARTES_POR_SLOT:
            opcoes.append(discord.SelectOption(
                label="Adicionar Embed",
                value=PARTE_ADICIONAR,
                description="Empilha mais uma embed nesta mesma mensagem",
                emoji=EMOJIS_APP.get("add_embed"),
            ))
        if len(partes) > 1:
            opcoes.append(discord.SelectOption(
                label="Remover Embed",
                value=PARTE_REMOVER,
                description=f"Tira a embed {self.parte_atual} da mensagem",
                emoji=EMOJIS_APP.get("remove_embed"),
            ))
        self.selecionar_parte.options = opcoes

    def _montar_menu_de_botoes(self):
        """Lista os botões da mensagem no menu de remoção, na ordem em que aparecem."""
        botoes = self.botoes_do_slot(self.slot_atual)
        self.adicionar_botao.disabled = len(botoes) >= BOTAO_LIMITE_POR_SLOT

        if not botoes:
            # O Discord exige ao menos uma opção mesmo em um menu desabilitado
            self.selecionar_botao.disabled = True
            self.selecionar_botao.options = [
                discord.SelectOption(label="Nenhum botão criado", value="0")
            ]
            return

        self.selecionar_botao.disabled = False
        # O ícone segue a posição no menu, e não o emoji do botão: um emoji de
        # servidor apagado derrubaria o painel na hora de renderizar as opções
        self.selecionar_botao.options = [
            discord.SelectOption(
                label=b["rotulo"][:100],
                value=str(posicao),
                description=b["url"][:100],
                emoji=EMOJIS_NUMEROS[posicao],
            )
            for posicao, b in enumerate(botoes)
        ]

    def _montar_menu_de_campos(self):
        """Lista os campos da embed em edição, na ordem em que aparecem nela."""
        campos = self.campos_atuais
        # Um campo removido não deixa seleção pendente atrás de si
        if self.campo_atual is not None and not 0 <= self.campo_atual < len(campos):
            self.campo_atual = None

        self.adicionar_campo.disabled = len(campos) >= CAMPO_LIMITE_POR_EMBED
        self.editar_campo.disabled = self.campo_atual is None
        self.remover_campo.disabled = self.campo_atual is None

        if not campos:
            # O Discord exige ao menos uma opção mesmo em um menu desabilitado
            self.selecionar_campo.disabled = True
            self.selecionar_campo.placeholder = "Nenhum campo criado — use Adicionar Campo"
            self.selecionar_campo.options = [
                discord.SelectOption(label="Nenhum campo criado", value="0")
            ]
            return

        self.selecionar_campo.disabled = False
        self.selecionar_campo.placeholder = "Selecione o campo que quer editar ou remover"
        # O ícone segue a posição no menu, como nos outros seletores do painel
        self.selecionar_campo.options = [
            discord.SelectOption(
                label=(c.get("nome") or "Sem título")[:100],
                value=str(posicao),
                description=((c.get("valor") or "").strip() or "Sem parágrafo")[:100],
                emoji=EMOJIS_NUMEROS[posicao],
                default=posicao == self.campo_atual,
            )
            for posicao, c in enumerate(campos)
        ]

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

        if self.modo == MODO_CORES:
            self.add_item(self.selecionar_cor)
            for item in (self.voltar_cores, self.encontrar_cores,
                         self.adicionar_cor, self.remover_cor):
                self.add_item(item)
            return

        if self.modo == MODO_CAMPOS:
            self.add_item(self.selecionar_campo)
            for item in (self.voltar_campos, self.adicionar_campo,
                         self.editar_campo, self.remover_campo):
                self.add_item(item)
            return

        if self.modo == MODO_BOTOES:
            self.add_item(self.selecionar_botao)
            self.add_item(self.voltar_botoes)
            return

        if self.modo == MODO_JSON:
            for item in (self.voltar_acoes, self.importar_json, self.exportar_json):
                self.add_item(item)
            return

        if self.modo == MODO_ENVIAR:
            for item in (self.voltar_acoes, self.enviar, self.enviar_personalizado):
                self.add_item(item)
            return

        # Linha 0: os botões de link como vão sair na mensagem, colados na embed
        for botao in self._montar_botoes_de_link():
            self.add_item(botao)
        # Linha 1: as embeds empilhadas na mensagem e as ações de empilhar e tirar
        self.add_item(self.selecionar_parte)
        for item in (self.editar_titulo, self.editar_descricao, self.editar_cor,
                     self.editar_autor, self.editar_rodape):
            self.add_item(item)
        self.add_item(self.editar_imagem)
        self.add_item(self.editar_campos)
        self.add_item(self.adicionar_botao)
        # Sem nenhum botão criado não há o que remover
        if self.botoes_do_slot(self.slot_atual):
            self.add_item(self.remover_botao)
        self.add_item(self.renomear)
        self.add_item(self.voltar)
        self.add_item(self.abrir_json)
        # O botão de salvar só existe enquanto houver alteração pendente
        if self.tem_alteracoes:
            self.add_item(self.salvar)
        self.add_item(self.excluir_embed)
        self.add_item(self.abrir_enviar)

    @property
    def tem_alteracoes(self) -> bool:
        return self.slot_atual is not None and (
            self.slot_atual in self.rascunhos or self.slot_atual in self.rascunhos_botoes
        )

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
        return salvas or [embed_padrao()]

    def botoes_do_slot(self, slot: int) -> list[dict]:
        """Botões da mensagem do slot: o rascunho pendente, se houver; senão o salvo."""
        if slot in self.rascunhos_botoes:
            return self.rascunhos_botoes[slot]
        return [b for b in self.botoes if b["slot"] == slot]

    def dados_do_slot(self, slot: int) -> dict:
        """Primeira embed do slot — é dela que saem o nome e o resumo do menu."""
        return self.partes_do_slot(slot)[0]

    @property
    def dados_atuais(self) -> dict:
        """Dados da embed selecionada; sem seleção, o template de exemplo."""
        if self.slot_atual is None:
            return embed_padrao()
        partes = self.partes_do_slot(self.slot_atual)
        return partes[min(self.parte_atual, len(partes)) - 1]

    @property
    def campos_atuais(self) -> list[dict]:
        """Campos da embed selecionada, na ordem em que aparecem nela."""
        return self.dados_atuais.get("campos") or []

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

    def registrar_rascunho_botoes(self, slot: int, botoes: list[dict]):
        """O mesmo do rascunho da embed, para a lista de botões da mensagem."""
        salvos = [b for b in self.botoes if b["slot"] == slot]
        igual = len(salvos) == len(botoes) and all(
            all(a.get(campo) == b.get(campo) for campo in BOTAO_CAMPOS)
            for a, b in zip(botoes, salvos)
        )
        if igual:
            self.rascunhos_botoes.pop(slot, None)
        else:
            self.rascunhos_botoes[slot] = botoes

    def conteudo(self) -> str:
        ocupados = self.slots_ocupados
        total = f"({len(ocupados)}/{EMBED_LIMITE_POR_USUARIO})"
        if not ocupados:
            linha = "**Painel de Criação de Embed**"
        elif self.slot_atual is None:
            linha = f"**Painel de Criação e Seleção de Embed** - {total}"
        else:
            nome_embed = self.rotulo_do_slot(self.slot_atual)
            titulo_painel = CABECALHO_POR_MODO.get(self.modo, "Painel de Edição de Embed")
            cabecalho = f'**{titulo_painel}** - Editando "{nome_embed}"'
            quantidade = len(self.partes_do_slot(self.slot_atual))
            if quantidade > 1:
                cabecalho += f" - embed {self.parte_atual} de {quantidade}"
            partes = [cabecalho]
            # A prévia mostra uma linha de botões; o que passa disso vai no texto
            restantes = self.botoes_do_slot(self.slot_atual)[BOTAO_POR_LINHA:]
            if restantes and self.modo is None:
                # O emoji fica fora da crase: dentro dela o Discord não o renderiza
                lista = " ".join(
                    f"{b['emoji'] + ' ' if b.get('emoji') else ''}`{b['rotulo']}`"
                    for b in restantes
                )
                partes.append(
                    f"**Botões fora da prévia** (a mensagem enviada mostra todos): {lista}"
                )
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
            botao_remover(self.id_usuario, slot)
        self.rascunhos.pop(slot, None)
        self.rascunhos_botoes.pop(slot, None)
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
        self.modo = None
        self.campo_atual = None
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Adicionar Embed", emoji="<:new_embed:1536200609827524658>", style=discord.ButtonStyle.success, row=1)
    async def adicionar_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NovaEmbedModal(self))

    # ----------------------------------------------------------- modo edição

    @discord.ui.button(label="Título", emoji="<:title_embed:1536201573200564315>", style=discord.ButtonStyle.secondary, row=2)
    async def editar_titulo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TituloModal(self))

    @discord.ui.button(label="Descrição", emoji="<:description_embed:1536155252498104340>", style=discord.ButtonStyle.secondary, row=2)
    async def editar_descricao(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DescricaoModal(self))

    @discord.ui.button(label="Cor", emoji="<:color_embed:1536200617217761350>", style=discord.ButtonStyle.secondary, row=2)
    async def editar_cor(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.modo = MODO_CORES
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Autor", emoji="<:author_embed:1536155249096785980>", style=discord.ButtonStyle.secondary, row=2)
    async def editar_autor(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AutorModal(self))

    @discord.ui.button(label="Rodapé", emoji="<:rodape_embed:1536200607155888139>", style=discord.ButtonStyle.secondary, row=2)
    async def editar_rodape(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RodapeModal(self))

    @discord.ui.button(label="Imagem e Thumbnail", emoji="<:image_embed:1536155250149564437>", style=discord.ButtonStyle.secondary, row=3)
    async def editar_imagem(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ImagemModal(self))

    @discord.ui.button(label="Editar Campos", emoji="<:editar_campos_embed:1536200613346672760>", style=discord.ButtonStyle.secondary, row=3)
    async def editar_campos(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.modo = MODO_CAMPOS
        # O painel abre sem campo escolhido: Editar e Remover ficam desabilitados
        self.campo_atual = None
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Adicionar Botão", emoji="<:add_button_embed:1536155254272557197>", style=discord.ButtonStyle.secondary, row=3)
    async def adicionar_botao(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BotaoLinkModal(self))

    @discord.ui.button(label="Remover Botão", emoji="<:remove_button_embed:1536155255639646268>", style=discord.ButtonStyle.secondary, row=3)
    async def remover_botao(self, interaction: discord.Interaction, button: discord.ui.Button):
        botoes = self.botoes_do_slot(self.slot_atual)
        # O botão nem aparece sem botões criados; a checagem cobre o painel desatualizado
        if not botoes:
            await interaction.response.send_message(
                "Esta mensagem ainda não tem botões. Use **Adicionar Botão** para criar um.",
                ephemeral=True,
            )
            return

        # Com um botão só não há escolha a fazer: o clique já remove
        if len(botoes) == 1:
            self.registrar_rascunho_botoes(self.slot_atual, [])
            self.modo = None
            self.recarregar()
            await self.atualizar(interaction)
            return

        self.modo = MODO_BOTOES
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Renomear", emoji="<:renomear_embed:1536200611006259270>", style=discord.ButtonStyle.secondary, row=3)
    async def renomear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenomearModal(self))

    @discord.ui.button(emoji="<:voltar_embed:1536200612226793482>", style=discord.ButtonStyle.secondary, row=4)
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Os rascunhos são guardados por slot, então voltar não descarta nada
        self.slot_atual = None
        self.parte_atual = 1
        self.modo = None
        self.campo_atual = None
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="JSON", emoji="<:import_embed:1536154668906979358>", style=discord.ButtonStyle.primary, row=4)
    async def abrir_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.modo = MODO_JSON
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Importar JSON", emoji="<:import_embed:1536154668906979358>", style=discord.ButtonStyle.primary, row=1)
    async def importar_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: carregar uma embed a partir de um JSON colado pelo usuário
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Exportar JSON", emoji="<:export_embed:1536154667359408221>", style=discord.ButtonStyle.primary, row=1)
    async def exportar_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: devolver a embed atual serializada em JSON
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Salvar Alterações", emoji="<:save_embed:1536200608510648381>", style=discord.ButtonStyle.success, row=4)
    async def salvar(self, interaction: discord.Interaction, button: discord.ui.Button):
        slot = self.slot_atual
        rascunho = self.rascunhos.get(slot)
        rascunho_botoes = self.rascunhos_botoes.get(slot)
        if rascunho is None and rascunho_botoes is None:
            await interaction.response.send_message("Não há alterações pendentes.", ephemeral=True)
            return

        # O limite é conferido de novo aqui: o painel pode estar aberto há tempo
        if slot not in self.slots_salvos and len(self.slots_salvos) >= EMBED_LIMITE_POR_USUARIO:
            await interaction.response.send_message(
                f"Você já atingiu o limite de {EMBED_LIMITE_POR_USUARIO} embeds.", ephemeral=True
            )
            return

        self.rascunhos.pop(slot, None)
        self.rascunhos_botoes.pop(slot, None)
        if rascunho is not None:
            embed_salvar_slot(self.id_usuario, slot, rascunho)
        if rascunho_botoes is not None:
            botao_salvar_slot(self.id_usuario, slot, rascunho_botoes)

        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Excluir Embed", emoji="<:deletar_embed:1536192015010766878>", style=discord.ButtonStyle.danger, row=4)
    async def excluir_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ExcluirEmbedModal(self))

    @discord.ui.button(label="Enviar", emoji="<:enviar_embed:1536200615422853161>", style=discord.ButtonStyle.success, row=4)
    async def abrir_enviar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.modo = MODO_ENVIAR
        self.recarregar()
        await self.atualizar(interaction)

    @discord.ui.button(label="Enviar Personalizado", emoji="<:enviar_personalizado_embed:1536203707052462120>", style=discord.ButtonStyle.success, row=1)
    async def enviar_personalizado(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: enviar a mensagem via webhook com nome/avatar personalizados
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)

    @discord.ui.button(label="Enviar", emoji="<:enviar_embed:1536200615422853161>", style=discord.ButtonStyle.success, row=1)
    async def enviar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: enviar a embed montada no canal escolhido
        await interaction.response.send_message("Ainda não implementado.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CriarEmbed(bot))
