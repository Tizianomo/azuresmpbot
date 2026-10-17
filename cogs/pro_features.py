from __future__ import annotations

import json
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

DATA_FILE = Path(os.getenv("AZURE_DATA_FILE", "azure_data.json"))
OWNER_ID = int(os.getenv("OWNER_ID", "0"))


def read_data() -> dict:
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_admin(interaction: discord.Interaction) -> bool:
    user = interaction.user
    return isinstance(user, discord.Member) and (
        user.guild_permissions.administrator
        or (OWNER_ID != 0 and user.id == OWNER_ID)
    )


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Cerrar ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="azure_ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not channel.name.startswith("ticket-"):
            await interaction.response.send_message("Este botón solo funciona dentro de un ticket.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("No se pudo verificar tu usuario.", ephemeral=True)
            return
        topic = channel.topic or ""
        is_owner = f"owner:{interaction.user.id}" in topic
        staff_role_id = read_data().get("ticket_staff_role", {}).get(str(channel.guild.id))
        is_staff = interaction.user.guild_permissions.manage_channels or bool(
            staff_role_id and any(role.id == int(staff_role_id) for role in interaction.user.roles)
        )
        if not (is_owner or is_staff):
            await interaction.response.send_message("Solo quien abrió el ticket o el staff puede cerrarlo.", ephemeral=True)
            return
        await interaction.response.send_message("Ticket cerrado. El canal se eliminará en unos segundos.", ephemeral=True)
        await channel.delete(reason=f"Ticket cerrado por {interaction.user}")


class StaffApplicationModal(discord.ui.Modal, title="Postulación para Staff"):
    age = discord.ui.TextInput(label="Edad", placeholder="Tu edad", max_length=3)
    timezone = discord.ui.TextInput(label="País / zona horaria", placeholder="Ej.: Argentina (UTC-3)", max_length=80)
    experience = discord.ui.TextInput(label="Experiencia", placeholder="¿Fuiste staff antes?", style=discord.TextStyle.paragraph, max_length=800)
    reason = discord.ui.TextInput(label="¿Por qué querés entrar al staff?", style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Usá este formulario dentro del servidor.", ephemeral=True)
            return
        data = read_data()
        channel_id = data.get("staff_application_channel", {}).get(str(interaction.guild.id))
        channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Las postulaciones todavía no están configuradas. Un administrador debe usar /setapplications.",
                ephemeral=True,
            )
            return
        embed = discord.Embed(title="📋 Nueva postulación para Staff", color=discord.Color.blurple())
        embed.add_field(name="Usuario", value=f"{interaction.user.mention} (ID: {interaction.user.id})", inline=False)
        embed.add_field(name="Edad", value=str(self.age), inline=True)
        embed.add_field(name="País / zona horaria", value=str(self.timezone), inline=True)
        embed.add_field(name="Experiencia", value=str(self.experience), inline=False)
        embed.add_field(name="Motivo", value=str(self.reason), inline=False)
        embed.set_footer(text="AzureSMP • Postulación")
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.send_message("¡Tu postulación fue enviada al equipo de Staff!", ephemeral=True)


class TicketOpenSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Seleccioná una opción...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="Abrir ticket",
                    description="Crear un canal privado con el equipo de soporte",
                    emoji="🎫",
                    value="open_ticket",
                )
            ],
            custom_id="azure_ticket_select",
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Usá este menú dentro del servidor.", ephemeral=True
            )
            return

        existing = next(
            (
                channel for channel in guild.text_channels
                if (channel.topic or "").startswith(f"owner:{interaction.user.id}")
            ),
            None,
        )
        if existing:
            await interaction.response.send_message(
                f"Ya tenés un ticket abierto: {existing.mention}", ephemeral=True
            )
            return

        data = read_data()
        category_id = data.get("ticket_category", {}).get(str(guild.id))
        category = guild.get_channel(int(category_id)) if category_id else None
        staff_id = data.get("ticket_staff_role", {}).get(str(guild.id))
        staff_role = guild.get_role(int(staff_id)) if staff_id else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
        }
        bot_member = guild.me
        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True,
                read_message_history=True
            )
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )

        safe_name = "".join(
            c.lower() if c.isalnum() else "-"
            for c in interaction.user.name
        )[:20].strip("-") or "usuario"

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{safe_name}",
                category=(
                    category if isinstance(category, discord.CategoryChannel) else None
                ),
                overwrites=overwrites,
                topic=f"owner:{interaction.user.id} | Ticket de {interaction.user}",
                reason=f"Ticket abierto por {interaction.user}",
            )
            embed = discord.Embed(
                title="🎫 Soporte AzureSMP",
                description=(
                    f"Hola {interaction.user.mention}.\n\n"
                    "Explicá tu consulta y el equipo de staff te ayudará lo antes posible.\n\n"
                    "🔒 No compartas contraseñas ni tokens."
                ),
                color=discord.Color.from_rgb(0, 179, 255),
            )
            embed.set_footer(text="AzureSMP • Centro de soporte")
            await channel.send(
                content=interaction.user.mention,
                embed=embed,
                view=TicketCloseView(),
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            await interaction.followup.send(
                f"Tu ticket está listo: {channel.mention}", ephemeral=True
            )
        except discord.HTTPException:
            await interaction.followup.send(
                "No pude crear el ticket. Revisá que el bot tenga permisos para "
                "administrar canales, ver canales y enviar mensajes.",
                ephemeral=True,
            )


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketOpenSelect())

