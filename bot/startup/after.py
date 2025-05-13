import socket
import time
from bot.config import _bot, conf
from bot.fun.emojis import enmoji, enmoji2
from bot.fun.quips import enquip, enquip2
from bot.utils.bot_utils import encode_job as ejob
from bot.utils.log_utils import logger
from bot.utils.rss_utils import scheduler
from bot.workers.auto.status import autostat
from bot.workers.auto.transcode import something

from .before import *


async def start_aria2p():
    try:
        aria2 = aria2p.API(
            aria2p.Client(host="http://localhost", port=conf.ARIA2_PORT, secret="")
        )
        aria2.client.get_global_stat()  # Confirm connection

        # Optional: Ensure temp dir exists
        temp_dir = f"{os.getcwd()}/temp"
        os.makedirs(temp_dir, exist_ok=True)

        # Test download
        try:
            download = aria2.add(
                "https://nyaa.si/download/1752639.torrent",
                {"dir": temp_dir}
            )
            await logger(f"Aria2 add success: {download}", important=True)
            await asyncio.sleep(2)
            downloads = aria2.get_downloads()
            await asyncio.sleep(3)
            aria2.remove(downloads, force=True, files=True, clean=True)
        except Exception as e:
            await logger(f"Failed to add/remove torrent: {e}", critical=True)

        _bot.aria2 = aria2
        _bot.sas = True
        await logger(f"Aria2 is set and marked online: {_bot.sas}", important=True)

    except Exception as e:
        _bot.sas = False
        await logger(f"Aria2 connection failed: {e}", critical=True)


def wait_for_port(host, port, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


async def start_rpc():
    os.system(
        f"aria2c --enable-rpc=true --rpc-max-request-size=1024M --rpc-listen-port={conf.ARIA2_PORT} "
        "--seed-time=0 --follow-torrent=mem --summary-interval=0 --daemon=true --allow-overwrite=true "
        "--user-agent=Wget/1.12"
    )

    if not _bot.started:
        if wait_for_port("localhost", conf.ARIA2_PORT):
            await asyncio.sleep(1)  # slight buffer
            await start_aria2p()
            await logger("Aria2 RPC server reachable after start", critical=True)

        else:
            _bot.sas = False
            await logger("Aria2 RPC server not reachable after start", critical=True)

        

async def start_qbit():
    os.system(
        f"qbittorrent-nox -d --webui-port={conf.QBIT_PORT} --profile={os.getcwd()}/qbit"
    )
    os.system(
        f"qbittorrent-nox -d --webui-port={conf.QBIT_PORT2} --profile={os.getcwd()}/qbit  --configuration=1"
    )
    # TO_DO: Properly check if qbit is fully operational.
    _bot.sqs = False


async def onrestart():
    try:
        if sys.argv[1] == "restart":
            msg = "**Restarted!** "
        elif sys.argv[1].startswith("update"):
            s = sys.argv[1].split()[1]
            if s == "True":
                with open(version_file, "r") as file:
                    v = file.read()
                msg = f"**Updated to >>>** `{v}`"
            else:
                msg = "**No major update found!**\n" f"`Bot restarted! {enmoji()}`"
        else:
            return
        chat_id, msg_id = map(int, sys.argv[2].split(":"))
        await pyro.edit_message_text(chat_id, msg_id, msg)
    except Exception:
        await logger(Exception)


async def onstart():
    try:
        await start_rpc()
        for i in conf.OWNER.split():
            try:
                await tele.send_message(int(i), f"**I'm {enquip()} {enmoji()}**")
            except Exception:
                pass
        if conf.LOG_CHANNEL:
            me = await pyro.get_users("me")
            await tele.send_message(
                conf.LOG_CHANNEL, f"**{me.first_name} is {enquip()} {enmoji()}**"
            )
        dev = conf.DEV or conf.LOG_CHANNEL or int(conf.OWNER.split()[0])
        try:
            await tele.send_message(
                dev,
                f"**Aria2:** `{'Online' if _bot.sas else 'Offline/Not_ready'}`"
            )
        except Exception:
            await logger(Exception)
    except BaseException:
        pass


async def on_termination():
    try:
        dead_msg = f"**I'm {enquip2()} {enmoji2()}**"
        if conf.LOG_CHANNEL:
            await tele.send_message((conf.LOG_CHANNEL), dead_msg)
        else:
            for i in conf.OWNER.split():
                try:
                    await tele.send_message(int(i), dead_msg)
                except Exception:
                    pass
    except Exception:
        pass
    # More cleanup code?
    exit(0)

_bot.sas = True

async def on_startup():
    try: 
        asyncio.create_task(start_rpc())
        asyncio.create_task(autostat())
        loop = asyncio.get_running_loop()
        for signame in {"SIGINT", "SIGTERM", "SIGABRT"}:
            loop.add_signal_handler(
                getattr(signal, signame),
                lambda: asyncio.create_task(on_termination()),
            )
        if len(sys.argv) == 3:
            await onrestart()
        else:
            await asyncio.sleep(1)
            await onstart()
        await entime.start()
        ejob.reset(force=True)
        await asyncio.sleep(30)
        asyncio.create_task(something())
    except Exception:
        logger(Exception)
    _bot.started = True
