AzureSMP Bot — módulo de comandos

IMPORTANTE:
- Este paquete conserva el main.py proporcionado y añade el módulo cogs.commands.
- No incluye el token real.
- Configura DISCORD_BOT_TOKEN y OWNER_ID como variables de entorno en tu hosting.
- No subas .env ni el token a GitHub.
- Instala dependencias con: pip install -r requirements.txt
- Para que funcionen bienvenida/despedida, activa Server Members Intent en Discord Developer Portal y habilita intents.members en main.py.
- La persistencia de advertencias y configuración usa azure_data.json en el directorio de trabajo; el hosting debe conservar ese archivo/disco.
- Revisa permisos y jerarquía del bot en Discord antes de usar comandos de moderación.
- Los comandos de presencia administrativa requieren permisos de administrador; /sync requiere OWNER_ID configurado o permisos de administrador.
- /remind funciona mientras el proceso siga encendido y el bot pueda enviar DM o mensaje en el canal.