class AzureFeatures(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ticketpanel", description="Publica el panel para abrir tickets de soporte")
    async def ticketpanel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="🎫 Centro de soporte • AzureSMP",
            description="¿Necesitás ayuda? Seleccioná **Abrir ticket** en el menú de abajo para crear un canal privado con el equipo de staff.",
            color=discord.Color.blurple(),
        )
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("Usá este comando dentro de un canal de texto.", ephemeral=True)
            return
        await interaction.channel.send(embed=embed, view=TicketPanelView())
        await interaction.followup.send("Panel de tickets publicado.", ephemeral=True)

    @app_commands.command(name="applystaff", description="Abre el formulario para postularte al Staff")
    async def applystaff(self, interaction: discord.Interaction):
        await interaction.response.send_modal(StaffApplicationModal())

    @app_commands.command(name="setapplications", description="Configura el canal donde llegan las postulaciones")
    @app_commands.describe(canal="Canal privado para que el Staff revise las postulaciones")
    @app_commands.check(is_admin)
    async def setapplications(self, interaction: discord.Interaction, canal: discord.TextChannel):
        data = read_data()
        data.setdefault("staff_application_channel", {})[str(interaction.guild_id)] = canal.id
        write_data(data)
        await interaction.response.send_message(f"Canal de postulaciones configurado: {canal.mention}", ephemeral=True)

    @app_commands.command(name="setticketstaff", description="Configura el rol que podrá ver los tickets")
    @app_commands.describe(rol="Rol de soporte")
    async def setticketstaff(self, interaction: discord.Interaction, rol: discord.Role):
        data = read_data()
        data.setdefault("ticket_staff_role", {})[str(interaction.guild_id)] = rol.id
        write_data(data)
        await interaction.response.send_message(f"Rol de soporte configurado: {rol.mention}", ephemeral=True)

    @app_commands.command(name="setticketcategory", description="Configura la categoría donde se crearán tickets")
    @app_commands.describe(categoria="Categoría de Discord para los tickets")
    async def setticketcategory(self, interaction: discord.Interaction, categoria: discord.CategoryChannel):
        data = read_data()
        data.setdefault("ticket_category", {})[str(interaction.guild_id)] = categoria.id
        write_data(data)
        await interaction.response.send_message(f"Categoría de tickets configurada: **{categoria.name}**", ephemeral=True)

    @app_commands.command(name="setstats", description="Publica estadísticas del servidor y las actualiza")
    @app_commands.describe(canal="Canal donde se mostrará el contador de miembros")
    @app_commands.check(is_admin)
    async def setstats(self, interaction: discord.Interaction, canal: discord.TextChannel):
        data = read_data()
        data.setdefault("stats_channel", {})[str(interaction.guild_id)] = canal.id
        write_data(data)
        await self.update_stats(interaction.guild)
        await interaction.response.send_message(f"Estadísticas configuradas en {canal.mention}.", ephemeral=True)

    async def update_stats(self, guild: discord.Guild | None):
        if guild is None:
            return
        data = read_data()
        channel_id = data.get("stats_channel", {}).get(str(guild.id))
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.edit(topic=f"👥 Miembros: {guild.member_count or len(guild.members)} | 🤖 Bots: {sum(m.bot for m in guild.members)}")
            except discord.HTTPException:
                pass

    @app_commands.command(name="stats", description="Muestra estadísticas actuales del servidor")
    async def stats(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.", ephemeral=True)
            return
        embed = discord.Embed(title=f"Estadísticas • {guild.name}", color=discord.Color.blurple())
        embed.add_field(name="Miembros", value=str(guild.member_count or len(guild.members)), inline=True)
        embed.add_field(name="Bots", value=str(sum(m.bot for m in guild.members)), inline=True)
        embed.add_field(name="Canales", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Creado", value=discord.utils.format_dt(guild.created_at, style="D"), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setminecraft", description="Configura la dirección de tu servidor Minecraft")
    @app_commands.describe(direccion="IP o dominio y puerto opcional, por ejemplo play.ejemplo.net:25565")
    @app_commands.check(is_admin)
    async def setminecraft(self, interaction: discord.Interaction, direccion: str):
        address = direccion.strip()
        if not address or len(address) > 255 or any(c.isspace() for c in address):
            await interaction.response.send_message("Indicá una IP o dominio válido.", ephemeral=True)
            return
        data = read_data()
        data.setdefault("minecraft_server", {})[str(interaction.guild_id)] = address
        write_data(data)
        await interaction.response.send_message(f"Servidor Minecraft configurado como `{address}`. Probá /minecraft.", ephemeral=True)

    @app_commands.command(name="minecraft", description="Consulta el estado de conexión del servidor Minecraft")
    async def minecraft(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.", ephemeral=True)
            return
        address = read_data().get("minecraft_server", {}).get(str(guild.id))
        if not address:
            await interaction.response.send_message("Un administrador debe configurar la IP con /setminecraft primero.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            from mcstatus import JavaServer
            server = await JavaServer.async_lookup(address)
            status = await server.async_status()
            embed = discord.Embed(title="🟢 Servidor Minecraft en línea", description=f"`{address}`", color=discord.Color.green())
            embed.add_field(name="Jugadores", value=f"{status.players.online}/{status.players.max}", inline=True)
            embed.add_field(name="Latencia", value=f"{round(status.latency)} ms", inline=True)
            names = [player.name for player in (status.players.sample or []) if player.name]
            if names:
                embed.add_field(name="Conectados", value=", ".join(names[:20]), inline=False)
            await interaction.followup.send(embed=embed)
        except Exception:
            await interaction.followup.send(
                f"No pude consultar `{address}`. Verificá la IP/puerto y que el servidor permita consultas de estado. Si usás un proxy o hosting, comprobá que el dominio apunte al servidor correcto.",
                ephemeral=True,
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        guild_key = str(guild.id)
        data = read_data()

        # Número persistente de llegada: conserva el orden aunque el bot se reinicie.
        current_count = guild.member_count or len(guild.members)
        previous_number = int(data.get("join_numbers", {}).get(guild_key, 0))
        join_number = max(previous_number + 1, current_count)
        data.setdefault("join_numbers", {})[guild_key] = join_number
        write_data(data)

        welcome_id = data.get("welcome_channel", {}).get(guild_key)
        welcome = guild.get_channel(int(welcome_id)) if welcome_id else None
        # Si no se configuró un canal por ID, buscar automáticamente #bienvenidas.
        if not isinstance(welcome, discord.TextChannel):
            welcome = next(
                (
                    channel for channel in guild.text_channels
                    if any(word in channel.name.casefold() for word in ("bienvenidas", "bienvenida", "welcome"))
                ),
                None,
            )
        if isinstance(welcome, discord.TextChannel):
            rules_channel = next(
                (
                    channel for channel in guild.text_channels
                    if any(word in channel.name.casefold() for word in ("normas", "reglas", "rules"))
                ),
                None,
            )
            rules_text = (
                f"📜 Antes de participar, leé la normativa en {rules_channel.mention} y respetá a toda la comunidad."
                if rules_channel
                else "📜 Antes de participar, recordá leer y respetar la normativa del servidor."
            )
            embed = discord.Embed(
                title=f"¡Te damos la bienvenida a {guild.name}!",
                description=(
                    f"¡Hola, {member.mention}! 👋\n\n"
                    f"Nos alegra que hayas llegado a **{guild.name}**. Queremos que te sientas parte de la comunidad, "
                    "conozcas a los demás y disfrutes del servidor. Si necesitás ayuda, podés consultar al equipo de staff.\n\n"
                    f"⭐ **¡Sos nuestro miembro número #{join_number}!**\n\n"
                    f"{rules_text}\n\n"
                    "Tomate un momento para conocer los canales, revisar la información importante y mantener un ambiente "
                    "respetuoso. ¡Esperamos que tengas una gran experiencia con nosotros!"
                ),
                color=discord.Color.from_rgb(0, 179, 255),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="👤 Perfil", value=f"**Nombre:** {member.mention}\n**Usuario:** {discord.utils.escape_markdown(member.name)}", inline=True)
            embed.add_field(name="🗓️ Cuenta creada", value=discord.utils.format_dt(member.created_at, style="D"), inline=True)
            embed.add_field(name="🚪 Ingreso al servidor", value=discord.utils.format_dt(member.joined_at or discord.utils.utcnow(), style="F"), inline=False)
            embed.add_field(name="🆔 Identificador", value=str(member.id), inline=True)
            embed.set_footer(text=f"{guild.name} • ¡Gracias por unirte!", icon_url=guild.icon.url if guild.icon else None)
            try:
                await welcome.send(
                    content=f"¡Bienvenido/a, {member.mention}!",
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
            except discord.HTTPException:
                pass
        await self.update_stats(guild)
        await self.log_event(guild, f"📥 {member} se unió al servidor. Miembro de llegada #{join_number}.")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        data = read_data()
        goodbye_id = data.get("goodbye_channel", {}).get(str(member.guild.id))
        goodbye = member.guild.get_channel(int(goodbye_id)) if goodbye_id else None
        if isinstance(goodbye, discord.TextChannel):
            try:
                await goodbye.send(f"👋 **{member}** salió del servidor. Ahora somos {member.guild.member_count} miembros.")
            except discord.HTTPException:
                pass
        await self.update_stats(member.guild)
        await self.log_event(member.guild, f"📤 {member} salió del servidor.")

    async def log_event(self, guild: discord.Guild, message: str):
        data = read_data()
        channel_id = data.get("log_channel", {}).get(str(guild.id))
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(message)
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.update_stats(guild)


async def setup(bot: commands.Bot):
    bot.add_view(TicketPanelView())
    bot.add_view(TicketCloseView())
    await bot.add_cog(AzureFeatures(bot))
