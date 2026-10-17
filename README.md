# AzureSMP Bot

Bot de Discord de AzureSMP con comandos de moderación, utilidades y economía.

## Economía

La economía guarda los datos en \`azure_data.json\` y separa los perfiles por servidor. Comandos principales:

- Cuenta: \`.bal\`, \`.dep\`, \`.with\`, \`.pay\`, \`.cooldowns\`
- Recompensas: \`.daily\`, \`.weekly\`, \`.collect\`
- Actividades: \`.work\`, \`.crime\`, \`.rob\`, \`.beg\`, \`.search\`, \`.fish\`, \`.mine\`, \`.hunt\`
- Casino virtual: \`.bj\`, \`.hilo\`, \`.slots\`, \`.coinflip\`, \`.dice\`, \`.roulette\`, \`.rps\`, \`.scratch\`, \`.ludopatia\`
- Tienda: \`.shopitems\`, \`.shopinfo\`, \`.buy\`, \`.sell\`, \`.inventory\`, \`.use\`
- Ranking: \`.top\`, \`.top -cash\`, \`.top -bank\`, \`.top -total\`, \`.rankeco\`, \`.profile\`, \`.networth\`

Cantidades: \`10k\`, \`2m\`, \`50%\`, \`all\` y \`todo\`. El casino utiliza dinero virtual.

## Panel web

La interfaz está en \`web/index.html\`. Puede publicarse como sitio estático desde GitHub Pages usando la carpeta \`/web\` como fuente si la configuración de Pages del repositorio lo permite.

El panel requiere una URL HTTPS accesible de la API del bot y una clave privada independiente.

Variables de entorno necesarias en el hosting:

- \`DISCORD_BOT_TOKEN\`: token privado del bot de Discord.
- \`DISCORD_BOT_BRIDGE_TOKEN\`: clave secreta diferente para autenticar el panel web. No uses el token del bot como clave del panel.
- \`DISCORD_BOT_BRIDGE_PORT\`: puerto HTTP que el hosting debe exponer y asignar a la API (por defecto 8000).
- \`DASHBOARD_ORIGINS\`: orígenes permitidos para la web. Durante pruebas puede ser \`*\`; en producción, configura el dominio real de GitHub Pages.
- \`AZURE_DATA_FILE\`: opcional, ruta de \`azure_data.json\` si el archivo de datos está en otro lugar.

El panel puede consultar estado, iniciar o detener la conexión de Discord, publicar mensajes, leer mensajes de canales accesibles, exportar una transcripción de los últimos mensajes y consultar advertencias guardadas.

**Importante sobre prender/apagar:** el botón de apagado cierra la conexión de Discord, no detiene el proceso Python completo. El proceso y la API deben seguir activos para poder volver a prenderlo desde la web. El hosting debe mantener ese proceso funcionando 24/7 y exponer el puerto configurado. Si el proveedor detiene el contenedor completo, la web no podrá arrancarlo desde ese mismo contenedor.

## Seguridad

1. Configura los secretos en las variables de entorno del hosting, no en archivos públicos ni en GitHub.
2. Genera una clave aleatoria para \`DISCORD_BOT_BRIDGE_TOKEN\` y guárdala de forma privada.
3. La clave del panel permite operar el bot y consultar mensajes accesibles; no la compartas.
4. Habilita Message Content Intent en Discord Developer Portal para que funcionen los comandos con prefijo y la lectura de mensajes.
5. El bot necesita permisos adecuados en Discord para enviar mensajes y leer historiales.

## Ejecución

Instala dependencias con \`pip install -r requirements.txt\` y ejecuta \`python main.py\`. La variable \`DISCORD_BOT_TOKEN\` debe estar configurada antes del inicio.
