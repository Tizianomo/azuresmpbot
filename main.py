import asyncio
import secrets
import logging
import os

import discord
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
from discord.ext import commands


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("discord_ping_bot")
message_content_access = True


def require_bridge_token(
    token: str | None = Header(default=None, alias="X-Discord-Bridge-Token"),
) -> None:
    expected = os.getenv("DISCORD_BOT_TOKEN")
    if not expected or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="No autorizado.")


class PingBot(commands.Bot):
    async def setup_hook(self) -> None:
        # Carga los comandos adicionales sin eliminar los que ya estén registrados.
        try:
            await self.load_extension("cogs.commands")
            logger.info("Módulo cogs.commands cargado.")
            await self.load_extension("cogs.pro_features")
            logger.info("Módulo cogs.pro_features cargado.")
        except Exception:
            logger.exception("No se pudo cargar cogs.commands; se conservará el resto del bot.")
            raise

        synced_commands = await self.tree.sync()
        logger.info("Sincronizados %s comandos de aplicación.", len(synced_commands))

    async def on_ready(self) -> None:
        global message_content_access
        message_content_access = self.intents.message_content
        logger.info(
            "Bot conectado como %s en %s servidores.",
            self.user,
            len(self.guilds),
        )


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = PingBot(
    command_prefix=commands.when_mentioned,
    intents=intents,
)
api = FastAPI(
    title="Discord bot internal bridge",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    dependencies=[Depends(require_bridge_token)],
)


