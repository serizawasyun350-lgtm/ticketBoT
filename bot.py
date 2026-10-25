import asyncio
import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, Modal, Select, TextInput, View
from aiohttp import web

# 環境変数からトークンを取得
TOKEN = os.getenv("TOKEN")

# Botのインテント設定
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

# サーバーごとの通報チャンネルIDを保存する辞書
report_channels = {}


# 1. 通報フォーム（モーダル）
class DetailedReportModal(Modal):

  def __init__(self, category: str):
    super().__init__(title=f"通報フォーム ({category})")
    self.category = category

    self.target_user = TextInput(
        label="通報したい人 (ユーザー名やID)",
        style=discord.TextStyle.short,
        placeholder="例: @yamada または 123456789 (不明なら「なし」)",
        required=True,
        max_length=100,
    )
    self.add_item(self.target_user)

    self.reason = TextInput(
        label="詳しい状況や理由",
        style=discord.TextStyle.paragraph,
        placeholder="いつ、どこで、どのような行為があったか詳しく記入してください...",
        required=True,
        max_length=1000,
    )
    self.add_item(self.reason)

  async def on_submit(self, interaction: discord.Interaction):
    guild = interaction.guild
    channel_id = report_channels.get(guild.id)
    report_channel = guild.get_channel(channel_id) if channel_id else None

    embed = discord.Embed(
        title="🚨 新しい通報がありました",
        color=discord.Color.orange(),
    )
    embed.add_field(
        name="通報カテゴリ", value=self.category, inline=False
    )
    embed.add_field(
        name="通報者",
        value=f"{interaction.user} (ID: {interaction.user.id})",
        inline=False,
    )
    embed.add_field(
        name="通報したい人", value=self.target_user.value, inline=False
    )
    embed.add_field(
        name="対象チャンネル", value=interaction.channel.mention, inline=False
    )
    embed.add_field(
        name="詳細な理由", value=self.reason.value, inline=False
    )
    embed.set_footer(
        text=f"サーバー名: {guild.name}",
        icon_url=guild.icon.url if guild.icon else None,
    )

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


# 2. カテゴリー選択セレクトメニュー
class ReportSelect(Select):

  def __init__(self):
    options = [
        discord.SelectOption(
            label="荒らし行為",
            description="サーバーやチャンネルを荒らす行為",
            emoji="💥",
        ),
        discord.SelectOption(
            label="スパム・宣伝",
            description="無関係な宣伝やスパムメッセージの送信",
            emoji="📢",
        ),
        discord.SelectOption(
            label="暴言・ハラスメント",
            description="攻撃的な発言や嫌がらせ行為",
            emoji="⚠️",
        ),
        discord.SelectOption(
            label="迷惑行為",
            description="ルール違反や周りのユーザーへの迷惑行為",
            emoji="🛑",
        ),
        discord.SelectOption(
            label="その他",
            description="上記に当てはまらないその他の問題",
            emoji="📌",
        ),
    ]
    super().__init__(
        placeholder="通報のカテゴリーを選択してください...",
        min_values=1,
        max_values=1,
        options=options,
    )

  async def callback(self, interaction: discord.Interaction):
    selected_category = self.values[0]
    await interaction.response.send_modal(
        DetailedReportModal(category=selected_category)
    )


class ReportSelectView(View):

  def __init__(self):
    super().__init__(timeout=60)
    self.add_item(ReportSelect())


# 3. チケット確認用ビュー
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


# 4. チケットコントロールパネル
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
    await interaction.response.send_message(
        "通報する内容のカテゴリーを選んでください：",
        view=ReportSelectView(),
        ephemeral=True,
    )


# 5. チケット作成用パネル
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


# /ticket_panel コマンド
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


# /report_setup コマンド
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


# 簡易Webサーバーの設定（Render対策）
routes = web.RouteTableDef()


@routes.get("/")
async def hello(request):
  return web.Response(text="Bot is running!")


async def run_web_server():
  app = web.Application()
  app.add_routes(routes)
  port = int(os.environ.get("PORT", 10000))
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
