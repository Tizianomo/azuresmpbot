from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from datetime import timedelta
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("azure_commands")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DATA_FILE = Path(os.getenv("AZURE_DATA_FILE", "azure_data.json"))

COMMANDS = [
    ("help", "Lista los comandos"), ("botinfo", "Información del bot"),
    ("serverinfo", "Información del servidor"), ("userinfo", "Usuario; argumento opcional: mención o ID"),
    ("avatar", "Avatar de usuario; argumento opcional: mención o ID"), ("banner", "Banner de usuario; argumento opcional: mención o ID"),
    ("roleinfo", "Información de rol; argumento: ID"), ("channelinfo", "Información del canal"),
    ("invite", "Crea invitación de un solo uso"), ("clear", "Borra mensajes; argumento: cantidad 1-100"),
    ("kick", "Expulsa usuario; argumento: mención/ID | motivo"), ("ban", "Banea usuario; argumento: mención/ID | motivo"),
    ("unban", "Desbanea usuario; argumento: ID"), ("timeout", "Silencia usuario; argumento: mención/ID | minutos"),
    ("untimeout", "Quita silencio; argumento: mención/ID"), ("warn", "Advierte usuario; argumento: mención/ID | motivo"),
    ("warnings", "Consulta advertencias; argumento: mención/ID"), ("purgeuser", "Borra mensajes de usuario; argumento: mención/ID"),
    ("slowmode", "Modo lento; argumento: segundos"), ("poll", "Crea encuesta; argumento: pregunta"),
    ("suggest", "Publica sugerencia; argumento: texto"), ("announce", "Anuncio; argumento: título | texto"),
    ("welcome", "Configura canal de bienvenida; argumento: ID canal"), ("goodbye", "Configura canal de despedida; argumento: ID canal"),
    ("serverrules", "Publica reglas; argumento: texto"), ("membercount", "Cantidad de miembros"),
    ("say", "Envía mensaje como bot; argumento: texto"), ("embed", "Publica embed; argumento: título | texto"),
    ("remind", "Recordatorio por DM; argumento: minutos | texto"), ("coinflip", "Lanza una moneda"),
    ("dice", "Tira dado; argumento: caras"), ("8ball", "Respuesta mágica"), ("choose", "Elige entre opciones separadas por comas"),
    ("rps", "Piedra, papel o tijera; argumento: elección"), ("joke", "Cuenta un chiste"),
    ("compliment", "Envía un cumplido"), ("ship", "Compatibilidad divertida; argumento: dos menciones"),
    ("meme", "Meme de texto"), ("fact", "Dato curioso"), ("online", "Muestra al bot en línea"),
    ("offline", "Muestra al bot desconectado sin apagarlo"), ("setstatus", "Cambia actividad; argumento: texto"),
    ("setnick", "Cambia apodo; argumento: mención/ID | apodo"), ("roleadd", "Asigna rol; argumento: ID miembro ID rol"),
    ("roleremove", "Quita rol; argumento: ID miembro ID rol"), ("lock", "Bloquea el canal"),
    ("unlock", "Desbloquea el canal"), ("setlog", "Configura canal de logs; argumento: ID canal"),
    ("sync", "Sincroniza comandos slash")
]

def read_data():
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

def write_data(data):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_member(guild, value):
    value = value.strip().replace("<@", "").replace("!", "").replace(">", "")
    return guild.get_member(int(value)) if value.isdigit() else None

