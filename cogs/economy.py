from __future__ import annotations

import random
import time
import json
import os
from pathlib import Path

import discord
from discord.ext import commands

DATA_FILE = Path(os.getenv("AZURE_DATA_FILE", "azure_data.json"))
ROB_COOLDOWN = 60 * 60
WORK_COOLDOWN = 60 * 30
FISH_COOLDOWN = 60 * 20
MINE_COOLDOWN = 60 * 20
DAILY_COOLDOWN = 60 * 60 * 24
KEY_PRICE = 500


def read_data() -> dict:
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def user_wallet(data: dict, guild_id: int, user_id: int) -> dict:
    economy = data.setdefault("economy", {}).setdefault(str(guild_id), {})
    return economy.setdefault(str(user_id), {
        "wallet": 0, "bank": 0, "keys": 0, "cooldowns": {}
    })


def money(amount: int) -> str:
    return f"${amount:,}".replace(",", ".")


def remaining(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min"
    return f"{seconds} s"


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_profile(self, ctx: commands.Context) -> tuple[dict, dict]:
        data = read_data()
        profile = user_wallet(data, ctx.guild.id, ctx.author.id)
        return data, profile

    async def cooldown_check(self, ctx: commands.Context, profile: dict, name: str, duration: int) -> bool:
        now = time.time()
        last = float(profile.setdefault("cooldowns", {}).get(name, 0))
        if now - last < duration:
            await ctx.reply(f"⏳ Esperá **{remaining(duration - (now - last))}** para volver a usar este comando.", mention_author=False)
            return False
        profile["cooldowns"][name] = now
        return True

    @commands.command(name="balance", aliases=["bal", "dinero"])
    @commands.guild_only()
    async def balance(self, ctx: commands.Context, member: discord.Member | None = None):
        target = member or ctx.author
        data = read_data()
        profile = user_wallet(data, ctx.guild.id, target.id)
        write_data(data)
        embed = discord.Embed(title=f"💰 Economía de {target.display_name}", color=discord.Color.from_rgb(0, 179, 255))
        embed.add_field(name="Cartera", value=money(int(profile["wallet"])), inline=True)
        embed.add_field(name="Banco", value=money(int(profile["bank"])), inline=True)
        embed.add_field(name="Llaves", value=str(int(profile["keys"])), inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="bank", aliases=["banco"])
    @commands.guild_only()
    async def bank(self, ctx: commands.Context):
        data, profile = await self.get_profile(ctx)
        write_data(data)
        await ctx.reply(f"🏦 Tenés **{money(int(profile['bank']))}** guardados en el banco. Lo que está en el banco no puede ser robado.", mention_author=False)

    @commands.command(name="deposit", aliases=["depositar"])
    @commands.guild_only()
    async def deposit(self, ctx: commands.Context, amount: str):
        data, profile = await self.get_profile(ctx)
        value = int(profile["wallet"]) if amount.lower() == "all" else (int(amount) if amount.isdigit() else 0)
        if value <= 0 or value > int(profile["wallet"]):
            await ctx.reply("Indicá una cantidad válida. Ejemplo: `.deposit 500` o `.deposit all`.", mention_author=False)
            return
        profile["wallet"] -= value
        profile["bank"] += value
        write_data(data)
        await ctx.reply(f"🏦 Depositaste **{money(value)}**. Cartera: {money(profile['wallet'])} · Banco: {money(profile['bank'])}.", mention_author=False)

    @commands.command(name="withdraw", aliases=["retirar"])
    @commands.guild_only()
    async def withdraw(self, ctx: commands.Context, amount: str):
        data, profile = await self.get_profile(ctx)
        value = int(profile["bank"]) if amount.lower() == "all" else (int(amount) if amount.isdigit() else 0)
        if value <= 0 or value > int(profile["bank"]):
            await ctx.reply("Indicá una cantidad válida. Ejemplo: `.withdraw 500` o `.withdraw all`.", mention_author=False)
            return
        profile["bank"] -= value
        profile["wallet"] += value
        write_data(data)
        await ctx.reply(f"💵 Retiraste **{money(value)}**. Cartera: {money(profile['wallet'])} · Banco: {money(profile['bank'])}.", mention_author=False)

    @commands.command(name="daily", aliases=["diario"])
    @commands.guild_only()
    async def daily(self, ctx: commands.Context):
        data, profile = await self.get_profile(ctx)
        if not await self.cooldown_check(ctx, profile, "daily", DAILY_COOLDOWN):
            return
        reward = random.randint(500, 1000)
        profile["wallet"] += reward
        write_data(data)
        await ctx.reply(f"🎁 Cobraste tu recompensa diaria de **{money(reward)}**.", mention_author=False)

    @commands.command(name="jobs", aliases=["trabajos", "job"])
    @commands.guild_only()
    async def jobs(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🧰 Trabajos de AzureSMP",
            description="Usá `.work` cada 30 minutos para trabajar y cobrar.",
            color=discord.Color.from_rgb(0, 179, 255),
        )
        embed.add_field(name="🛠️ Minero", value="Extrae recursos y cobra.", inline=True)
        embed.add_field(name="🎣 Pescador", value="Pesca y vende lo que consigue.", inline=True)
        embed.add_field(name="📦 Repartidor", value="Entrega paquetes y gana dinero.", inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="work", aliases=["trabajar"])
    @commands.guild_only()
    async def work(self, ctx: commands.Context):
        data, profile = await self.get_profile(ctx)
        if not await self.cooldown_check(ctx, profile, "work", WORK_COOLDOWN):
            return
        job, reward = random.choice([
            ("repartidor", random.randint(80, 180)),
            ("ayudante de construcción", random.randint(100, 210)),
            ("minero", random.randint(90, 230)),
            ("camarero", random.randint(80, 190)),
        ])
        profile["wallet"] += reward
        write_data(data)
        await ctx.reply(f"🧰 Trabajaste como **{job}** y ganaste **{money(reward)}**.", mention_author=False)

    @commands.command(name="fish", aliases=["pescar"])
    @commands.guild_only()
    async def fish(self, ctx: commands.Context):
        data, profile = await self.get_profile(ctx)
        if not await self.cooldown_check(ctx, profile, "fish", FISH_COOLDOWN):
            return
        catch, reward = random.choice([
            ("una sardina", 45), ("una trucha", 80), ("un salmón", 120),
            ("un pez dorado", 180), ("una bota vieja", 10), ("un pez legendario", 350),
        ])
        profile["wallet"] += reward
        write_data(data)
        await ctx.reply(f"🎣 Pescaste **{catch}** y ganaste **{money(reward)}**.", mention_author=False)

    @commands.command(name="mine", aliases=["minar"])
    @commands.guild_only()
    async def mine(self, ctx: commands.Context):
        data, profile = await self.get_profile(ctx)
        if not await self.cooldown_check(ctx, profile, "mine", MINE_COOLDOWN):
            return
        find, reward = random.choice([
            ("carbón", 40), ("hierro", 75), ("oro", 130),
            ("diamantes", 220), ("esmeraldas", 280), ("piedra", 15),
        ])
        profile["wallet"] += reward
        write_data(data)
        await ctx.reply(f"⛏️ Encontraste **{find}** y ganaste **{money(reward)}**.", mention_author=False)

    @commands.command(name="rob", aliases=["robar"])
    @commands.guild_only()
    async def rob(self, ctx: commands.Context, target: discord.Member):
        if target.bot or target.id == ctx.author.id:
            await ctx.reply("Tenés que mencionar a otra persona real del servidor.", mention_author=False)
            return
        data, robber = await self.get_profile(ctx)
        victim = user_wallet(data, ctx.guild.id, target.id)
        if int(victim["wallet"]) <= 0:
            await ctx.reply(f"🏦 {target.mention} no tiene dinero en su cartera. Si guardó todo en el banco, no podés robarle nada.", mention_author=False)
            return
        if not await self.cooldown_check(ctx, robber, "rob", ROB_COOLDOWN):
            return
        if random.random() >= 0.17:
            fine = min(int(robber["wallet"]), random.randint(30, 120))
            robber["wallet"] -= fine
            write_data(data)
            await ctx.reply(f"🚨 ¡Te atraparon intentando robar a {target.mention}! Pagaste una multa de **{money(fine)}**.", mention_author=False)
            return
        stolen = min(int(victim["wallet"]), max(1, int(int(victim["wallet"]) * random.uniform(0.10, 0.35))))
        victim["wallet"] -= stolen
        robber["wallet"] += stolen
        write_data(data)
        await ctx.reply(f"🕵️ ¡Robo exitoso! Le robaste **{money(stolen)}** a {target.mention}. Tenés un **17%** de probabilidad de éxito. El dinero del banco está protegido.", mention_author=False, allowed_mentions=discord.AllowedMentions(users=True))

    @commands.command(name="shopitems", aliases=["tienda"])
    @commands.guild_only()
    async def shopitems(self, ctx: commands.Context):
        embed = discord.Embed(title="🛒 Tienda de AzureSMP", description="Comprá una llave y después usá `.opencrate` para abrir una recompensa aleatoria.", color=discord.Color.from_rgb(0, 179, 255))
        embed.add_field(name="🗝️ Llave misteriosa", value=f"Precio: **{money(KEY_PRICE)}**\nComando: `.buy llave [cantidad]`", inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="buy", aliases=["comprar"])
    @commands.guild_only()
    async def buy(self, ctx: commands.Context, item: str, quantity: int = 1):
        if item.lower() not in ("llave", "llaves", "key", "keys") or not 1 <= quantity <= 20:
            await ctx.reply("Uso: `.buy llave [cantidad]` (máximo 20 por compra).", mention_author=False)
            return
        data, profile = await self.get_profile(ctx)
        cost = KEY_PRICE * quantity
        if int(profile["wallet"]) < cost:
            await ctx.reply(f"Te faltan **{money(cost - int(profile['wallet']))}** para comprar {quantity} llave(s).", mention_author=False)
            return
        profile["wallet"] -= cost
        profile["keys"] += quantity
        write_data(data)
        await ctx.reply(f"🗝️ Compraste **{quantity}** llave(s) por **{money(cost)}**. Llaves disponibles: **{profile['keys']}**.", mention_author=False)

    @commands.command(name="opencrate", aliases=["usekey", "abrirllave"])
    @commands.guild_only()
    async def opencrate(self, ctx: commands.Context):
        data, profile = await self.get_profile(ctx)
        if int(profile["keys"]) < 1:
            await ctx.reply("No tenés llaves. Mirá `.shopitems` y comprá una con `.buy llave`.", mention_author=False)
            return
        profile["keys"] -= 1
        reward = random.choices(
            [250, 500, 800, 1500, 3000, 10000],
            weights=[35, 28, 20, 10, 5, 2],
            k=1,
        )[0]
        profile["wallet"] += reward
        write_data(data)
        await ctx.reply(f"🎁 Abriste la caja misteriosa y ganaste **{money(reward)}**. Te quedan **{profile['keys']}** llave(s).", mention_author=False)

    @commands.command(name="inventory", aliases=["inv", "inventario"])
    @commands.guild_only()
    async def inventory(self, ctx: commands.Context):
        data, profile = await self.get_profile(ctx)
        write_data(data)
        await ctx.reply(f"🎒 Inventario de {ctx.author.mention}: 🗝️ Llaves: **{profile['keys']}** · 💵 Cartera: **{money(profile['wallet'])}** · 🏦 Banco: **{money(profile['bank'])}**.", mention_author=False, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="sanciones")
    @commands.guild_only()
    async def sanciones(self, ctx: commands.Context, target: discord.Member | None = None):
        if not ctx.author.guild_permissions.moderate_members and not ctx.author.guild_permissions.manage_messages:
            await ctx.reply("Necesitás permisos de moderación para consultar las sanciones.", mention_author=False)
            return
        target = target or ctx.author
        data = read_data()
        entries = data.get("warnings", {}).get(f"{ctx.guild.id}:{target.id}", [])
        embed = discord.Embed(title=f"⚖️ Sanciones de {target}", color=discord.Color.orange())
        if entries:
            for index, entry in enumerate(entries[-10:], start=max(1, len(entries) - 9)):
                embed.add_field(name=f"Advertencia #{index}", value=str(entry.get("reason", "Sin motivo")), inline=False)
        else:
            embed.description = "No hay advertencias guardadas para este usuario."
        embed.set_footer(text="AzureSMP • Historial de advertencias")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="warn")
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx: commands.Context, target: discord.Member, *, reason: str = "Sin motivo indicado"):
        if target.bot or target.id == ctx.author.id:
            await ctx.reply("Elegí a otro miembro válido.", mention_author=False)
            return
        if target.top_role >= ctx.author.top_role:
            await ctx.reply("No podés sancionar a alguien con un rol igual o superior al tuyo.", mention_author=False)
            return
        data = read_data()
        entries = data.setdefault("warnings", {}).setdefault(f"{ctx.guild.id}:{target.id}", [])
        entries.append({"moderator": ctx.author.id, "reason": reason[:500], "timestamp": int(time.time())})
        write_data(data)
        await ctx.reply(f"⚠️ {target.mention} recibió una advertencia. Motivo: **{reason[:300]}**.", mention_author=False, allowed_mentions=discord.AllowedMentions(users=True))

    @warn.error
    async def warn_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("Necesitás el permiso **Moderar miembros** para usar .warn.", mention_author=False)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("Uso: `.warn @usuario motivo`.", mention_author=False)
        else:
            await ctx.reply("No pude aplicar la advertencia. Revisá los permisos y la jerarquía de roles.", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
