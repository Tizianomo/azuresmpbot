from __future__ import annotations
import json, os, random, time, tempfile
from pathlib import Path
from typing import Any
import discord
from discord.ext import commands

DATA_FILE = Path(os.getenv("AZURE_DATA_FILE", "azure_data.json"))
BLUE = discord.Color.from_rgb(0, 179, 255)
CD = {"daily":86400,"weekly":604800,"work":1800,"crime":2700,"rob":3600,"beg":300,"search":600,"fish":1200,"mine":1200,"hunt":1500,"collect":21600,"ludopatia":10}
ITEMS = {
 "llave":{"name":"Llave misteriosa","buy":500,"sell":250,"desc":"Abre una caja con premio aleatorio."},
 "caña":{"name":"Caña de pesca","buy":1200,"sell":500,"desc":"Mejora las ganancias al pescar."},
 "pico":{"name":"Pico reforzado","buy":1500,"sell":650,"desc":"Mejora las ganancias al minar."},
 "amuleto":{"name":"Amuleto de suerte","buy":3000,"sell":1200,"desc":"Objeto coleccionable."},
}
ITEM_ALIASES={"key":"llave","keys":"llave","llaves":"llave","rod":"caña","cana":"caña","pickaxe":"pico","charm":"amuleto"}

def read_data() -> dict[str, Any]:
    try:
        d=json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d,dict) else {}
    except (OSError,json.JSONDecodeError): return {}

