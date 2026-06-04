import os
import io
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from google import genai

# Load configuration values
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')

# Initialize the official Google GenAI Client
ai_client = genai.Client(api_key=GEMINI_KEY)

class GeminiDiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Synchronize slash commands globally across all servers
        await self.tree.sync()
        print("Slash commands synced successfully!")

bot = GeminiDiscordBot()

@bot.event
async def on_ready():
    print(f'🤖 Bot logged in as {bot.user.name}')
    print("Application is live and running 24/7 via Gemini engine.")

# 1. /ask Command (Gemini 2.5 Flash Text Generation)
@bot.tree.command(name="ask", description="Ask Gemini a question via text")
@app_commands.describe(prompt="What do you want to ask Gemini?")
async def ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        reply = response.text
        if len(reply) > 1950:
            reply = reply[:1950] + "... (truncated due to length limits)"
            
        output_text = f"🤖 **Gemini Response:**\n{reply}"
        await interaction.followup.send(content=output_text)
        
    except Exception as e:
        await interaction.followup.send(content=f"❌ Error communicating with Gemini API: {e}")

# 2. /imagine Command (Stable Production Imagen 3 Identifier)
@bot.tree.command(name="imagine", description="Generate a high-quality image using Imagen 3")
@app_commands.describe(prompt="Describe the image you want to create")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    
    try:
        result = ai_client.models.generate_images(
            model='imagen-3.0',  # Using the stable production identifier to prevent 404s
            prompt=prompt,
            config=dict(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="1:1"
            )
        )
        
        # Capture raw image data streaming into a sendable Discord file attachment
        generated_image = result.generated_images[0]
        image_bytes = io.BytesIO(generated_image.image.image_bytes)
        discord_file = discord.File(fp=image_bytes, filename="imagine.jpg")
        
        caption = f"🎨 **Imagen 3 Output for:** *\"{prompt}\"*";
        await interaction.followup.send(content=caption, file=discord_file)
    except Exception as e:
        await interaction.followup.send(content=f"❌ Failed to generate image: {e}")

# 3. /ai Command (Voice Framework Placeholder)
@bot.tree.command(name="ai", description="Make the bot join your VC and speak")
async def ai(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ You must be in a voice channel to execute this command!")
        return
        
    channel = interaction.user.voice.channel
    await interaction.response.send_message(f"🎙️ Joining voice channel: **{channel.name}**...")
    
    try:
        vc = await channel.connect()
        print(f"Connected successfully to voice channel {channel.name}")
    except Exception as e:
        await interaction.followup.send(content=f"❌ Failed to establish voice connection: {e}")

bot.run(TOKEN)
