"""The standard Torznab category catalog (Newznab numbering)."""

from pyjackett.core.category import TorznabCategory

CONSOLE = TorznabCategory(1000, "Console")
CONSOLE_NDS = TorznabCategory(1010, "Console/NDS")
CONSOLE_PSP = TorznabCategory(1020, "Console/PSP")
CONSOLE_WII = TorznabCategory(1030, "Console/Wii")
CONSOLE_X_BOX = TorznabCategory(1040, "Console/XBox")
CONSOLE_X_BOX_360 = TorznabCategory(1050, "Console/XBox 360")
CONSOLE_WIIWARE = TorznabCategory(1060, "Console/Wiiware")
CONSOLE_X_BOX_360DLC = TorznabCategory(1070, "Console/XBox 360 DLC")
CONSOLE_PS3 = TorznabCategory(1080, "Console/PS3")
CONSOLE_OTHER = TorznabCategory(1090, "Console/Other")
CONSOLE_3DS = TorznabCategory(1110, "Console/3DS")
CONSOLE_PS_VITA = TorznabCategory(1120, "Console/PS Vita")
CONSOLE_WII_U = TorznabCategory(1130, "Console/WiiU")
CONSOLE_X_BOX_ONE = TorznabCategory(1140, "Console/XBox One")
CONSOLE_PS4 = TorznabCategory(1180, "Console/PS4")
MOVIES = TorznabCategory(2000, "Movies")
MOVIES_FOREIGN = TorznabCategory(2010, "Movies/Foreign")
MOVIES_OTHER = TorznabCategory(2020, "Movies/Other")
MOVIES_SD = TorznabCategory(2030, "Movies/SD")
MOVIES_HD = TorznabCategory(2040, "Movies/HD")
MOVIES_UHD = TorznabCategory(2045, "Movies/UHD")
MOVIES_BLURAY = TorznabCategory(2050, "Movies/BluRay")
MOVIES_3D = TorznabCategory(2060, "Movies/3D")
MOVIES_DVD = TorznabCategory(2070, "Movies/DVD")
MOVIES_WEBDL = TorznabCategory(2080, "Movies/WEB-DL")
AUDIO = TorznabCategory(3000, "Audio")
AUDIO_MP3 = TorznabCategory(3010, "Audio/MP3")
AUDIO_VIDEO = TorznabCategory(3020, "Audio/Video")
AUDIO_AUDIOBOOK = TorznabCategory(3030, "Audio/Audiobook")
AUDIO_LOSSLESS = TorznabCategory(3040, "Audio/Lossless")
AUDIO_OTHER = TorznabCategory(3050, "Audio/Other")
AUDIO_FOREIGN = TorznabCategory(3060, "Audio/Foreign")
PC = TorznabCategory(4000, "PC")
PC0DAY = TorznabCategory(4010, "PC/0day")
PCISO = TorznabCategory(4020, "PC/ISO")
PC_MAC = TorznabCategory(4030, "PC/Mac")
PC_MOBILE_OTHER = TorznabCategory(4040, "PC/Mobile-Other")
PC_GAMES = TorznabCategory(4050, "PC/Games")
PC_MOBILEI_OS = TorznabCategory(4060, "PC/Mobile-iOS")
PC_MOBILE_ANDROID = TorznabCategory(4070, "PC/Mobile-Android")
TV = TorznabCategory(5000, "TV")
TVWEBDL = TorznabCategory(5010, "TV/WEB-DL")
TV_FOREIGN = TorznabCategory(5020, "TV/Foreign")
TVSD = TorznabCategory(5030, "TV/SD")
TVHD = TorznabCategory(5040, "TV/HD")
TVUHD = TorznabCategory(5045, "TV/UHD")
TV_OTHER = TorznabCategory(5050, "TV/Other")
TV_SPORT = TorznabCategory(5060, "TV/Sport")
TV_ANIME = TorznabCategory(5070, "TV/Anime")
TV_DOCUMENTARY = TorznabCategory(5080, "TV/Documentary")
XXX = TorznabCategory(6000, "XXX")
XXXDVD = TorznabCategory(6010, "XXX/DVD")
XXXWMV = TorznabCategory(6020, "XXX/WMV")
XXX_XVI_D = TorznabCategory(6030, "XXX/XviD")
XX_XX_264 = TorznabCategory(6040, "XXX/x264")
XXXUHD = TorznabCategory(6045, "XXX/UHD")
XXX_PACK = TorznabCategory(6050, "XXX/Pack")
XXX_IMAGE_SET = TorznabCategory(6060, "XXX/ImageSet")
XXX_OTHER = TorznabCategory(6070, "XXX/Other")
XXXSD = TorznabCategory(6080, "XXX/SD")
XXXWEBDL = TorznabCategory(6090, "XXX/WEB-DL")
BOOKS = TorznabCategory(7000, "Books")
BOOKS_MAGS = TorznabCategory(7010, "Books/Mags")
BOOKS_E_BOOK = TorznabCategory(7020, "Books/EBook")
BOOKS_COMICS = TorznabCategory(7030, "Books/Comics")
BOOKS_TECHNICAL = TorznabCategory(7040, "Books/Technical")
BOOKS_OTHER = TorznabCategory(7050, "Books/Other")
BOOKS_FOREIGN = TorznabCategory(7060, "Books/Foreign")
OTHER = TorznabCategory(8000, "Other")
OTHER_MISC = TorznabCategory(8010, "Other/Misc")
OTHER_HASHED = TorznabCategory(8020, "Other/Hashed")

