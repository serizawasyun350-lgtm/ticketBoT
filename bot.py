import asyncio
import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, Modal, TextInput, View
from aiohttp import web

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

# サーバーごとの通報チャンネルIDを保存する辞書 (※Botを再起動するとリセットされます)
report_channels = {}


# 1. 通報理由を入力するモーダル（ポップアップ）
class ReportModal(Modal, title="サーバー管理者に通報する"):
  reason = TextInput(
      label="通報理由",
      style=discord.TextStyle.paragraph,
      placeholder="不正行為や荒らし、迷惑行為の内容を詳しく記入してください...",
      required=True,
      max_length=1000,
  )

  async def on_submit(self, interaction: discord.Interaction):
    guild = interaction.guild
    # このサーバーに設定された通報チャンネルIDを取得
    channel_id = report_channels.get(guild.id)
    report_channel = guild.get_channel(channel_id) if channel_id else None

    # 埋め込み（Embed）で管理者向けに通報内容を作成
    embed = discord.Embed(
        title="🚨 新しい通報がありました",
        color=discord.Color.orange(),
    )
    embed.add_field(
        name="通報者",
        value=f"{interaction.user} (ID: {interaction.user.id})",
        inline=False,
    )
    embed.add_field(
        name="対象チャンネル", value=interaction.channel.mention, inline=False
    )
    embed.add_field(
        name="通報理由", value=self.reason.value, inline=False
    )
    embed.set_footer(
        text=f"サーバー名: {guild.name}",
        icon_url=guild.icon.url if guild.icon else None,
    )

    # 通報チャンネルが設定されている場合は送信
    if report_channel:
      await report_channel.send(embed=embed)
      await interaction.response.send_message(
          "管理者へ通報を送信しました。ご協力ありがとうございます。", ephemeral=True
      )
    else:
      await interaction.response.send_message(
          "エラー: このサーバーの通報チャンネルが設定されていません。管理者に `/report_setup` の実行をお願いしてください。",
          ephemeral=True,
      )


# 2. チケットを閉じる際の確認用ビュー
class CloseConfirmView(View):

  def __init__(self):
    super().__init__(timeout=60)

  @discord.ui.button(
      label="はい、閉じます",
      style=discord.ButtonStyle.danger,
      custom_id="confirm_close",
  )
  async def confirm_close(
      self, interaction: discord.Interaction, button: Button
  ):
    await interaction.response.send_message(
        "チケットを閉じています... (5秒後に削除されます)", ephemeral=True
    )
    await asyncio.sleep(5)
    await interaction.channel.delete()

  @discord.ui.button(
      label="キャンセル",
      style=discord.ButtonStyle.secondary,
      custom_id="cancel_close",
  )
  async def cancel_close(
      self, interaction: discord.Interaction, button: Button
  ):
    await interaction.message.delete()
    await interaction.response.send_message("キャンセルしました。", ephemeral=True)


# 3. チケット内部に表示されるコントロールパネル（閉じるボタン ＋ 通報ボタン）
class TicketControlView(View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="🔒 チケットを閉じる",
      style=discord.ButtonStyle.red,
      custom_id="close_ticket",
  )
  async def close_ticket(
      self, interaction: discord.Interaction, button: Button
  ):
    await interaction.response.send_message(
        "本当にこのチケットを閉じますか？",
        view=CloseConfirmView(),
        ephemeral=True,
    )

  @discord.ui.button(
      label="🚨 管理者へ通報",
      style=discord.ButtonStyle.secondary,
      custom_id="report_ticket",
  )
  async def report_ticket(
      self, interaction: discord.Interaction, button: Button
  ):
    await interaction.response.send_modal(ReportModal())


# 4. 最初のエントリーパネル（チケット作成ボタン）
class TicketView(View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="🎫 チケットを作成",
      style=discord.ButtonStyle.green,
      custom_id="create_ticket",
  )
  async def create_ticket(
      self, interaction: discord.Interaction, button: Button
  ):
    guild = interaction.guild

    channel_name = f"ticket-{interaction.user.name.lower()}"
    existing_channel = discord.utils.get(
        guild.text_channels, name=channel_name
    )
    if existing_channel:
      await interaction.response.send_message(
          f"すでにチケットチャンネルが存在します: {existing_channel.mention}",
          ephemeral=True,
      )
      return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(
            read_messages=True, send_messages=True, read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True,
        ),
    }

    ticket_channel = await guild.create_text_channel(
        name=channel_name, overwrites=overwrites
    )

    await ticket_channel.send(
        f"{interaction.user.mention} さん、ようこそ！\nスタッフが対応するまでしばらくお待ちください。",
        view=TicketControlView(),
    )

    await interaction.response.send_message(
        f"チケットを作成しました！ 👉 {ticket_channel.mention}", ephemeral=True
    )


@bot.event
async def on_ready():
  print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
  bot.add_view(TicketView())
  bot.add_view(TicketControlView())

  try:
    synced = await bot.tree.sync()
    print(f"{len(synced)} 個のスラッシュコマンドを同期しました。")
  except Exception as e:
    print(e)


# /ticket_panel スラッシュコマンド
@bot.tree.command(
    name="ticket_panel", description="チケット作成パネルを送信します"
)
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
  embed = discord.Embed(
      title="🎫 お問い合わせチケット",
      description=(
          "下のボタンを押すと、あなた専用のプライベートチャンネルが作成されます。\n"
          "何かご用件がある場合はボタンを押してください。"
      ),
      color=discord.Color.blue(),
  )
  await interaction.channel.send(embed=embed, view=TicketView())
  await interaction.response.send_message(
      "チケットパネルを送信しました！", ephemeral=True
  )


@ticket_panel.error
async def ticket_panel_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
  if isinstance(error, app_commands.errors.MissingPermissions):
    if interaction.response.is_done():
      await interaction.followup.send(
          "このコマンドを実行する権限（管理者権限）がありません。", ephemeral=True
      )
    else:
      await interaction.response.send_message(
          "このコマンドを実行する権限（管理者権限）がありません。", ephemeral=True
      )


# /report_setup スラッシュコマンド（通報チャンネルの指定）
@bot.tree.command(
    name="report_setup", description="通報通知を受け取るチャンネルを設定します"
)
@app_commands.describe(channel="通報通知を送るテキストチャンネル")
@app_commands.checks.has_permissions(administrator=True)
async def report_setup(
    interaction: discord.Interaction, channel: discord.TextChannel
):
  report_channels[interaction.guild_id] = channel.id
  await interaction.response.send_message(
      f"通報通知チャンネルを {channel.mention} に設定しました！", ephemeral=True
  )


@report_setup.error
async def report_setup_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
  if isinstance(error, app_commands.errors.MissingPermissions):
    if interaction.response.is_done():
      await interaction.followup.send(
          "このコマンドを実行する権限（管理者権限）がありません。", ephemeral=True
      )
    else:
      await interaction.response.send_message(
          "このコマンドを実行する権限（管理者権限）がありません。", ephemeral=True
      )


# 簡易Webサーバーの設定（Renderのポート対策）
routes = web.RouteTableDef()


@routes.get("/")
async def hello(request):
  return web.Response(text="Bot is running!")


async def run_web_server():
  app = web.Application()
  app.add_routes(routes)
  port = int(os.environ.get("PORT", 8080))
  runner = web.AppRunner(app)
  await runner.setup()
  site = web.TCPSite(runner, "0.0.0.0", port)
  await site.start()
  print(f"Web server started on port {port}")


async def main():
  await run_web_server()
  async with bot:
    await bot.start(TOKEN)


if __name__ == "__main__":
  asyncio.run(main())