class OutgoingMessage(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


def require_connected_bot() -> None:
    if not bot.is_ready() or bot.user is None:
        raise HTTPException(status_code=503, detail="El bot no está conectado a Discord.")


def to_message_data(message: discord.Message) -> dict[str, object]:
    return {
        "id": str(message.id),
        "channelId": str(message.channel.id),
        "authorId": str(message.author.id),
        "authorName": message.author.display_name,
        "authorAvatarUrl": str(message.author.display_avatar.url),
        "content": message.content,
        "timestamp": message.created_at.isoformat(),
        "isBot": message.author.bot,
    }


def visible_text_channels(guild: discord.Guild) -> list[discord.TextChannel]:
    member = guild.me
    if member is None:
        return []
    return [
        channel
        for channel in guild.text_channels
        if channel.permissions_for(member).view_channel
    ]


def get_text_channel(channel_id: str) -> discord.TextChannel:
    try:
        numeric_id = int(channel_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="ID de canal inválido.") from error

    channel = bot.get_channel(numeric_id)
    if not isinstance(channel, discord.TextChannel):
        raise HTTPException(status_code=404, detail="No se encontró el canal de texto.")

    member = channel.guild.me
    if member is None:
        raise HTTPException(status_code=503, detail="El bot no está listo en este servidor.")

    permissions = channel.permissions_for(member)
    if not permissions.view_channel:
        raise HTTPException(status_code=403, detail="El bot no puede ver este canal.")
    return channel


@bot.tree.command(name="ping", description="Comprueba si el bot está conectado.")
async def ping(interaction: discord.Interaction) -> None:
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! Latencia: {latency_ms} ms.")


@api.get("/internal/status")
async def get_status() -> dict[str, object]:
    user = bot.user
    return {
        "connected": bot.is_ready() and user is not None,
        "username": user.name if user else None,
        "avatarUrl": str(user.display_avatar.url) if user else None,
        "guildCount": len(bot.guilds) if bot.is_ready() else 0,
        "messageContentEnabled": message_content_access,
    }


@api.get("/internal/guilds")
async def get_guilds() -> list[dict[str, object]]:
    require_connected_bot()
    return [
        {
            "id": str(guild.id),
            "name": guild.name,
            "iconUrl": str(guild.icon.url) if guild.icon else None,
            "channelCount": len(visible_text_channels(guild)),
        }
        for guild in sorted(bot.guilds, key=lambda item: item.name.casefold())
    ]


@api.get("/internal/guilds/{guild_id}/channels")
async def get_channels(guild_id: str) -> list[dict[str, object]]:
    require_connected_bot()
    try:
        numeric_id = int(guild_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="ID de servidor inválido.") from error

    guild = bot.get_guild(numeric_id)
    if guild is None:
        raise HTTPException(status_code=404, detail="No se encontró el servidor.")

    member = guild.me
    if member is None:
        raise HTTPException(status_code=503, detail="El bot no está listo en este servidor.")

    channels = visible_text_channels(guild)
    return [
        {
            "id": str(channel.id),
            "name": channel.name,
            "type": channel.type.name,
            "categoryName": channel.category.name if channel.category else None,
            "canRead": channel.permissions_for(member).read_message_history,
            "canSend": channel.permissions_for(member).send_messages,
        }
        for channel in sorted(channels, key=lambda item: item.position)
    ]


@api.get("/internal/channels/{channel_id}/messages")
async def get_messages(
    channel_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    before: str | None = None,
) -> dict[str, object]:
    require_connected_bot()
    if not message_content_access:
        raise HTTPException(
            status_code=403,
            detail="Habilitá Message Content Intent en Discord Developer Portal y reiniciá el bot.",
        )

    channel = get_text_channel(channel_id)
    member = channel.guild.me
    if member is None or not channel.permissions_for(member).read_message_history:
        raise HTTPException(
            status_code=403,
            detail="El bot necesita permiso para leer el historial de este canal.",
        )

    before_message = None
    if before is not None:
        if not before.isdigit():
            raise HTTPException(status_code=400, detail="Cursor de mensajes inválido.")
        before_message = discord.Object(id=int(before))

    try:
        fetched: list[discord.Message] = [
            message
            async for message in channel.history(
                limit=limit,
                before=before_message,
            )
        ]
    except discord.Forbidden as error:
        raise HTTPException(status_code=403, detail="Discord rechazó el acceso al canal.") from error
    except discord.NotFound as error:
        raise HTTPException(status_code=404, detail="No se encontró el canal.") from error
    except discord.HTTPException as error:
        raise HTTPException(status_code=502, detail="No se pudieron cargar los mensajes.") from error

    has_more = len(fetched) == limit
    next_cursor = str(fetched[-1].id) if has_more and fetched else None
    fetched.reverse()
    return {
        "messages": [to_message_data(message) for message in fetched],
        "hasMore": has_more,
        "nextCursor": next_cursor,
    }


@api.post("/internal/channels/{channel_id}/messages", status_code=201)
async def send_message(channel_id: str, payload: OutgoingMessage) -> dict[str, object]:
    require_connected_bot()
    channel = get_text_channel(channel_id)
    member = channel.guild.me
    if member is None or not channel.permissions_for(member).send_messages:
        raise HTTPException(
            status_code=403,
            detail="El bot necesita permiso para enviar mensajes en este canal.",
        )
    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="Escribí un mensaje antes de enviarlo.")

    try:
        message = await channel.send(
            payload.content,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.Forbidden as error:
        raise HTTPException(status_code=403, detail="Discord rechazó el envío del mensaje.") from error
    except discord.NotFound as error:
        raise HTTPException(status_code=404, detail="No se encontró el canal.") from error
    except discord.HTTPException as error:
        raise HTTPException(status_code=502, detail="No se pudo enviar el mensaje.") from error

    return to_message_data(message)


async def start_bot(token: str) -> None:
    global message_content_access
    try:
        await bot.start(token)
    except discord.PrivilegedIntentsRequired:
        message_content_access = False
        logger.error(
            "Discord requiere habilitar Message Content Intent en Developer Portal."
        )
    except discord.LoginFailure:
        logger.error("Discord rechazó el token del bot. Revisá el secreto configurado.")
    except Exception as error:
        logger.error("No se pudo conectar el bot (%s).", type(error).__name__)


async def run_services(token: str) -> None:
    bot_task = asyncio.create_task(start_bot(token), name="discord-gateway")
    server = uvicorn.Server(
        uvicorn.Config(
            api,
            host="0.0.0.0",
            port=int(os.getenv("DISCORD_BOT_BRIDGE_PORT", "8000")),
            log_level="warning",
            access_log=False,
        )
    )
    try:
        await server.serve()
    finally:
        if not bot.is_closed():
            await bot.close()
        await bot_task


async def run_bot() -> None:
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Falta DISCORD_BOT_TOKEN. Guardá el token del bot en los secretos del proyecto."
        )

    await run_services(token)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot detenido.")
