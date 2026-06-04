import os
import io
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load configuration values from environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')

# Initialize the official Google GenAI Client
ai_client = genai.Client(api_key=GEMINI_KEY)

class AssistantBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True  # Required to record and stream audio features
        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self):
        print(f'🎙️ Google Assistant Mode Active as {self.user.name}')
        print("Application is live and running 24/7 via Gemini engine.")

bot = AssistantBot()

# --- VOICE LOGIC PROCESSING ---

async def process_and_speak(vc, audio_path):
    """
    Takes the recorded voice file, sends it to Gemini to interpret,
    and streams the voice response back out loud.
    """
    try:
        print("Processing audio file with Gemini...")
        
        # Open the recorded audio file from the voice channel session
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        # Send the raw voice directly to Gemini with explicit system instructions
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                "You are a helpful voice assistant like Google Assistant. Listen to the user's voice message above and reply with a short, natural, single-sentence spoken response."
            ],
            config=types.GenerateContentConfig(
                response_mime_type="audio/mp3"  # Instructs Gemini to reply directly with an audio format
            )
        )

        # Extract the raw spoken audio bytes from the response
        reply_audio_data = response.candidates[0].content.parts[0].inline_data.data
        audio_stream = io.BytesIO(reply_audio_data)

        # Play the response audio directly back inside the voice channel
        print("Streaming Gemini voice response back to VC...")
        vc.play(discord.FFmpegPCMAudio(audio_stream, pipe=True))

    except Exception as e:
        print(f"Error handling voice response pipeline: {e}")

class VoiceSink(discord.sinks.WaveSink):
    """
    Custom audio receiver that catches the user's raw voice data streams.
    """
    def __init__(self, vc, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vc = vc

    def callback(self, user_id, file, error):
        # When recording halts, save the voice file and trigger the processing engine
        if not error:
            audio_path = f"user_{user_id}.wav"
            with open(audio_path, "wb") as f:
                f.write(file.read())
            
            # Initiate async task execution pipeline
            bot.loop.create_task(process_and_speak(self.vc, audio_path))

async def assistant_listening_loop(vc):
    """
    Continuous loop infrastructure that handles the recording cycles.
    """
    print("Starting continuous live listening loop...")
    while vc.is_connected():
        if vc.is_playing():
            await asyncio.sleep(0.5)
            continue

        # Record audio windows to capture conversation chunks
        sink = VoiceSink(vc)
        vc.start_recording(sink)
        await asyncio.sleep(5)  # Listens for speech in 5-second sampling cycles
        vc.stop_recording()     # Cuts the sink and fires off processing execution
        
        # Give the bot time to finish its response stream before sampling background room data again
        while vc.is_playing():
            await asyncio.sleep(0.5)

# --- NATIVE PY-CORD SLASH COMMANDS ---

# 1. Real-Time Assistant /ai Activation (Voice Loop)
@bot.slash_command(name="ai", description="Turn on real-time Google Assistant mode in your current VC")
async def ai(ctx: discord.ApplicationContext):
    if not ctx.author.voice:
        await ctx.respond("❌ You must join a voice channel first!")
        return

    channel = ctx.author.voice.channel
    await ctx.respond(f"🤖 **Google Assistant Activated** in **{channel.name}**! Speak freely, I am listening.")

    try:
        vc = await channel.connect()
        # Launch the async loop infrastructure task
        bot.loop.create_task(assistant_listening_loop(vc))
    except Exception as e:
        await ctx.send(content=f"❌ Voice interface failed: {e}")

# 2. Voice Assistant Deactivation Switch
@bot.slash_command(name="stop_ai", description="Stop the voice assistant loop and disconnect the bot")
async def stop_ai(ctx: discord.ApplicationContext):
    if ctx.guild.voice_client:
        await ctx.guild.voice_client.disconnect()
        await ctx.respond("👋 Assistant deactivated. Goodbye!")
    else:
        await ctx.respond("❌ I am not connected to any voice channel.")

# 3. Text Assistant Interface (/ask)
@bot.slash_command(name="ask", description="Ask Gemini a question via text")
async def ask(ctx: discord.ApplicationContext, prompt: str):
    await ctx.defer()
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        await ctx.respond(f"🤖 **Gemini Response:**\n{response.text}")
    except Exception as e:
        await ctx.respond(f"❌ Error communicating with Gemini API: {e}")

# 4. Corrected Image Generation Engine (/imagine)
@bot.slash_command(name="imagine", description="Generate a high-quality image using Imagen 3")
async def imagine(ctx: discord.ApplicationContext, prompt: str):
    await ctx.defer()
    try:
        # Using the standard production identifier format with proper dictionary configs
        result = ai_client.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=prompt,
            config=dict(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="1:1"
            )
        )

        if result and result.generated_images:
            generated_image = result.generated_images[0]
            image_bytes = io.BytesIO(generated_image.image.image_bytes)
            discord_file = discord.File(fp=image_bytes, filename="imagine.jpg")
            await ctx.respond(content=f"🎨 **Imagen 3 Output for:** *\"{prompt}\"*", file=discord_file)
        else:
            await ctx.respond("❌ API succeeded but returned no image data.")
            
    except Exception as e:
        await ctx.respond(f"❌ Failed to generate image: {e}")

bot.run(TOKEN)
