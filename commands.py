from __future__ import annotations

import asyncio
import json
import os
import random
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

DATA_FILE = Path(os.getenv("AZURE_DATA_FILE", "azure_data.json"))
OWNER_ID = int(os.getenv("OWNER_ID", "0"))


def load_data() -> dict:
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"warnings": {}, "welcome_channel": {}, "goodbye_channel": {}, "log_channel": {}}


def save_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_owner(interaction: discord.Interaction) -> bool:
    return OWNER_ID != 0 and interaction.user.id == OWNER_ID


async def log_action(guild: discord.Guild, message: str) -> None:
    data = load_data()
    channel_id = data.get("log_channel", {}).get(str(guild.id))
    if not channel_id:
        return
    channel = guild.get_channel(int(channel_id))
    if isinstance(channel, discord.TextChannel):
        try:
            await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            pass


def has_manage_messages():
    return app_commands.checks.has_permissions(manage_messages=True)


def has_moderate_members():
    return app_commands.checks.has_permissions(moderate_members=True)


def has_manage_guild():
    return app_commands.checks.has_permissions(manage_guild=True)


def has_administrator():
    return app_commands.checks.has_permissions(administrator=True)


def has_manage_roles():
    return app_commands.checks.has_permissions(manage_roles=True)


def has_manage_channels():
    return app_commands.checks.has_permissions(manage_channels=True)


class InfoCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Muestra las categorías de comandos.")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(title="AzureSMP Bot • Comandos", color=discord.Color.blurple())
        embed.add_field(name="Información", value="`/ping` `/botinfo` `/serverinfo` `/userinfo` `/avatar` `/banner` `/roleinfo` `/channelinfo` `/invite`", inline=False)
        embed.add_field(name="Moderación", value="`/clear` `/kick` `/ban` `/unban` `/timeout` `/untimeout` `/warn` `/warnings` `/purgeuser` `/slowmode`", inline=False)
        embed.add_field(name="Comunidad", value="`/poll` `/suggest` `/announce` `/welcome` `/goodbye` `/serverrules` `/membercount` `/say` `/embed` `/remind`", inline=False)
        embed.add_field(name="Diversión", value="`/coinflip` `/dice` `/8ball` `/choose` `/rps` `/joke` `/compliment` `/ship` `/meme` `/fact`", inline=False)
        embed.add_field(name="Administración", value="`/online` `/offline` `/setstatus` `/setnick` `/roleadd` `/roleremove` `/lock` `/unlock` `/setlog` `/sync`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="botinfo", description="Muestra información del bot.")
    async def botinfo(self, interaction: discord.Interaction):
        embed = discord.Embed(title=str(self.bot.user), color=discord.Color.blurple())
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="Latencia", value=f"{round(self.bot.latency * 1000)} ms")
        embed.add_field(name="Servidores", value=str(len(self.bot.guilds)))
        embed.add_field(name="Discord.py", value=discord.__version__)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Muestra información de este servidor.")
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=guild.name, color=discord.Color.blurple())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Miembros", value=str(guild.member_count or 0))
        embed.add_field(name="Canales", value=str(len(guild.channels)))
        embed.add_field(name="Roles", value=str(len(guild.roles)))
        embed.add_field(name="Creado", value=discord.utils.format_dt(guild.created_at, style="D"), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Muestra información de un usuario.")
    @app_commands.guild_only()
    async def userinfo(self, interaction: discord.Interaction, usuario: discord.Member | None = None):
        member = usuario or interaction.user
        embed = discord.Embed(title=f"Usuario: {member}", color=discord.Color.blurple())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=str(member.id))
        embed.add_field(name="Cuenta creada", value=discord.utils.format_dt(member.created_at, style="D"), inline=False)
        embed.add_field(name="Entró al servidor", value=discord.utils.format_dt(member.joined_at, style="D") if member.joined_at else "Desconocido", inline=False)
        embed.add_field(name="Roles", value=str(max(0, len(member.roles) - 1)))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Muestra el avatar de un usuario.")
    async def avatar(self, interaction: discord.Interaction, usuario: discord.User | None = None):
        user = usuario or interaction.user
        embed = discord.Embed(title=f"Avatar de {user}", color=discord.Color.blurple())
        embed.set_image(url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="banner", description="Muestra el banner de un usuario si tiene uno.")
    async def banner(self, interaction: discord.Interaction, usuario: discord.User | None = None):
        user = usuario or interaction.user
        try:
            user = await self.bot.fetch_user(user.id)
        except discord.HTTPException:
            pass
        if not user.banner:
            await interaction.response.send_message("Ese usuario no tiene un banner visible.", ephemeral=True)
            return
        embed = discord.Embed(title=f"Banner de {user}", color=discord.Color.blurple())
        embed.set_image(url=user.banner.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roleinfo", description="Muestra información de un rol.")
    @app_commands.guild_only()
    async def roleinfo(self, interaction: discord.Interaction, rol: discord.Role):
        embed = discord.Embed(title=rol.name, color=rol.color)
        embed.add_field(name="ID", value=str(rol.id))
        embed.add_field(name="Miembros", value=str(len(rol.members)))
        embed.add_field(name="Mencionable", value="Sí" if rol.mentionable else "No")
        embed.add_field(name="Creado", value=discord.utils.format_dt(rol.created_at, style="D"))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="channelinfo", description="Muestra información de un canal.")
    @app_commands.guild_only()
    async def channelinfo(self, interaction: discord.Interaction, canal: discord.TextChannel | None = None):
        channel = canal or interaction.channel
        embed = discord.Embed(title=f"#{channel.name}", color=discord.Color.blurple())
        embed.add_field(name="ID", value=str(channel.id))
        embed.add_field(name="Categoría", value=channel.category.name if channel.category else "Ninguna")
        embed.add_field(name="Creado", value=discord.utils.format_dt(channel.created_at, style="D"))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="invite", description="Muestra un enlace de invitación al servidor.")
    @app_commands.guild_only()
    async def invite(self, interaction: discord.Interaction):
        guild = interaction.guild
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).create_instant_invite:
                try:
                    invite = await channel.create_invite(max_age=3600, max_uses=1, reason="Comando /invite")
                    await interaction.response.send_message(f"Invitación (válida por 1 hora): {invite.url}", ephemeral=True)
                    return
                except discord.HTTPException:
                    continue
        await interaction.response.send_message("No tengo permiso para crear invitaciones.", ephemeral=True)


class ModerationCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Borra mensajes recientes del canal.")
    @has_manage_messages()
    @app_commands.guild_only()
    async def clear(self, interaction: discord.Interaction, cantidad: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=cantidad)
        await interaction.followup.send(f"Se borraron {len(deleted)} mensajes.", ephemeral=True)
        await log_action(interaction.guild, f"🧹 {interaction.user} borró {len(deleted)} mensajes en {interaction.channel.mention}.")

    @app_commands.command(name="kick", description="Expulsa a un miembro del servidor.")
    @has_moderate_members()
    @app_commands.guild_only()
    async def kick(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Sin motivo indicado"):
        if usuario.top_role >= interaction.user.top_role and not is_owner(interaction):
            await interaction.response.send_message("No podés expulsar a alguien con un rol igual o superior al tuyo.", ephemeral=True); return
        try:
            await usuario.kick(reason=f"{interaction.user}: {motivo}")
        except discord.HTTPException:
            await interaction.response.send_message("No pude expulsar a ese miembro. Revisá mi jerarquía y permisos.", ephemeral=True); return
        await interaction.response.send_message(f"Se expulsó a **{usuario}**. Motivo: {motivo}")
        await log_action(interaction.guild, f"👢 {usuario} expulsado por {interaction.user}. Motivo: {motivo}")

    @app_commands.command(name="ban", description="Banea a un usuario del servidor.")
    @has_moderate_members()
    @app_commands.guild_only()
    async def ban(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Sin motivo indicado"):
        if usuario.top_role >= interaction.user.top_role and not is_owner(interaction):
            await interaction.response.send_message("No podés banear a alguien con un rol igual o superior al tuyo.", ephemeral=True); return
        try:
            await usuario.ban(reason=f"{interaction.user}: {motivo}")
        except discord.HTTPException:
            await interaction.response.send_message("No pude banear a ese miembro. Revisá mi jerarquía y permisos.", ephemeral=True); return
        await interaction.response.send_message(f"Se baneó a **{usuario}**. Motivo: {motivo}")
        await log_action(interaction.guild, f"🔨 {usuario} baneado por {interaction.user}. Motivo: {motivo}")

    @app_commands.command(name="unban", description="Desbanea a un usuario usando su ID.")
    @has_moderate_members()
    @app_commands.guild_only()
    async def unban(self, interaction: discord.Interaction, usuario_id: str, motivo: str = "Sin motivo indicado"):
        try:
            user = await self.bot.fetch_user(int(usuario_id))
            await interaction.guild.unban(user, reason=f"{interaction.user}: {motivo}")
        except (ValueError, discord.HTTPException):
            await interaction.response.send_message("No pude desbanearlo. Revisá el ID y la lista de baneados.", ephemeral=True); return
        await interaction.response.send_message(f"Se desbaneó a **{user}**.")

    @app_commands.command(name="timeout", description="Aplica timeout de 1 a 40320 minutos.")
    @has_moderate_members()
    @app_commands.guild_only()
    async def timeout(self, interaction: discord.Interaction, usuario: discord.Member, minutos: app_commands.Range[int, 1, 40320], motivo: str = "Sin motivo indicado"):
        if usuario.top_role >= interaction.user.top_role and not is_owner(interaction):
            await interaction.response.send_message("No podés moderar a alguien con un rol igual o superior al tuyo.", ephemeral=True); return
        try:
            await usuario.timeout(timedelta(minutes=minutos), reason=f"{interaction.user}: {motivo}")
        except discord.HTTPException:
            await interaction.response.send_message("No pude aplicar el timeout. Revisá permisos y jerarquía.", ephemeral=True); return
        await interaction.response.send_message(f"Timeout aplicado a {usuario.mention} por {minutos} minutos. Motivo: {motivo}")
        await log_action(interaction.guild, f"⏳ Timeout a {usuario} por {minutos} minutos. Moderador: {interaction.user}. Motivo: {motivo}")

    @app_commands.command(name="untimeout", description="Quita el timeout de un miembro.")
    @has_moderate_members()
    @app_commands.guild_only()
    async def untimeout(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Sin motivo indicado"):
        try:
            await usuario.timeout(None, reason=f"{interaction.user}: {motivo}")
        except discord.HTTPException:
            await interaction.response.send_message("No pude quitar el timeout.", ephemeral=True); return
        await interaction.response.send_message(f"Se quitó el timeout de {usuario.mention}.")

    @app_commands.command(name="warn", description="Registra una advertencia para un miembro.")
    @has_moderate_members()
    @app_commands.guild_only()
    async def warn(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str):
        data = load_data()
        key = f"{interaction.guild.id}:{usuario.id}"
        data.setdefault("warnings", {}).setdefault(key, []).append({
            "moderator": interaction.user.id, "reason": motivo,
            "time": datetime.now(timezone.utc).isoformat()
        })
        save_data(data)
        count = len(data["warnings"][key])
        await interaction.response.send_message(f"Advertencia registrada para {usuario.mention}. Total: **{count}**.")
        await log_action(interaction.guild, f"⚠️ Advertencia a {usuario} por {interaction.user}: {motivo}")

    @app_commands.command(name="warnings", description="Consulta las advertencias de un miembro.")
    @has_moderate_members()
    @app_commands.guild_only()
    async def warnings(self, interaction: discord.Interaction, usuario: discord.Member):
        data = load_data()
        entries = data.get("warnings", {}).get(f"{interaction.guild.id}:{usuario.id}", [])
        if not entries:
            await interaction.response.send_message(f"{usuario.mention} no tiene advertencias registradas.", ephemeral=True); return
        lines = [f"**{i}.** {item['reason']} — <@{item['moderator']}> · {item['time'][:10]}" for i, item in enumerate(entries[-10:], 1)]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="purgeuser", description="Borra mensajes recientes de un miembro en este canal.")
    @has_manage_messages()
    @app_commands.guild_only()
    async def purgeuser(self, interaction: discord.Interaction, usuario: discord.Member, cantidad: app_commands.Range[int, 1, 100] = 25):
        await interaction.response.defer(ephemeral=True)
        matched = 0
        def target_message(message: discord.Message) -> bool:
            nonlocal matched
            if message.author.id != usuario.id or matched >= cantidad:
                return False
            matched += 1
            return True
        deleted = await interaction.channel.purge(limit=500, check=target_message, bulk=True)
        await interaction.followup.send(f"Se borraron {len(deleted)} mensajes de {usuario.mention}.", ephemeral=True)

    @app_commands.command(name="slowmode", description="Configura el modo lento del canal (0 a 21600 segundos).")
    @has_manage_messages()
    @app_commands.guild_only()
    async def slowmode(self, interaction: discord.Interaction, segundos: app_commands.Range[int, 0, 21600]):
        await interaction.channel.edit(slowmode_delay=segundos, reason=f"Configurado por {interaction.user}")
        await interaction.response.send_message(f"Modo lento configurado en {segundos} segundos.")


class CommunityCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Crea una encuesta con reacciones.")
    async def poll(self, interaction: discord.Interaction, pregunta: str, opcion_a: str, opcion_b: str):
        embed = discord.Embed(title="📊 Encuesta", description=f"**{pregunta}**\n\n🇦 {opcion_a}\n🇧 {opcion_b}", color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        for emoji in ("🇦", "🇧"):
            try: await message.add_reaction(emoji)
            except discord.HTTPException: pass

    @app_commands.command(name="suggest", description="Envía una sugerencia al canal actual.")
    async def suggest(self, interaction: discord.Interaction, sugerencia: str):
        embed = discord.Embed(title="💡 Nueva sugerencia", description=sugerencia, color=discord.Color.green())
        embed.set_footer(text=f"Sugerido por {interaction.user}")
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        for emoji in ("👍", "👎"):
            try: await message.add_reaction(emoji)
            except discord.HTTPException: pass

    @app_commands.command(name="announce", description="Publica un anuncio en un canal.")
    @has_manage_guild()
    @app_commands.guild_only()
    async def announce(self, interaction: discord.Interaction, canal: discord.TextChannel, titulo: str, mensaje: str):
        embed = discord.Embed(title=titulo, description=mensaje, color=discord.Color.blurple(), timestamp=datetime.now(timezone.utc))
        await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.send_message(f"Anuncio publicado en {canal.mention}.", ephemeral=True)

    @app_commands.command(name="welcome", description="Configura el canal de bienvenida.")
    @has_manage_guild()
    @app_commands.guild_only()
    async def welcome(self, interaction: discord.Interaction, canal: discord.TextChannel):
        data = load_data(); data.setdefault("welcome_channel", {})[str(interaction.guild.id)] = canal.id; save_data(data)
        await interaction.response.send_message(f"Bienvenidas configuradas en {canal.mention}.", ephemeral=True)

    @app_commands.command(name="goodbye", description="Configura el canal de despedidas.")
    @has_manage_guild()
    @app_commands.guild_only()
    async def goodbye(self, interaction: discord.Interaction, canal: discord.TextChannel):
        data = load_data(); data.setdefault("goodbye_channel", {})[str(interaction.guild.id)] = canal.id; save_data(data)
        await interaction.response.send_message(f"Despedidas configuradas en {canal.mention}.", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        data = load_data(); channel_id = data.get("welcome_channel", {}).get(str(member.guild.id))
        channel = member.guild.get_channel(int(channel_id)) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            await channel.send(f"¡Bienvenido/a {member.mention} a **{member.guild.name}**!")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        data = load_data(); channel_id = data.get("goodbye_channel", {}).get(str(member.guild.id))
        channel = member.guild.get_channel(int(channel_id)) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            await channel.send(f"**{member}** salió del servidor. ¡Hasta pronto!")

    @app_commands.command(name="serverrules", description="Publica las reglas básicas del servidor.")
    @has_manage_guild()
    @app_commands.guild_only()
    async def serverrules(self, interaction: discord.Interaction, canal: discord.TextChannel, reglas: str):
        embed = discord.Embed(title="📜 Reglas del servidor", description=reglas, color=discord.Color.blurple())
        await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.send_message(f"Reglas publicadas en {canal.mention}.", ephemeral=True)

    @app_commands.command(name="membercount", description="Muestra el número de miembros.")
    @app_commands.guild_only()
    async def membercount(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"👥 **{interaction.guild.name}** tiene **{interaction.guild.member_count or 0}** miembros.")

    @app_commands.command(name="say", description="Envía un mensaje como el bot.")
    @has_manage_guild()
    @app_commands.guild_only()
    async def say(self, interaction: discord.Interaction, mensaje: str):
        await interaction.channel.send(mensaje, allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.send_message("Mensaje enviado.", ephemeral=True)

    @app_commands.command(name="embed", description="Publica un embed personalizado.")
    @has_manage_guild()
    @app_commands.guild_only()
    async def embed_cmd(self, interaction: discord.Interaction, titulo: str, descripcion: str):
        embed = discord.Embed(title=titulo, description=descripcion, color=discord.Color.blurple())
        await interaction.channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.send_message("Embed publicado.", ephemeral=True)

    @app_commands.command(name="remind", description="Te recuerda algo después de unos minutos (máximo 60).")
    async def remind(self, interaction: discord.Interaction, minutos: app_commands.Range[int, 1, 60], recordatorio: str):
        await interaction.response.send_message(f"Te recordaré esto en {minutos} minuto(s).", ephemeral=True)
        await asyncio.sleep(minutos * 60)
        try:
            await interaction.user.send(f"⏰ Recordatorio: {recordatorio}")
        except discord.HTTPException:
            channel = interaction.channel
            if isinstance(channel, discord.TextChannel):
                await channel.send(f"{interaction.user.mention}, recordatorio: {recordatorio}", allowed_mentions=discord.AllowedMentions(users=True))


class FunCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="Lanza una moneda.")
    async def coinflip(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🪙 Salió **{random.choice(['Cara', 'Cruz'])}**.")

    @app_commands.command(name="dice", description="Tira un dado.")
    async def dice(self, interaction: discord.Interaction, caras: app_commands.Range[int, 2, 100] = 6):
        await interaction.response.send_message(f"🎲 Salió **{random.randint(1, caras)}** (dado de {caras} caras).")

    @app_commands.command(name="8ball", description="Responde una pregunta al azar.")
    async def eightball(self, interaction: discord.Interaction, pregunta: str):
        await interaction.response.send_message(f"🎱 {random.choice(['Sí, seguro.', 'No lo creo.', 'Puede ser.', 'Preguntá más tarde.', 'Definitivamente.', 'Las señales dicen que no.'])}")

    @app_commands.command(name="choose", description="Elige una opción de una lista separada por comas.")
    async def choose(self, interaction: discord.Interaction, opciones: str):
        choices = [x.strip() for x in opciones.split(",") if x.strip()]
        if len(choices) < 2:
            await interaction.response.send_message("Escribí al menos dos opciones separadas por comas.", ephemeral=True); return
        await interaction.response.send_message(f"🎯 Elijo: **{random.choice(choices)}**")

    @app_commands.command(name="rps", description="Juega piedra, papel o tijera.")
    async def rps(self, interaction: discord.Interaction, jugada: str):
        pick = jugada.lower()
        if pick not in ("piedra", "papel", "tijera"):
            await interaction.response.send_message("Elegí piedra, papel o tijera.", ephemeral=True); return
        bot_pick = random.choice(["piedra", "papel", "tijera"])
        result = "Empate." if pick == bot_pick else ("Ganaste." if (pick, bot_pick) in {("piedra", "tijera"), ("papel", "piedra"), ("tijera", "papel")} else "Perdiste.")
        await interaction.response.send_message(f"Vos: **{pick}** · Bot: **{bot_pick}**. {result}")

    @app_commands.command(name="joke", description="Cuenta un chiste.")
    async def joke(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice([
            "¿Qué hace una abeja en el gimnasio? ¡Zum-ba!",
            "¿Qué le dice un techo a otro? Techo de menos.",
            "¿Por qué el libro de matemáticas estaba triste? Tenía muchos problemas.",
            "¿Qué hace una computadora en la playa? Busca la red."
        ]))

    @app_commands.command(name="compliment", description="Envía un cumplido amistoso.")
    async def compliment(self, interaction: discord.Interaction, usuario: discord.User | None = None):
        user = usuario or interaction.user
        await interaction.response.send_message(f"✨ {user.mention}, ¡tu buena onda mejora el servidor!")

    @app_commands.command(name="ship", description="Calcula una compatibilidad divertida.")
    async def ship(self, interaction: discord.Interaction, usuario_a: discord.User, usuario_b: discord.User):
        score = secrets.randbelow(101)
        await interaction.response.send_message(f"💞 Compatibilidad de {usuario_a.mention} + {usuario_b.mention}: **{score}%** (solo por diversión).")

    @app_commands.command(name="meme", description="Muestra una idea de meme aleatoria.")
    async def meme(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice([
            "Yo: hoy me duermo temprano. También yo a las 3 AM: un video más.",
            "Cuando el bot funciona a la primera: misión legendaria completada.",
            "El admin: no toquen nada. El servidor: *se cae*."
        ]))

    @app_commands.command(name="fact", description="Comparte un dato curioso.")
    async def fact(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice([
            "Los pulpos tienen tres corazones.",
            "Un día en Venus dura más que su año.",
            "La miel bien conservada puede durar muchísimo tiempo.",
            "Los tiburones existen desde antes que los árboles."
        ]))


class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="online", description="Pone la presencia del bot en línea.")
    @has_administrator()
    async def online(self, interaction: discord.Interaction):
        await self.bot.change_presence(status=discord.Status.online, activity=discord.Game("AzureSMP"))
        await interaction.response.send_message("Presencia cambiada a **En línea**.", ephemeral=True)

    @app_commands.command(name="offline", description="Pone al bot como desconectado sin apagarlo.")
    @has_administrator()
    async def offline(self, interaction: discord.Interaction):
        await self.bot.change_presence(status=discord.Status.invisible)
        await interaction.response.send_message("El bot sigue funcionando, pero aparece desconectado.", ephemeral=True)

    @app_commands.command(name="setstatus", description="Cambia la actividad visible del bot.")
    @has_administrator()
    async def setstatus(self, interaction: discord.Interaction, texto: str):
        await self.bot.change_presence(status=discord.Status.online, activity=discord.Game(texto[:128]))
        await interaction.response.send_message("Actividad actualizada.", ephemeral=True)

    @app_commands.command(name="setnick", description="Cambia el apodo de un miembro.")
    @has_manage_guild()
    @app_commands.guild_only()
    async def setnick(self, interaction: discord.Interaction, usuario: discord.Member, apodo: str):
        try:
            await usuario.edit(nick=apodo[:32], reason=f"Cambiado por {interaction.user}")
        except discord.HTTPException:
            await interaction.response.send_message("No pude cambiar el apodo. Revisá mis permisos y jerarquía.", ephemeral=True); return
        await interaction.response.send_message(f"Apodo actualizado para {usuario.mention}.")

    @app_commands.command(name="roleadd", description="Asigna un rol a un miembro.")
    @has_manage_roles()
    @app_commands.guild_only()
    async def roleadd(self, interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
        if rol >= interaction.guild.me.top_role or (rol >= interaction.user.top_role and not is_owner(interaction)):
            await interaction.response.send_message("La jerarquía de roles impide esta acción.", ephemeral=True); return
        try:
            await usuario.add_roles(rol, reason=f"Asignado por {interaction.user}")
        except discord.HTTPException:
            await interaction.response.send_message("No pude asignar ese rol.", ephemeral=True); return
        await interaction.response.send_message(f"Se asignó {rol.mention} a {usuario.mention}.")

    @app_commands.command(name="roleremove", description="Quita un rol a un miembro.")
    @has_manage_roles()
    @app_commands.guild_only()
    async def roleremove(self, interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
        if rol >= interaction.guild.me.top_role or (rol >= interaction.user.top_role and not is_owner(interaction)):
            await interaction.response.send_message("La jerarquía de roles impide esta acción.", ephemeral=True); return
        try:
            await usuario.remove_roles(rol, reason=f"Quitado por {interaction.user}")
        except discord.HTTPException:
            await interaction.response.send_message("No pude quitar ese rol.", ephemeral=True); return
        await interaction.response.send_message(f"Se quitó {rol.mention} de {usuario.mention}.")

    @app_commands.command(name="lock", description="Bloquea el envío de mensajes en un canal.")
    @has_manage_channels()
    @app_commands.guild_only()
    async def lock(self, interaction: discord.Interaction, canal: discord.TextChannel | None = None):
        channel = canal or interaction.channel
        await channel.set_permissions(interaction.guild.default_role, send_messages=False, reason=f"Bloqueado por {interaction.user}")
        await interaction.response.send_message(f"🔒 {channel.mention} quedó bloqueado.")

    @app_commands.command(name="unlock", description="Desbloquea el envío de mensajes en un canal.")
    @has_manage_channels()
    @app_commands.guild_only()
    async def unlock(self, interaction: discord.Interaction, canal: discord.TextChannel | None = None):
        channel = canal or interaction.channel
        await channel.set_permissions(interaction.guild.default_role, send_messages=None, reason=f"Desbloqueado por {interaction.user}")
        await interaction.response.send_message(f"🔓 {channel.mention} quedó desbloqueado.")

    @app_commands.command(name="setlog", description="Configura el canal de registros de moderación.")
    @has_manage_guild()
    @app_commands.guild_only()
    async def setlog(self, interaction: discord.Interaction, canal: discord.TextChannel):
        data = load_data(); data.setdefault("log_channel", {})[str(interaction.guild.id)] = canal.id; save_data(data)
        await interaction.response.send_message(f"Los registros se enviarán a {canal.mention}.", ephemeral=True)

    @app_commands.command(name="sync", description="Sincroniza los comandos slash del bot.")
    @app_commands.guild_only()
    async def sync(self, interaction: discord.Interaction):
        if not is_owner(interaction) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Solo el propietario del bot o un administrador puede usar este comando.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        synced = await self.bot.tree.sync()
        await interaction.followup.send(f"Se sincronizaron {len(synced)} comandos.", ephemeral=True)


async def setup(bot: commands.Bot):
    # Cada extensión se añade de forma modular; ping ya existe en main.py.
    await bot.add_cog(InfoCommands(bot))
    await bot.add_cog(ModerationCommands(bot))
    await bot.add_cog(CommunityCommands(bot))
    await bot.add_cog(FunCommands(bot))
    await bot.add_cog(AdminCommands(bot))
