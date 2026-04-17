from __future__ import annotations

import asyncio
import signal
import sys

import aiohttp
from loguru import logger

from app.bot.bot import create_bot, create_dispatcher, set_main_menu
from app.config import get_settings
from app.db.engine import engine, session_factory
from app.db.repositories.headline import SourceRepository
from app.services.notifier import NotifierService
from app.services.scraper import ScraperService
from app.sources.registry import build_sources_registry


async def seed_sources() -> None:
    """Seed default sources, update existing ones and deactivate legacy unsupported ones."""
    async with session_factory() as session:
        repository = SourceRepository(session)
        affected = await repository.seed_defaults()
        logger.info("Seed sources completed. Affected rows: {}", affected)


def configure_logging() -> None:
    """Configure loguru logging."""
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        enqueue=True,
        backtrace=False,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    )


async def _run_component(name: str, coro) -> None:
    """Run component and log crashes explicitly."""
    logger.info("{} started.", name)
    try:
        await coro
    except asyncio.CancelledError:
        logger.info("{} cancelled.", name)
        raise
    except Exception:
        logger.exception("{} crashed.", name)
        raise


async def run_components(
    scraper: ScraperService,
    notifier: NotifierService,
    dispatcher,
    bot,
) -> None:
    """Run application components concurrently and fail fast on errors."""
    tasks = {
        "scraper": asyncio.create_task(
            _run_component("Scraper service", scraper.run())
        ),
        "notifier": asyncio.create_task(
            _run_component("Notifier service", notifier.run())
        ),
        "polling": asyncio.create_task(
            _run_component(
                "Bot polling",
                dispatcher.start_polling(
                    bot,
                    allowed_updates=dispatcher.resolve_used_update_types(),
                    handle_signals=False,
                    close_bot_session=False,
                ),
            )
        ),
    }

    done, pending = await asyncio.wait(
        tasks.values(),
        return_when=asyncio.FIRST_EXCEPTION,
    )

    for task in pending:
        task.cancel()

    await asyncio.gather(*pending, return_exceptions=True)

    for name, task in tasks.items():
        if task in done:
            exc = task.exception()
            if exc is not None:
                logger.error("Component '{}' failed with exception.", name)
                raise exc


async def main() -> None:
    """Application entrypoint."""
    configure_logging()
    settings = get_settings()

    http_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=settings.http_timeout_seconds)
    )

    bot = create_bot(settings)
    dispatcher = create_dispatcher(session_factory)

    await seed_sources()

    await bot.delete_webhook(drop_pending_updates=True)
    await set_main_menu(bot)

    sources_registry = build_sources_registry(
        session=http_session,
        settings=settings,
        timeout_seconds=settings.http_timeout_seconds,
    )

    scraper = ScraperService(
        session_factory=session_factory,
        sources_registry=sources_registry,
        interval_seconds=settings.scraper_interval_seconds,
    )
    notifier = NotifierService(
        bot=bot,
        session_factory=session_factory,
        interval_seconds=settings.notifier_interval_seconds,
    )

    shutdown_event = asyncio.Event()

    def _handle_shutdown_signal() -> None:
        logger.info("Shutdown signal received.")
        scraper.stop()
        notifier.stop()
        dispatcher.stop_polling()
        shutdown_event.set()

    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_shutdown_signal)
        except NotImplementedError:
            logger.warning("Signal handlers are not supported on this platform.")
            break

    runner_task = asyncio.create_task(
        run_components(
            scraper=scraper,
            notifier=notifier,
            dispatcher=dispatcher,
            bot=bot,
        )
    )
    shutdown_task = asyncio.create_task(shutdown_event.wait())

    try:
        done, pending = await asyncio.wait(
            {runner_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if runner_task in done:
            await runner_task
    finally:
        scraper.stop()
        notifier.stop()
        dispatcher.stop_polling()

        shutdown_task.cancel()
        await asyncio.gather(shutdown_task, return_exceptions=True)

        await http_session.close()
        await bot.session.close()
        await engine.dispose()

        if not runner_task.done():
            runner_task.cancel()
            try:
                await runner_task
            except asyncio.CancelledError:
                logger.info("Runner task cancelled during shutdown.")


if __name__ == "__main__":
    asyncio.run(main())