ALL_CATEGORIES = [
    CONSOLE,
    CONSOLE_NDS,
    CONSOLE_PSP,
    CONSOLE_WII,
    CONSOLE_X_BOX,
    CONSOLE_X_BOX_360,
    CONSOLE_WIIWARE,
    CONSOLE_X_BOX_360DLC,
    CONSOLE_PS3,
    CONSOLE_OTHER,
    CONSOLE_3DS,
    CONSOLE_PS_VITA,
    CONSOLE_WII_U,
    CONSOLE_X_BOX_ONE,
    CONSOLE_PS4,
    MOVIES,
    MOVIES_FOREIGN,
    MOVIES_OTHER,
    MOVIES_SD,
    MOVIES_HD,
    MOVIES_UHD,
    MOVIES_BLURAY,
    MOVIES_3D,
    MOVIES_DVD,
    MOVIES_WEBDL,
    AUDIO,
    AUDIO_MP3,
    AUDIO_VIDEO,
    AUDIO_AUDIOBOOK,
    AUDIO_LOSSLESS,
    AUDIO_OTHER,
    AUDIO_FOREIGN,
    PC,
    PC0DAY,
    PCISO,
    PC_MAC,
    PC_MOBILE_OTHER,
    PC_GAMES,
    PC_MOBILEI_OS,
    PC_MOBILE_ANDROID,
    TV,
    TVWEBDL,
    TV_FOREIGN,
    TVSD,
    TVHD,
    TVUHD,
    TV_OTHER,
    TV_SPORT,
    TV_ANIME,
    TV_DOCUMENTARY,
    XXX,
    XXXDVD,
    XXXWMV,
    XXX_XVI_D,
    XX_XX_264,
    XXXUHD,
    XXX_PACK,
    XXX_IMAGE_SET,
    XXX_OTHER,
    XXXSD,
    XXXWEBDL,
    BOOKS,
    BOOKS_MAGS,
    BOOKS_E_BOOK,
    BOOKS_COMICS,
    BOOKS_TECHNICAL,
    BOOKS_OTHER,
    BOOKS_FOREIGN,
    OTHER,
    OTHER_MISC,
    OTHER_HASHED,
]

PARENT_CATEGORIES = [
    CONSOLE,
    MOVIES,
    AUDIO,
    PC,
    TV,
    XXX,
    BOOKS,
    OTHER,
]


def _attach_subcategories() -> None:
    """Wire each child category to its parent (same thousands block)."""
    parents = {parent.id: parent for parent in PARENT_CATEGORIES}
    for category in ALL_CATEGORIES:
        parent = parents.get(category.id // 1000 * 1000)
        if parent is not None and parent is not category:
            parent.subcategories.append(category)


_attach_subcategories()
