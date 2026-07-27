"""Публикация в Telegram через aiogram и Telethon (userbot)."""

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile
from loguru import logger

from app.core.config import get_settings
from app.domain.enums import ContentMode
from app.domain.publish import PublishPermanentError
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.publishers.base import BasePublisher
from app.infrastructure.publishers.telegram_user_publisher import (
    TelegramUserPublisher,
    TelethonNotReadyError,
    TelethonPublishError,
)
from app.infrastructure.publishers.telegraph_publisher import TelegraphPublisher
from app.infrastructure.stats.telethon_lock import TelethonSessionBusyError
from app.utils.telegram_channels import is_telegram_long_form_channel
from app.utils.text_format import (
    TELEGRAM_BOT_CAPTION_MAX,
    TELEGRAM_MESSAGE_MAX,
    TELEGRAM_USER_CAPTION_MAX,
    append_cross_promote_footer,
    append_post_footer,
    build_article_read_more_html,
    build_article_telegram_text,
    cross_promote_footer_length,
    repair_telegram_html,
    to_telegram_api_html,
)


class TelegramPublisher(BasePublisher):
    """Публикует в Telegram-канал."""

    def __init__(self) -> None:
        self._user_publisher = TelegramUserPublisher()

    async def publish(
        self,
        post: ProcessedPost,
        channel: Channel,
        image_bytes: bytes | None,
        video_bytes: bytes | None = None,
    ) -> str:
        """Отправляет сообщение в канал.

        Args:
            post: пост.
            channel: канал (platform_id = @channel или -100...).
            image_bytes: картинка.

        Returns:
            str: message_id основного сообщения (текст или фото).

        Raises:
            RuntimeError: при ошибке.
        """
        if post.content_mode == ContentMode.ARTICLE.value:
            return await self._publish_article(post, channel, image_bytes, video_bytes)

        settings = get_settings()
        if not settings.telegram_bot_token:
            msg = "TELEGRAM_BOT_TOKEN not configured"
            raise RuntimeError(msg)

        bot = Bot(token=settings.telegram_bot_token)
        chat_id = channel.platform_id
        text = repair_telegram_html(
            to_telegram_api_html(post.rewritten_text)
        )
        text = append_cross_promote_footer(
            text,
            channel.cross_promote_url,
            channel.cross_promote_label,
            promote_emoji_id=channel.cross_promote_emoji_id,
        )
        text = append_post_footer(text, channel.post_footer)[:TELEGRAM_MESSAGE_MAX]

        try:
            message_id = await self._send_content(
                bot,
                chat_id,
                text,
                image_bytes,
                video_bytes=video_bytes,
                channel=channel,
                prefer_userbot=bool(image_bytes and not video_bytes),
            )
            logger.info(
                "Telegram published",
                channel_id=channel.id,
                message_id=message_id,
            )
            return message_id
        except PublishPermanentError:
            raise
        except Exception as exc:
            msg = f"Telegram publish failed: {exc}"
            raise RuntimeError(msg) from exc
        finally:
            await bot.session.close()

    async def _publish_article(
        self,
        post: ProcessedPost,
        channel: Channel,
        image_bytes: bytes | None,
        video_bytes: bytes | None = None,
    ) -> str:
        """Публикует статью: полный текст в TG (long-form) или анонс + Telegraph.

        Args:
            post: пост в режиме article.
            channel: канал.
            image_bytes: обложка.

        Returns:
            str: message_id основного сообщения.

        Raises:
            RuntimeError: при ошибке API.
        """
        settings = get_settings()
        if not settings.telegram_bot_token:
            msg = "TELEGRAM_BOT_TOKEN not configured"
            raise RuntimeError(msg)

        if not post.article_body and not post.rewritten_text:
            msg = "Article body is empty"
            raise RuntimeError(msg)

        if is_telegram_long_form_channel(channel):
            return await self._publish_long_form_article(
                post, channel, image_bytes, video_bytes
            )

        return await self._publish_telegraph_article(post, channel, image_bytes, video_bytes)

    async def _publish_long_form_article(
        self,
        post: ProcessedPost,
        channel: Channel,
        image_bytes: bytes | None,
        video_bytes: bytes | None = None,
    ) -> str:
        """Публикует статью целиком в Telegram без Telegraph (Github, Параграф)."""
        # Резервируем место под футер, чтобы кросс-промо ссылка не обрезалась.
        footer_reserve = cross_promote_footer_length(
            channel.cross_promote_url,
            channel.cross_promote_label,
            promote_emoji_id=channel.cross_promote_emoji_id,
        )
        text = build_article_telegram_text(
            article_title=post.article_title,
            teaser_html=post.rewritten_text,
            body_html=post.article_body,
            max_length=TELEGRAM_USER_CAPTION_MAX - footer_reserve,
        )
        text = append_cross_promote_footer(
            text,
            channel.cross_promote_url,
            channel.cross_promote_label,
            promote_emoji_id=channel.cross_promote_emoji_id,
        )
        text = append_post_footer(text, channel.post_footer)

        settings = get_settings()
        bot = Bot(token=settings.telegram_bot_token)
        chat_id = channel.platform_id
        try:
            message_id = await self._send_content(
                bot,
                chat_id,
                text,
                image_bytes,
                video_bytes=video_bytes,
                channel=channel,
                prefer_userbot=bool(image_bytes and not video_bytes),
            )
            logger.info(
                "Telegram long-form article published",
                channel_id=channel.id,
                message_id=message_id,
                text_length=len(text),
            )
            return message_id
        except PublishPermanentError:
            raise
        except Exception as exc:
            msg = f"Telegram publish failed: {exc}"
            raise RuntimeError(msg) from exc
        finally:
            await bot.session.close()

    async def _publish_telegraph_article(
        self,
        post: ProcessedPost,
        channel: Channel,
        image_bytes: bytes | None,
        video_bytes: bytes | None = None,
    ) -> str:
        """Публикует анонс статьи со ссылкой на Telegraph (прочие article-каналы)."""
        if not post.article_body:
            msg = "Article body is empty"
            raise RuntimeError(msg)

        telegraph = TelegraphPublisher()
        telegraph_url = post.telegraph_url
        title = (post.article_title or "Статья").strip()
        if not telegraph_url:
            telegraph_url = await telegraph.create_page(
                title,
                post.article_body,
                author_name=channel.name,
            )
            post.telegraph_url = telegraph_url
        else:
            await telegraph.set_author_name(
                telegraph_url,
                channel.name,
                title=title,
            )

        teaser = repair_telegram_html(to_telegram_api_html(post.rewritten_text.strip()))
        link = build_article_read_more_html(
            telegraph_url,
            channel_name=channel.name,
            article_title=title,
            article_body=post.article_body or "",
            post_id=post.id,
        )
        caption = append_cross_promote_footer(
            f"{teaser}\n\n{link}".strip(),
            channel.cross_promote_url,
            channel.cross_promote_label,
            promote_emoji_id=channel.cross_promote_emoji_id,
        )
        caption = append_post_footer(caption, channel.post_footer)

        settings = get_settings()
        bot = Bot(token=settings.telegram_bot_token)
        chat_id = channel.platform_id
        try:
            message_id = await self._send_content(
                bot,
                chat_id,
                caption,
                image_bytes,
                video_bytes=video_bytes,
                channel=channel,
                prefer_userbot=bool(image_bytes and not video_bytes),
            )
            logger.info(
                "Telegram article teaser published",
                channel_id=channel.id,
                message_id=message_id,
                telegraph_url=telegraph_url,
            )
            return message_id
        except PublishPermanentError:
            raise
        except Exception as exc:
            msg = f"Telegram publish failed: {exc}"
            raise RuntimeError(msg) from exc
        finally:
            await bot.session.close()

    async def _send_content(
        self,
        bot: Bot,
        chat_id: str,
        text: str,
        image_bytes: bytes | None,
        video_bytes: bytes | None = None,
        *,
        channel: Channel | None = None,
        prefer_userbot: bool = False,
    ) -> str:
        """Отправляет фото и/или текст; при необходимости через userbot.

        Args:
            bot: экземпляр aiogram Bot.
            chat_id: ID чата.
            text: HTML-текст.
            image_bytes: байты изображения.
            channel: канал (для userbot).
            prefer_userbot: предпочитать MTProto для поста с медиа (один пузырь до 4096).

        Returns:
            str: message_id основного сообщения.
        """
        use_userbot = (
            channel is not None
            and image_bytes
            and not video_bytes
            and self._user_publisher.is_configured()
            and (
                prefer_userbot
                or len(text) > TELEGRAM_BOT_CAPTION_MAX
            )
        )
        if use_userbot:
            try:
                return await self._user_publisher.publish(channel, text, image_bytes)
            except TelethonNotReadyError as exc:
                logger.warning(
                    "Telethon publish skipped, falling back to bot API",
                    channel_id=channel.id if channel else None,
                    error=str(exc),
                )
            except TelethonSessionBusyError as exc:
                logger.warning(
                    "Telethon session busy, falling back to bot API",
                    channel_id=channel.id if channel else None,
                    error=str(exc),
                )
            except TelethonPublishError as exc:
                logger.warning(
                    "Telethon publish failed, falling back to bot API",
                    channel_id=channel.id if channel else None,
                    error=str(exc),
                )

        return await self._send_via_bot(bot, chat_id, text, image_bytes, video_bytes)

    @staticmethod
    def _map_telegram_error(exc: Exception) -> Exception:
        """Преобразует ошибки Telegram API в типы для политики retry."""
        if isinstance(exc, TelegramBadRequest):
            message = str(exc).lower()
            if "parse entities" in message or "can't parse" in message:
                return PublishPermanentError(f"Telegram publish failed: {exc}")
        return exc

    @staticmethod
    async def _send_via_bot(
        bot: Bot,
        chat_id: str,
        text: str,
        image_bytes: bytes | None,
        video_bytes: bytes | None = None,
    ) -> str:
        """Отправляет фото и/или текст через Bot API."""
        try:
            if video_bytes:
                from app.infrastructure.media.gifski_converter import is_gif_bytes

                as_gif = is_gif_bytes(video_bytes)
                media = BufferedInputFile(
                    video_bytes,
                    filename="postcard.gif" if as_gif else "postcard.mp4",
                )
                send_media = bot.send_animation if as_gif else bot.send_video
                media_kw = "animation" if as_gif else "video"
                if len(text) <= TELEGRAM_BOT_CAPTION_MAX:
                    result = await send_media(
                        chat_id=chat_id,
                        **{media_kw: media},
                        caption=text,
                        parse_mode=ParseMode.HTML,
                    )
                    return str(result.message_id)
                media_msg = await send_media(chat_id=chat_id, **{media_kw: media})
                try:
                    text_msg = await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        reply_to_message_id=media_msg.message_id,
                    )
                except Exception as exc:
                    try:
                        await bot.delete_message(
                            chat_id=chat_id,
                            message_id=media_msg.message_id,
                        )
                    except Exception as rollback_exc:
                        logger.warning(
                            "Failed to delete orphan Telegram animation/video",
                            error=str(rollback_exc),
                        )
                    raise TelegramPublisher._map_telegram_error(exc) from exc
                logger.info(
                    "Telegram split publish: animation/video + text reply",
                    text_length=len(text),
                    as_gif=as_gif,
                )
                return str(text_msg.message_id)

            if image_bytes:
                photo = BufferedInputFile(image_bytes, filename="post.jpg")
                if len(text) <= TELEGRAM_BOT_CAPTION_MAX:
                    result = await bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=text,
                        parse_mode=ParseMode.HTML,
                    )
                    return str(result.message_id)
                photo_msg = await bot.send_photo(chat_id=chat_id, photo=photo)
                try:
                    text_msg = await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        reply_to_message_id=photo_msg.message_id,
                    )
                except Exception as exc:
                    try:
                        await bot.delete_message(
                            chat_id=chat_id,
                            message_id=photo_msg.message_id,
                        )
                    except Exception as rollback_exc:
                        logger.warning(
                            "Failed to delete orphan Telegram photo",
                            error=str(rollback_exc),
                        )
                    raise TelegramPublisher._map_telegram_error(exc) from exc
                logger.info(
                    "Telegram split publish: photo + text reply",
                    text_length=len(text),
                )
                return str(text_msg.message_id)

            result = await bot.send_message(
                chat_id=chat_id,
                text=text[:TELEGRAM_MESSAGE_MAX],
                parse_mode=ParseMode.HTML,
            )
            return str(result.message_id)
        except Exception as exc:
            raise TelegramPublisher._map_telegram_error(exc) from exc
