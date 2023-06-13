import logging
import os

import httpx
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from tenacity import retry, wait_random_exponential, stop_after_attempt

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

api_key = os.environ.get("API_KEY")
library_id = os.environ.get("LIBRARY_ID")
model = os.environ.get("MODEL", "gpt-3.5-turbo")
bot_token = os.environ.get("BOT_TOKEN")
bot_name = os.environ.get("BOT_NAME", "")
allow_chat_id = os.environ.get("ALLOW_CHAT_ID", "")
if allow_chat_id:
    allow_chat_id = allow_chat_id.split(',')
    for i in range(len(allow_chat_id)):
        allow_chat_id[i] = allow_chat_id[i].strip()


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(3))
def ask(query: str):
    r = httpx.post(
        'https://api.aiproxy.io/api/library/ask',
        headers={
            "Authorization": f"Bearer {api_key}"
        },
        json={
            "query": query,
            "model": model,
            "libraryId": library_id,
            "stream": False,
        },
        timeout=180
    )
    r.raise_for_status()
    j = r.json()
    answer = str(j.get('answer'))
    documents = j.get('documents')
    if documents:
        refs = ''
        for i, doc in enumerate(documents):
            no = i + 1
            refs += f'\n<a href="{doc.get("url")}">[{no}] {doc.get("title")}</a>'
            if answer.find(f'[{no}]') == -1:
                continue
            answer = answer.replace(f'[{no}]', f'<a href="{doc.get("url")}">[{no}]</a>')
        answer += '\n\n相关文档：' + refs

    logger.info(f"ask complete totalElapsedMs: {j.get('totalElapsedMs')}")
    return answer


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message.text
    query = message.replace("/help", "").strip()
    logger.info(f"Query: {query}")
    answer = ask(query)
    await update.message.reply_html(answer, disable_web_page_preview=True)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    if allow_chat_id and str(chat_id) not in allow_chat_id:
        await update.message.reply_text("很抱歉，你没有权限使用这个机器人。")
        return
    message = update.message.text
    if f"@{bot_name}" in message:
        query = message.replace(f"@{bot_name}", "").strip()
        logger.info(f"Query: {query}")
        answer = ask(query)
        await update.message.reply_html(answer, disable_web_page_preview=True)


def main() -> None:
    application = Application.builder().token(bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    application.run_polling()


if __name__ == "__main__":
    main()
