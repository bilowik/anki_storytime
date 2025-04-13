import sys

# When bundlings the packages they will be placed here.
sys.path.append("./libs")

from typing import Callable, List, Union
import aqt
from aqt import mw
import aqt.gui_hooks
from aqt.main import AnkiQt
from aqt.overview import Overview, OverviewContent
from anki.collection import Collection

AI_BUTTON_URI = "anki_storytime__ai_button";


def main():
    aqt.gui_hooks.overview_will_render_bottom.append(add_ai_button)
    return 

def get_forgotten_cards(mw: AnkiQt) -> List[str]:
    col: Union[Collection, None] = mw.col 
    if col is None:
        return []
    return list(map(lambda x: col.get_note(x).fields[1], col.find_notes("rated:1:1")))





def add_ai_button(link_handler: Callable[[str], bool], links: List[List[str]]) -> Callable[[str], bool]:
    d = mw

    links.append(['A', AI_BUTTON_URI, "AI Button"])
    def ai_button_link_handler(url: str):
        if url == AI_BUTTON_URI:
            # TODO: Do something here?
            print(AI_BUTTON_URI + '_button_test')
            print(get_forgotten_cards(mw))
        return link_handler(url)

    return ai_button_link_handler






main()