async def execute(bot, interaction, name, argument):
    g = interaction.guild
    arg = argument.strip()
    member = interaction.user if isinstance(interaction.user, discord.Member) else None
    admin = bool(member and member.guild_permissions.administrator)
    manage_messages = bool(member and member.guild_permissions.manage_messages)
    manage_guild = bool(member and member.guild_permissions.manage_guild)
    manage_roles = bool(member and member.guild_permissions.manage_roles)
    manage_channels = bool(member and member.guild_permissions.manage_channels)

    async def error(message="No tenés permisos o los argumentos no son válidos."):
        await interaction.response.send_message(message, ephemeral=True)

    if name == "help":
        embed = discord.Embed(title="AzureSMP Bot | Comandos", description="Consultá la descripción de cada comando para ver sus argumentos.", color=discord.Color.blurple())
        for title, value in [
            ("Información", "/ping /help /botinfo /serverinfo /userinfo /avatar /banner /roleinfo /channelinfo /invite /membercount"),
            ("Moderación", "/clear /kick /ban /unban /timeout /untimeout /warn /warnings /purgeuser /slowmode"),
            ("Comunidad", "/poll /suggest /announce /welcome /goodbye /serverrules /say /embed /remind /setlog"),
            ("Diversión", "/coinflip /dice /8ball /choose /rps /joke /compliment /ship /meme /fact"),
            ("Administración", "/online /offline /setstatus /setnick /roleadd /roleremove /lock /unlock /sync")
        ]:
            embed.add_field(name=title, value=value, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if name == "botinfo":
        await interaction.response.send_message(f"**{bot.user}** · {len(bot.guilds)} servidores · {round(bot.latency * 1000)} ms")
        return
    if name in ("serverinfo", "membercount") and g:
        await interaction.response.send_message(f"**{g.name}** · Miembros: {g.member_count} · Canales: {len(g.channels)} · Roles: {len(g.roles)}")
        return
    if name in ("userinfo", "avatar", "banner") and g:
        target = get_member(g, arg) if arg else interaction.user
        if not target:
            await error("No encontré ese miembro.")
            return
        if name == "userinfo":
            await interaction.response.send_message(f"Usuario: **{target}** · ID: `{target.id}`")
            return
        if name == "avatar":
            embed = discord.Embed(title=f"Avatar de {target}")
            embed.set_image(url=target.display_avatar.url)
            await interaction.response.send_message(embed=embed)
            return
        user = await bot.fetch_user(target.id)
        if not user.banner:
            await error("Ese usuario no tiene un banner visible.")
            return
        embed = discord.Embed(title=f"Banner de {user}")
        embed.set_image(url=user.banner.url)
        await interaction.response.send_message(embed=embed)
        return
    if name == "channelinfo":
        await interaction.response.send_message(f"Canal: **{getattr(interaction.channel, 'name', 'DM')}** · ID: {interaction.channel_id}")
        return
    if name == "roleinfo" and g:
        role = g.get_role(int(arg)) if arg.isdigit() else None
        if not role:
            await error("Indicá un ID de rol válido.")
            return
        await interaction.response.send_message(f"**{role.name}** · ID: {role.id} · Miembros: {len(role.members)}")
        return
    if name == "invite" and g:
        channel = next((c for c in g.text_channels if c.permissions_for(g.me).create_instant_invite), None)
        if channel is None:
            await error("No tengo permiso para crear invitaciones.")
            return
        invite = await channel.create_invite(max_age=3600, max_uses=1)
        await interaction.response.send_message(invite.url, ephemeral=True)
        return

    if name in ("coinflip", "dice", "8ball", "choose", "rps", "joke", "compliment", "meme", "fact", "ship"):
        if name == "coinflip":
            response = "🪙 Salió **" + random.choice(["Cara", "Cruz"]) + "**."
        elif name == "dice":
            try:
                faces = max(2, min(100, int(arg or "6")))
                response = f"🎲 Salió **{random.randint(1, faces)}** de {faces}."
            except ValueError:
                response = "Indicá un número de caras entre 2 y 100."
        elif name == "8ball":
            response = random.choice(["Sí, seguro.", "No lo creo.", "Puede ser.", "Preguntá más tarde.", "Definitivamente.", "Las señales dicen que no."])
        elif name == "choose":
            options = [x.strip() for x in arg.split(",") if x.strip()]
            response = "Elijo: **" + random.choice(options) + "**" if options else "Indicá opciones separadas por comas."
        elif name == "rps":
            if arg.lower() not in ("piedra", "papel", "tijera"):
                response = "Elegí piedra, papel o tijera."
            else:
                bot_pick = random.choice(["piedra", "papel", "tijera"])
                player_wins = (arg.lower(), bot_pick) in {("piedra", "tijera"), ("papel", "piedra"), ("tijera", "papel")}
                response = f"Vos: **{arg.lower()}** · Bot: **{bot_pick}** · " + ("Empate." if arg.lower() == bot_pick else "Ganaste." if player_wins else "Perdiste.")
        elif name == "joke":
            response = random.choice(["¿Qué hace una abeja en el gimnasio? ¡Zum-ba!", "¿Qué le dice un techo a otro? Techo de menos.", "¿Por qué estaba triste el libro de matemáticas? Tenía muchos problemas."])
        elif name == "compliment":
            response = f"✨ {interaction.user.mention}, ¡tu buena onda mejora el servidor!"
        elif name == "meme":
            response = "Yo: hoy me duermo temprano. También yo a las 3 AM: un video más."
        elif name == "fact":
            response = random.choice(["Los pulpos tienen tres corazones.", "Un día en Venus dura más que su año.", "Los tiburones existen desde antes que los árboles."])
        else:
            response = "Comando divertido: indicá dos menciones o IDs para comparar."
        await interaction.response.send_message(response)
        return

    if name in ("poll", "suggest", "serverrules", "announce", "say", "embed"):
        if name in ("serverrules", "announce", "say", "embed") and not manage_guild:
            await error()
            return
        if name == "poll":
            await interaction.response.send_message("📊 **Encuesta:** " + (arg or "¿Qué opinás?"))
            message = await interaction.original_response()
            for emoji in ("👍", "👎"):
                try:
                    await message.add_reaction(emoji)
                except discord.HTTPException:
                    pass
            return
        if name == "suggest":
            embed = discord.Embed(title="💡 Nueva sugerencia", description=arg or "Sin texto", color=discord.Color.green())
            embed.set_footer(text=f"Sugerido por {interaction.user}")
            await interaction.response.send_message(embed=embed)
            return
        if name == "serverrules":
            embed = discord.Embed(title="📜 Reglas del servidor", description=arg or "Agregá las reglas como argumento.")
        elif name in ("announce", "embed"):
            parts = arg.split("|", 1)
            embed = discord.Embed(title=parts[0].strip() or "AzureSMP", description=parts[1].strip() if len(parts) > 1 else "")
        else:
            if not arg:
                await error("Escribí el mensaje.")
                return
            await interaction.channel.send(arg, allowed_mentions=discord.AllowedMentions.none())
            await interaction.response.send_message("Mensaje enviado.", ephemeral=True)
            return
        await interaction.channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.send_message("Publicado.", ephemeral=True)
        return

    if name in ("welcome", "goodbye", "setlog"):
        if not manage_guild:
            await error()
            return
        channel_id = arg.replace("<#", "").replace(">", "")
        if not channel_id.isdigit():
            await error("Indicá el ID o mención del canal.")
            return
        data = read_data()
        key = {"welcome": "welcome_channel", "goodbye": "goodbye_channel", "setlog": "log_channel"}[name]
        data.setdefault(key, {})[str(g.id)] = int(channel_id)
        write_data(data)
        await interaction.response.send_message(f"Canal configurado: <#{channel_id}>.", ephemeral=True)
        return

    if name == "remind":
        parts = arg.split("|", 1)
        if len(parts) != 2 or not parts[0].strip().isdigit() or not 1 <= int(parts[0]) <= 60:
            await error("Formato: minutos | texto (1 a 60 minutos).")
            return
        minutes = int(parts[0])
        await interaction.response.send_message(f"Te recordaré en {minutes} minuto(s).", ephemeral=True)
        await asyncio.sleep(minutes * 60)
        try:
            await interaction.user.send("⏰ Recordatorio: " + parts[1].strip())
        except discord.HTTPException:
            pass
        return

    if name in ("clear", "purgeuser", "slowmode", "kick", "ban", "unban", "timeout", "untimeout", "warn", "warnings"):
        if name in ("clear", "purgeuser", "slowmode") and not manage_messages:
            await error()
            return
        if name not in ("clear", "purgeuser", "slowmode") and not (member and member.guild_permissions.moderate_members):
            await error("Necesitás permiso de moderación.")
            return
        if name == "clear":
            try:
                amount = max(1, min(100, int(arg)))
            except ValueError:
                await error("Indicá una cantidad de 1 a 100.")
                return
            await interaction.response.defer(ephemeral=True)
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(f"Se borraron {len(deleted)} mensajes.", ephemeral=True)
            return
        if name == "slowmode":
            try:
                seconds = max(0, min(21600, int(arg)))
            except ValueError:
                await error("Indicá segundos entre 0 y 21600.")
                return
            await interaction.channel.edit(slowmode_delay=seconds)
            await interaction.response.send_message(f"Modo lento: {seconds} segundos.")
            return
        parts = arg.split("|", 1)
        first = parts[0].strip() if parts else ""
        reason = parts[1].strip() if len(parts) > 1 else "Sin motivo indicado"
        if name == "unban":
            try:
                await g.unban(discord.Object(id=int(first)), reason=reason)
            except (ValueError, discord.HTTPException):
                await error("No se pudo desbanear. Revisá el ID y los permisos.")
                return
            await interaction.response.send_message("Usuario desbaneado.")
            return
        target = get_member(g, first)
        if not target:
            await error("Indicá una mención o ID de miembro válido.")
            return
        if target.top_role >= member.top_role and not (OWNER_ID and interaction.user.id == OWNER_ID):
            await error("No podés moderar a alguien con un rol igual o superior al tuyo.")
            return
        try:
            if name == "kick":
                await target.kick(reason=reason)
            elif name == "ban":
                await target.ban(reason=reason)
            elif name == "timeout":
                minutes = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 0
                if not 1 <= minutes <= 40320:
                    await error("Formato: mención | minutos (1 a 40320).")
                    return
                await target.timeout(timedelta(minutes=minutes), reason=reason)
            elif name == "untimeout":
                await target.timeout(None, reason=reason)
            elif name == "warn":
                data = read_data()
                data.setdefault("warnings", {}).setdefault(f"{g.id}:{target.id}", []).append({"moderator": interaction.user.id, "reason": reason})
                write_data(data)
            elif name == "warnings":
                entries = read_data().get("warnings", {}).get(f"{g.id}:{target.id}", [])
                await interaction.response.send_message("\n".join(f"{n+1}. {item['reason']}" for n, item in enumerate(entries[-10:])) or "No hay advertencias.", ephemeral=True)
                return
            elif name == "purgeuser":
                await interaction.response.defer(ephemeral=True)
                deleted = await interaction.channel.purge(limit=100, check=lambda message: message.author.id == target.id)
                await interaction.followup.send(f"Se borraron {len(deleted)} mensajes de {target.mention}.", ephemeral=True)
                return
        except (discord.Forbidden, discord.HTTPException, ValueError):
            await error("No se pudo completar la acción. Revisá permisos y jerarquía.")
            return
        await interaction.response.send_message(f"Acción **{name}** aplicada a **{target}**.")
        return

    if name in ("online", "offline", "setstatus"):
        if not admin:
            await error()
            return
        if name == "offline":
            await bot.change_presence(status=discord.Status.invisible)
        elif name == "online":
            await bot.change_presence(status=discord.Status.online, activity=discord.Game("AzureSMP"))
        else:
            await bot.change_presence(status=discord.Status.online, activity=discord.Game(arg[:128] or "AzureSMP"))
        await interaction.response.send_message("Presencia actualizada.", ephemeral=True)
        return
    if name == "setnick":
        if not manage_guild:
            await error()
            return
        parts = arg.split("|", 1)
        target = get_member(g, parts[0]) if parts else None
        if not target or len(parts) < 2:
            await error("Formato: mención | apodo")
            return
        try:
            await target.edit(nick=parts[1].strip()[:32], reason=f"Por {interaction.user}")
        except discord.HTTPException:
            await error("No pude cambiar el apodo; revisá la jerarquía.")
            return
        await interaction.response.send_message("Apodo actualizado.")
        return
    if name in ("roleadd", "roleremove"):
        if not manage_roles:
            await error()
            return
        parts = arg.split()
        if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
            await error("Formato: ID_MIEMBRO ID_ROL")
            return
        target, role = g.get_member(int(parts[0])), g.get_role(int(parts[1]))
        if not target or not role or role >= g.me.top_role:
            await error("Miembro o rol inválido, o jerarquía insuficiente.")
            return
        try:
            if name == "roleadd":
                await target.add_roles(role)
            else:
                await target.remove_roles(role)
        except discord.HTTPException:
            await error("No pude modificar el rol.")
            return
        await interaction.response.send_message("Rol actualizado.")
        return
    if name in ("lock", "unlock"):
        if not manage_channels:
            await error()
            return
        await interaction.channel.set_permissions(g.default_role, send_messages=False if name == "lock" else None)
        await interaction.response.send_message("🔒 Canal bloqueado." if name == "lock" else "🔓 Canal desbloqueado.")
        return
    if name == "sync":
        if not (admin or (OWNER_ID and interaction.user.id == OWNER_ID)):
            await error()
            return
        await interaction.response.defer(ephemeral=True)
        synced = await bot.tree.sync()
        await interaction.followup.send(f"Sincronizados {len(synced)} comandos.", ephemeral=True)
        return

    await error("Este comando no tiene una acción implementada.")

async def setup(bot: commands.Bot):
    for command_name, description in COMMANDS:
        def make_callback(fixed_name):
            async def callback(interaction: discord.Interaction, argumento: str = ""):
                try:
                    await execute(bot, interaction, fixed_name, argumento)
                except Exception as error:
                    logger.exception("Error ejecutando /%s", fixed_name)
                    message = (
                        "No pude completar ese comando. Revisá los permisos del bot y del canal; "
                        "el error quedó registrado en la consola."
                    )
                    try:
                        if interaction.response.is_done():
                            await interaction.followup.send(message, ephemeral=True)
                        else:
                            await interaction.response.send_message(message, ephemeral=True)
                    except discord.HTTPException:
                        logger.exception("No se pudo responder a la interacción /%s", fixed_name)
            callback.__name__ = "command_" + fixed_name.replace("-", "_")
            return callback
        bot.tree.add_command(app_commands.Command(name=command_name, description=description, callback=make_callback(command_name)))
