import os
import discord
from discord.ext import commands
from discord.ui import Button, View

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)


# チケットを閉じる際の確認用ビュー
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
    # 5秒後にチャンネルを削除
    import asyncio

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


# チケット内部に表示されるコントロールパネル（閉じるボタンなど）
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
    # 本当に閉じますか？という確認メッセージを送信
    await interaction.response.send_message(
        "本当にこのチケットを閉じますか？",
        view=CloseConfirmView(),
        ephemeral=True,
    )


# 最初のエントリーパネル（チケット作成ボタン）
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

    # 既に同じ名前のチャンネルがないか確認
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

    # 権限の設定（本人とBotのみ閲覧可能）
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

    # チャンネルを作成
    ticket_channel = await guild.create_text_channel(
        name=channel_name, overwrites=overwrites
    )

    # 作成されたチャンネルに案内と閉じるボタンを送信
    await ticket_channel.send(
        f"{interaction.user.mention} さん、ようこそ！\nスタッフが対応するまでしばらくお待ちください。",
        view=TicketControlView(),
    )

    # 押した本人にだけこっそり通知
    await interaction.response.send_message(
        f"チケットを作成しました！ 👉 {ticket_channel.mention}", ephemeral=True
    )


@bot.event
async def on_ready():
  print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
  # 永続ボタンのためにViewを登録
  bot.add_view(TicketView())
  bot.add_view(TicketControlView())


# /ticket_panel コマンドの定義
@bot.command(name="ticket_panel")
@commands.has_permissions(administrator=True)
async def ticket_panel(ctx):
  """チケット作成パネルを送信するコマンド"""
  embed = discord.Embed(
      title="🎫 お問い合わせチケット",
      description=(
          "下のボタンを押すと、あなた専用のプライベートチャンネルが作成されます。\n"
          "何かご用件がある場合はボタンを押してください。"
      ),
      color=discord.Color.blue(),
  )
  await ctx.send(embed=embed, view=TicketView())


# 権限がない場合のエラー処理
@ticket_panel.error
async def ticket_panel_error(ctx, error):
  if isinstance(error, commands.MissingPermissions):
    await ctx.send(
        "このコマンドを実行する権限（管理者権限）がありません。", ephemeral=True
    )


# Botの起動
bot.run(TOKEN)