def write_data(data: dict[str, Any]) -> None:
    DATA_FILE.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix="azure-",suffix=".json",dir=str(DATA_FILE.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
        os.replace(tmp,DATA_FILE)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def user_wallet(data: dict[str,Any], guild_id:int, user_id:int) -> dict[str,Any]:
    p=data.setdefault("economy",{}).setdefault(str(guild_id),{}).setdefault(str(user_id),{})
    p.setdefault("wallet",0); p.setdefault("bank",0); p.setdefault("keys",0)
    p.setdefault("cooldowns",{}); p.setdefault("items",{})
    p.setdefault("stats",{"earned":0,"spent":0,"won":0,"lost":0})
    for k in ("earned","spent","won","lost"): p["stats"].setdefault(k,0)
    return p

def money(n:int) -> str: return "$"+f"{int(n):,}".replace(",",".")
def remaining(seconds:float) -> str:
    seconds=max(0,int(seconds)); d,seconds=divmod(seconds,86400); h,seconds=divmod(seconds,3600); m,seconds=divmod(seconds,60)
    bits=[]
    if d: bits.append(f"{d} d")
    if h: bits.append(f"{h} h")
    if m: bits.append(f"{m} min")
    if seconds and not bits: bits.append(f"{seconds} s")
    return " ".join(bits) or "0 s"
def parse_amount(raw:str,available:int) -> int:
    v=raw.strip().lower().replace(",","").replace(".","")
    if v in ("all","todo","max"): return max(0,int(available))
    if v.endswith("%"):
        try: return max(0,min(int(available),int(int(available)*float(v[:-1])/100)))
        except ValueError: return 0
    mult=1
    if v.endswith("k"): mult,v=1000,v[:-1]
    elif v.endswith("m"): mult,v=1000000,v[:-1]
    elif v.endswith("b"): mult,v=1000000000,v[:-1]
    try:
        n=int(float(v)*mult)
        return n if n>0 else 0
    except ValueError: return 0
def item_key(v:str) -> str:
    v=v.strip().lower()
    return ITEM_ALIASES.get(v,v)

class Economy(commands.Cog):
    def __init__(self,bot:commands.Bot): self.bot=bot
    def profile(self,ctx): 
        d=read_data()
        return d,user_wallet(d,ctx.guild.id,ctx.author.id)
    def embed(self,title,description=None): return discord.Embed(title=title,description=description,color=BLUE,timestamp=discord.utils.utcnow())
    async def ready(self,ctx,p,name):
        duration=CD.get(name,0); now=time.time(); last=float(p["cooldowns"].get(name,0))
        if now-last<duration:
            await ctx.reply(f"⏳ Esperá **{remaining(duration-(now-last))}** para volver a usar este comando.",mention_author=False)
            return False
        p["cooldowns"][name]=now
        return True
    def earn(self,p,amount):
        p["wallet"]+=amount; p["stats"]["earned"]+=amount

    @commands.command(name="bal",aliases=["balance","dinero"])
    @commands.guild_only()
    async def bal(self,ctx,member:discord.Member|None=None):
        target=member or ctx.author; d=read_data(); p=user_wallet(d,ctx.guild.id,target.id); write_data(d)
        e=self.embed(f"💰 Economía de {target.display_name}"); e.set_thumbnail(url=target.display_avatar.url)
        e.add_field(name="💵 Cartera",value=money(p["wallet"]),inline=True); e.add_field(name="🏦 Banco",value=money(p["bank"]),inline=True)
        e.add_field(name="💎 Patrimonio",value=money(p["wallet"]+p["bank"]),inline=True); e.add_field(name="🗝️ Llaves",value=str(p["keys"]),inline=True)
        e.add_field(name="🎒 Objetos",value=str(sum(p["items"].values())),inline=True)
        await ctx.reply(embed=e,mention_author=False)

    @commands.command(name="bank",aliases=["banco"])
    @commands.guild_only()
    async def bank(self,ctx):
        _,p=self.profile(ctx); await ctx.reply(f"🏦 Tenés **{money(p['bank'])}** en el banco. El dinero guardado está protegido de robos.",mention_author=False)

    @commands.command(name="dep",aliases=["deposit","depositar"])
    @commands.guild_only()
    async def dep(self,ctx,amount:str):
        d,p=self.profile(ctx); n=parse_amount(amount,p["wallet"])
        if not 0<n<=p["wallet"]: return await ctx.reply("Cantidad inválida. Ejemplos: .dep 10k, .dep 50% o .dep all.",mention_author=False)
        p["wallet"]-=n; p["bank"]+=n; write_data(d)
        await ctx.reply(f"🏦 Depositaste **{money(n)}**. Cartera: {money(p['wallet'])} · Banco: {money(p['bank'])}.",mention_author=False)

    @commands.command(name="with",aliases=["withdraw","retirar"])
    @commands.guild_only()
    async def withdraw(self,ctx,amount:str):
        d,p=self.profile(ctx); n=parse_amount(amount,p["bank"])
        if not 0<n<=p["bank"]: return await ctx.reply("Cantidad inválida. Ejemplos: .with 2m, .with 50% o .with all.",mention_author=False)
        p["bank"]-=n; p["wallet"]+=n; write_data(d)
        await ctx.reply(f"💵 Retiraste **{money(n)}**. Cartera: {money(p['wallet'])} · Banco: {money(p['bank'])}.",mention_author=False)

    @commands.command(name="pay",aliases=["pagar","transferir"])
    @commands.guild_only()
    async def pay(self,ctx,member:discord.Member,amount:str):
        if member.bot or member.id==ctx.author.id: return await ctx.reply("Elegí a otra persona real.",mention_author=False)
        d,p=self.profile(ctx); target=user_wallet(d,ctx.guild.id,member.id); n=parse_amount(amount,p["wallet"])
        if not 0<n<=p["wallet"]: return await ctx.reply("No tenés esa cantidad en la cartera.",mention_author=False)
        p["wallet"]-=n; p["stats"]["spent"]+=n; target["wallet"]+=n; target["stats"]["earned"]+=n; write_data(d)
        await ctx.reply(f"🤝 Transferiste **{money(n)}** a {member.mention}.",mention_author=False,allowed_mentions=discord.AllowedMentions(users=True))

    @commands.command(name="cooldowns",aliases=["cd","tiempos"])
    @commands.guild_only()
    async def cooldowns(self,ctx):
        _,p=self.profile(ctx); now=time.time(); lines=[]
        for name,duration in CD.items():
            last=float(p["cooldowns"].get(name,0)); state="Disponible" if now-last>=duration else "En "+remaining(duration-(now-last))
            lines.append(f"**.{name}** — {state}")
        await ctx.reply(embed=self.embed("⏱️ Tus cooldowns","\n".join(lines)),mention_author=False)

    @commands.command(name="daily",aliases=["diario"])
    @commands.guild_only()
    async def daily(self,ctx):
        d,p=self.profile(ctx)
        if not await self.ready(ctx,p,"daily"): return
        n=random.randint(1200,2200); self.earn(p,n); write_data(d)
        await ctx.reply(f"🎁 Cobraste tu recompensa diaria: **{money(n)}**.",mention_author=False)

    @commands.command(name="weekly",aliases=["semanal"])
    @commands.guild_only()
    async def weekly(self,ctx):
        d,p=self.profile(ctx)
        if not await self.ready(ctx,p,"weekly"): return
        n=random.randint(8000,15000); self.earn(p,n); write_data(d)
        await ctx.reply(f"📅 Recompensa semanal: **{money(n)}**.",mention_author=False)

    @commands.command(name="collect",aliases=["cobrar"])
    @commands.guild_only()
    async def collect(self,ctx):
        d,p=self.profile(ctx)
        if not await self.ready(ctx,p,"collect"): return
        n=random.randint(2000,4500); self.earn(p,n); write_data(d)
        await ctx.reply(f"📦 Cobraste tu contrato: **{money(n)}**. Disponible de nuevo en 6 horas.",mention_author=False)

    @commands.command(name="work",aliases=["trabajar"])
    @commands.guild_only()
    async def work(self,ctx):
        d,p=self.profile(ctx)
        if not await self.ready(ctx,p,"work"): return
        job,n=random.choice([("repartidor",random.randint(450,850)),("constructor",random.randint(500,950)),("camarero",random.randint(400,800)),("programador",random.randint(700,1200)),("mecánico",random.randint(550,1000))])
        self.earn(p,n); write_data(d); await ctx.reply(f"🧰 Trabajaste como **{job}** y ganaste **{money(n)}**.",mention_author=False)

    @commands.command(name="crime",aliases=["crimen","delito"])
    @commands.guild_only()
    async def crime(self,ctx):
        d,p=self.profile(ctx)
        if not await self.ready(ctx,p,"crime"): return
        if random.random()<.58:
            n=random.randint(700,2800); self.earn(p,n); msg=f"🕶️ El golpe salió bien: conseguiste **{money(n)}**."
        else:
            n=min(p["wallet"],random.randint(300,1500)); p["wallet"]-=n; p["stats"]["lost"]+=n; msg=f"🚨 Te atraparon y pagaste **{money(n)}** de multa."
        write_data(d); await ctx.reply(msg,mention_author=False)

    @commands.command(name="rob",aliases=["robar"])
    @commands.guild_only()
    async def rob(self,ctx,target:discord.Member):
        if target.bot or target.id==ctx.author.id: return await ctx.reply("Mencioná a otra persona real.",mention_author=False)
        d,p=self.profile(ctx); victim=user_wallet(d,ctx.guild.id,target.id)
        if victim["wallet"]<=0: return await ctx.reply("Esa persona no tiene dinero en la cartera. El banco está protegido.",mention_author=False)
        if not await self.ready(ctx,p,"rob"): return
        if random.random()>=.17:
            n=min(p["wallet"],random.randint(100,700)); p["wallet"]-=n; p["stats"]["lost"]+=n; write_data(d)
            return await ctx.reply(f"🚔 Fallaste el robo y pagaste **{money(n)}** de multa. Éxito: 17%.",mention_author=False)
        n=min(victim["wallet"],max(1,int(victim["wallet"]*random.uniform(.08,.25))))
        victim["wallet"]-=n; victim["stats"]["lost"]+=n; p["wallet"]+=n; p["stats"]["earned"]+=n; write_data(d)
        await ctx.reply(f"🕵️ Le robaste **{money(n)}** a {target.mention}. Guardá tu dinero en el banco.",mention_author=False,allowed_mentions=discord.AllowedMentions(users=True))

    @commands.command(name="beg",aliases=["mendigar","pedir"])
    @commands.guild_only()
    async def beg(self,ctx):
        d,p=self.profile(ctx)
        if not await self.ready(ctx,p,"beg"): return
        if random.random()<.72:
            n=random.randint(50,450); self.earn(p,n); msg=f"🪙 Alguien te dio **{money(n)}**."
        else: msg="🥲 Nadie te dio dinero esta vez."
        write_data(d); await ctx.reply(msg,mention_author=False)

    @commands.command(name="search",aliases=["buscar","explorar"])
    @commands.guild_only()
    async def search(self,ctx):
        d,p=self.profile(ctx)
        if not await self.ready(ctx,p,"search"): return
        place,n=random.choice([("un parque",random.randint(100,450)),("un callejón",random.randint(200,650)),("la playa",random.randint(150,550)),("una estación abandonada",random.randint(250,800)),("un cofre enterrado",random.randint(500,1500))])
        self.earn(p,n); write_data(d); await ctx.reply(f"🔎 Buscaste en **{place}** y encontraste **{money(n)}**.",mention_author=False)

    @commands.command(name="fish",aliases=["pescar"])
    @commands.guild_only()
    async def fish(self,ctx):
        d,p=self.profile(ctx)
        if not await self.ready(ctx,p,"fish"): return
        fish,n=random.choice([("sardina",120),("trucha",250),("salmón",380),("pez dorado",550),("bota vieja",25),("pez legendario",1200)])
        n=int(n*(1.25 if p["items"].get("caña",0) else 1)); self.earn(p,n); write_data(d)
        await ctx.reply(f"🎣 Pescaste **{fish}** y ganaste **{money(n)}**.",mention_author=False)

    @commands.command(name="mine",aliases=["minar"])
    @commands.guild_only()
    async def mine(self,ctx):
        d,p=self.profile(ctx)
        if not await self.ready(ctx,p,"mine"): return
        ore,n=random.choice([("carbón",100),("hierro",220),("oro",350),("diamantes",650),("esmeraldas",800),("piedra",35),("cristal de Azure",1300)])
        n=int(n*(1.25 if p["items"].get("pico",0) else 1)); self.earn(p,n); write_data(d)
        await ctx.reply(f"⛏️ Encontraste **{ore}** y ganaste **{money(n)}**.",mention_author=False)

    @commands.command(name="hunt",aliases=["cazar"])
    @commands.guild_only()
    async def hunt(self,ctx):
        d,p=self.profile(ctx)
        if not await self.ready(ctx,p,"hunt"): return
        animal,n=random.choice([("un conejo",250),("un zorro",400),("un jabalí",650),("un ciervo",800),("una criatura mítica",1800)])
        self.earn(p,n); write_data(d); await ctx.reply(f"🏹 Cazaste {animal} y vendiste los recursos por **{money(n)}**.",mention_author=False)

    @commands.command(name="shopitems",aliases=["tienda","shop"])
    @commands.guild_only()
    async def shopitems(self,ctx):
        e=self.embed("🛒 Tienda AzureSMP","Usá .buy <objeto> [cantidad], .sell <objeto> [cantidad] y .inventory.")
        for k,it in ITEMS.items(): e.add_field(name=f"{it['name']} ({k})",value=f"Comprar: **{money(it['buy'])}** · Vender: **{money(it['sell'])}\n**{it['desc']}",inline=False)
        await ctx.reply(embed=e,mention_author=False)

    @commands.command(name="shopinfo",aliases=["iteminfo"])
    @commands.guild_only()
    async def shopinfo(self,ctx,*,item:str|None=None):
        if not item: return await ctx.invoke(self.shopitems)
        k=item_key(item)
        if k not in ITEMS: return await ctx.reply("Ese objeto no existe. Usá .shopitems.",mention_author=False)
        it=ITEMS[k]; await ctx.reply(embed=self.embed(it["name"],f"{it['desc']}\nComprar: {money(it['buy'])}\nVender: {money(it['sell'])}"),mention_author=False)

    @commands.command(name="buy",aliases=["comprar"])
    @commands.guild_only()
    async def buy(self,ctx,item:str,quantity:int=1):
        k=item_key(item)
        if k not in ITEMS or not 1<=quantity<=100: return await ctx.reply("Uso: .buy <llave|caña|pico|amuleto> [cantidad] (máximo 100).",mention_author=False)
        d,p=self.profile(ctx); total=ITEMS[k]["buy"]*quantity
        if p["wallet"]<total: return await ctx.reply(f"Te faltan **{money(total-p['wallet'])}**.",mention_author=False)
        p["wallet"]-=total; p["stats"]["spent"]+=total
        if k=="llave": p["keys"]+=quantity
        else: p["items"][k]=int(p["items"].get(k,0))+quantity
        write_data(d); await ctx.reply(f"🛍️ Compraste **{quantity} × {ITEMS[k]['name']}** por **{money(total)}**.",mention_author=False)

    @commands.command(name="sell",aliases=["vender"])
    @commands.guild_only()
    async def sell(self,ctx,item:str,quantity:str="1"):
        k=item_key(item)
        if k not in ITEMS: return await ctx.reply("Ese objeto no se puede vender. Usá .shopitems.",mention_author=False)
        d,p=self.profile(ctx); owned=p["keys"] if k=="llave" else int(p["items"].get(k,0))
        n=owned if quantity.lower() in ("all","todo") else parse_amount(quantity,owned)
        if not 0<n<=owned: return await ctx.reply(f"No tenés esa cantidad. Disponible: {owned}.",mention_author=False)
        if k=="llave": p["keys"]-=n
        else: p["items"][k]-=n
        total=ITEMS[k]["sell"]*n; self.earn(p,total); write_data(d)
        await ctx.reply(f"💱 Vendiste {n} × {ITEMS[k]['name']} por **{money(total)}**.",mention_author=False)

    @commands.command(name="inventory",aliases=["inv","inventario"])
    @commands.guild_only()
    async def inventory(self,ctx):
        _,p=self.profile(ctx); lines=[f"🗝️ Llaves: **{p['keys']}**"]
        lines.extend(f"• {ITEMS[k]['name']}: **{n}**" for k,n in p["items"].items() if n and k in ITEMS)
        lines.append(f"💵 Cartera: **{money(p['wallet'])}** · 🏦 Banco: **{money(p['bank'])}**")
        await ctx.reply(embed=self.embed(f"🎒 Inventario de {ctx.author.display_name}","\n".join(lines)),mention_author=False)

    @commands.command(name="use",aliases=["usar"])
    @commands.guild_only()
    async def use(self,ctx,item:str,quantity:int=1):
        k=item_key(item); d,p=self.profile(ctx)
        if k!="llave": return await ctx.reply("Por ahora solo podés usar llaves: .use llave [cantidad].",mention_author=False)
        if not 1<=quantity<=20 or p["keys"]<quantity: return await ctx.reply("No tenés suficientes llaves o la cantidad no es válida.",mention_author=False)
        rewards=[random.choices([250,500,900,1500,3000,7500,15000],weights=[25,25,22,15,8,4,1],k=1)[0] for _ in range(quantity)]
        total=sum(rewards); p["keys"]-=quantity; self.earn(p,total); write_data(d)
        await ctx.reply(f"🎁 Abriste {quantity} caja(s) y recibiste **{money(total)}**.",mention_author=False)

    async def casino(self,ctx,bet:str,game:str,choice:str=""):
        d,p=self.profile(ctx); stake=parse_amount(bet,p["wallet"])
        if not 0<stake<=p["wallet"]: return await ctx.reply("Apuesta inválida o saldo insuficiente.",mention_author=False)
        win=False; multiplier=1; detail=""
        if game=="slots":
            roll=[random.choice(["🍒","🍋","🍇","💎","7️⃣"]) for _ in range(3)]; count=max(roll.count(s) for s in set(roll)); multiplier=5 if count==3 else 1 if count==2 else 0; detail=" ".join(roll); win=multiplier>0
        elif game=="coinflip":
            side=random.choice(["cara","cruz"]); win=choice.lower() in (side,"heads" if side=="cara" else "tails"); detail=f"salió {side}"
        elif game=="dice":
            n=random.randint(1,6)
            if choice and choice.isdigit(): win=n==int(choice); multiplier=4
            else: win=n>=4
            detail=f"salió {n}"
        elif game=="scratch":
            roll=[random.choice(["⭐","🍀","💎","🍒","7️⃣"]) for _ in range(3)]; count=max(roll.count(s) for s in set(roll)); multiplier=4 if count==3 else 1 if count==2 else 0; detail=" ".join(roll); win=multiplier>0
        elif game=="rps":
            aliases={"piedra":"rock","papel":"paper","tijera":"scissors","tijeras":"scissors"}; choice=aliases.get(choice.lower(),choice.lower()); other=random.choice(["rock","paper","scissors"]); detail=f"vos: {choice}, Selene: {other}"
            win=(choice,other) in (("rock","scissors"),("paper","rock"),("scissors","paper"))
            if choice==other: return await ctx.reply(f"🤝 Empate ({detail}). No cambia tu saldo.",mention_author=False)
        elif game=="roulette":
            n=random.randint(0,36); color="green" if n==0 else "red" if n%2 else "black"; detail=f"{n} ({color})"
            win=choice.lower() in (color,{"red":"rojo","black":"negro","green":"verde"}.get(color))
            if choice.lower() in ("par","even"): win=n!=0 and n%2==0
            if choice.lower() in ("impar","odd"): win=n%2==1
            if color=="green" and win: multiplier=14
        elif game=="hilo":
            a,b=random.randint(1,13),random.randint(1,13); detail=f"{a} → {b}"
            if a==b: return await ctx.reply(f"🤝 Empate ({detail}). No cambia tu saldo.",mention_author=False)
            win=(b>a and choice.lower() in ("higher","mayor","alto")) or (b<a and choice.lower() in ("lower","menor","bajo"))
        elif game=="bj":
            a,b=random.randint(16,23),random.randint(15,23); detail=f"vos {a}, Selene {b}"
            if a==b: return await ctx.reply(f"🤝 Empate ({detail}). No cambia tu saldo.",mention_author=False)
            win=a<=21 and (b>21 or a>b)
            if a>21: win=False
        if win:
            amount=stake*multiplier; p["wallet"]+=amount; p["stats"]["won"]+=amount; msg=f"🎉 Ganaste **{money(amount)}** ({detail})."
        else:
            p["wallet"]-=stake; p["stats"]["lost"]+=stake; msg=f"🎲 Perdiste **{money(stake)}** ({detail})."
        write_data(d); await ctx.reply(msg,mention_author=False)

    @commands.command(name="bj",aliases=["blackjack"])
    @commands.guild_only()
    async def bj(self,ctx,bet:str): await self.casino(ctx,bet,"bj")
    @commands.command(name="hilo")
    @commands.guild_only()
    async def hilo(self,ctx,bet:str,choice:str="higher"): await self.casino(ctx,bet,"hilo",choice)
    @commands.command(name="slots",aliases=["tragamonedas"])
    @commands.guild_only()
    async def slots(self,ctx,bet:str): await self.casino(ctx,bet,"slots")
    @commands.command(name="coinflip",aliases=["moneda","caraocruz"])
    @commands.guild_only()
    async def coinflip(self,ctx,bet:str,choice:str="cara"): await self.casino(ctx,bet,"coinflip",choice)
    @commands.command(name="dice",aliases=["dados"])
    @commands.guild_only()
    async def dice(self,ctx,bet:str,guess:str=""): await self.casino(ctx,bet,"dice",guess)
    @commands.command(name="roulette",aliases=["ruleta"])
    @commands.guild_only()
    async def roulette(self,ctx,bet:str,choice:str="red"): await self.casino(ctx,bet,"roulette",choice)
    @commands.command(name="rps",aliases=["ppt"])
    @commands.guild_only()
    async def rps(self,ctx,bet:str,choice:str): await self.casino(ctx,bet,"rps",choice)
    @commands.command(name="scratch",aliases=["raspadita"])
    @commands.guild_only()
    async def scratch(self,ctx,bet:str): await self.casino(ctx,bet,"scratch")

    @commands.command(name="ludopatia",aliases=["selene"])
    @commands.guild_only()
    async def ludopatia(self,ctx,bet:str="100"):
        d,p=self.profile(ctx)
        if not await self.ready(ctx,p,"ludopatia"): return
        stake=parse_amount(bet,p["wallet"])
        if not 0<stake<=p["wallet"]: return await ctx.reply("Apuesta inválida. Uso: .ludopatia 100.",mention_author=False)
        r=random.random()
        if r<.45: p["wallet"]+=stake; p["stats"]["won"]+=stake; msg=f"🌙 Selene te entrega {money(stake)}. ¡Ganaste!"
        elif r<.9: p["wallet"]-=stake; p["stats"]["lost"]+=stake; msg=f"🌙 Selene se queda con {money(stake)}. Esta vez ganó ella."
        else: msg="🌙 Selene te devuelve la apuesta. Empate."
        write_data(d); await ctx.reply(msg+"\n*Dinero virtual; cooldown de 10 segundos.*",mention_author=False)

    async def show_top(self,ctx,mode,page):
        d=read_data(); eco=d.get("economy",{}).get(str(ctx.guild.id),{}); mode=mode.lower()
        key="wallet" if mode in ("-cash","cash","wallet") else "bank" if mode in ("-bank","bank") else "total"
        label={"wallet":"Cartera","bank":"Banco","total":"Patrimonio"}[key]; rows=[]
        for uid in eco:
            try:
                p=user_wallet(d,ctx.guild.id,int(uid)); amount=p["wallet"] if key=="wallet" else p["bank"] if key=="bank" else p["wallet"]+p["bank"]
                rows.append((int(uid),int(amount)))
            except (ValueError,TypeError): pass
        rows.sort(key=lambda x:x[1],reverse=True); page=max(1,page); chunk=rows[(page-1)*10:page*10]
        if not chunk: return await ctx.reply("No hay resultados en esa página.",mention_author=False)
        lines=[]
        for rank,(uid,amount) in enumerate(chunk,start=(page-1)*10+1):
            member=ctx.guild.get_member(uid); name=member.display_name if member else f"Usuario {uid}"; medal={1:"🥇",2:"🥈",3:"🥉"}.get(rank,f"{rank}.")
            lines.append(f"{medal} **{discord.utils.escape_markdown(name)}** — {money(amount)}")
        e=self.embed(f"🏆 Ranking de {label}","\n".join(lines)); e.set_footer(text=f"Página {page} · {len(rows)} perfiles · Ejemplo: .top -cash 2")
        await ctx.reply(embed=e,mention_author=False)

    @commands.command(name="top",aliases=["leaderboard"])
    @commands.guild_only()
    async def top(self,ctx,mode:str="-total",page:int=1): await self.show_top(ctx,mode,page)
    @commands.command(name="rankeco")
    @commands.guild_only()
    async def rankeco(self,ctx,mode:str="-total",page:int=1): await self.show_top(ctx,mode,page)

    @commands.command(name="profile",aliases=["perfil"])
    @commands.guild_only()
    async def profile_cmd(self,ctx,member:discord.Member|None=None):
        target=member or ctx.author; d=read_data(); p=user_wallet(d,ctx.guild.id,target.id); rows=d.get("economy",{}).get(str(ctx.guild.id),{}); values=[]
        for uid in rows:
            try:
                q=user_wallet(d,ctx.guild.id,int(uid)); values.append((int(uid),q["wallet"]+q["bank"]))
            except (ValueError,TypeError): pass
        values.sort(key=lambda x:x[1],reverse=True); rank=next((i for i,row in enumerate(values,1) if row[0]==target.id),None)
        e=self.embed(f"👤 Perfil económico de {target.display_name}"); e.set_thumbnail(url=target.display_avatar.url)
        e.add_field(name="Cartera",value=money(p["wallet"]),inline=True); e.add_field(name="Banco",value=money(p["bank"]),inline=True)
        e.add_field(name="Patrimonio",value=money(p["wallet"]+p["bank"]),inline=True); e.add_field(name="Ranking",value=f"#{rank}" if rank else "Sin ranking",inline=True)
        e.add_field(name="Ganado",value=money(p["stats"]["earned"]),inline=True); e.add_field(name="Ganancias casino",value=money(p["stats"]["won"]),inline=True); e.add_field(name="Pérdidas",value=money(p["stats"]["lost"]),inline=True)
        await ctx.reply(embed=e,mention_author=False)

    @commands.command(name="networth",aliases=["patrimonio"])
    @commands.guild_only()
    async def networth(self,ctx,member:discord.Member|None=None):
        target=member or ctx.author; d=read_data(); p=user_wallet(d,ctx.guild.id,target.id)
        await ctx.reply(f"💎 Patrimonio de **{target.display_name}**: **{money(p['wallet']+p['bank'])}** (cartera + banco).",mention_author=False)

    @commands.command(name="jobs",aliases=["trabajos","job"])
    @commands.guild_only()
    async def jobs(self,ctx):
        e=self.embed("🧰 Trabajos de AzureSMP","Ganancias aproximadas y cooldowns:")
        for name,desc in [("Work",".work · 30 min"),("Crime",".crime · 45 min"),("Beg",".beg · 5 min"),("Search",".search · 10 min"),("Fish",".fish · 20 min"),("Mine",".mine · 20 min"),("Hunt",".hunt · 25 min")]: e.add_field(name=name,value=desc,inline=True)
        await ctx.reply(embed=e,mention_author=False)

    @commands.command(name="sanciones")
    @commands.guild_only()
    async def sanciones(self,ctx,target:discord.Member|None=None):
        if not ctx.author.guild_permissions.moderate_members and not ctx.author.guild_permissions.manage_messages:
            return await ctx.reply("Necesitás permisos de moderación para consultar las sanciones.",mention_author=False)
        target=target or ctx.author; d=read_data(); entries=d.get("warnings",{}).get(f"{ctx.guild.id}:{target.id}",[]); e=self.embed(f"⚖️ Sanciones de {target.display_name}")
        if entries:
            for i,item in enumerate(entries[-10:],start=max(1,len(entries)-9)): e.add_field(name=f"Advertencia #{i}",value=f"{item.get('reason','Sin motivo')}\nPor: <@{item.get('moderator',0)}>",inline=False)
        else: e.description="No hay advertencias guardadas para este usuario."
        await ctx.reply(embed=e,mention_author=False)

    @commands.command(name="warn")
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def warn(self,ctx,target:discord.Member,*,reason:str="Sin motivo indicado"):
        if target.bot or target.id==ctx.author.id: return await ctx.reply("Elegí a otro miembro válido.",mention_author=False)
        if target.top_role>=ctx.author.top_role and ctx.guild.owner_id!=ctx.author.id: return await ctx.reply("No podés sancionar a alguien con un rol igual o superior al tuyo.",mention_author=False)
        d=read_data(); entries=d.setdefault("warnings",{}).setdefault(f"{ctx.guild.id}:{target.id}",[])
        entries.append({"moderator":ctx.author.id,"reason":reason[:500],"timestamp":int(time.time())}); write_data(d)
        await ctx.reply(f"⚠️ {target.mention} recibió una advertencia. Motivo: **{reason[:300]}**.",mention_author=False,allowed_mentions=discord.AllowedMentions(users=True))

    @warn.error
    async def warn_error(self,ctx,error):
        if isinstance(error,commands.MissingPermissions): await ctx.reply("Necesitás el permiso Moderar miembros para usar .warn.",mention_author=False)
        elif isinstance(error,commands.MissingRequiredArgument): await ctx.reply("Uso: .warn @usuario motivo.",mention_author=False)
        else: await ctx.reply("No pude aplicar la advertencia. Revisá los permisos y la jerarquía de roles.",mention_author=False)

async def setup(bot:commands.Bot):
    await bot.add_cog(Economy(bot))
