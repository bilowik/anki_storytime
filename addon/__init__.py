import sys
import os

# When bundlings the packages they will be placed here.
sys.path.insert(1, os.path.join(os.path.dirname((os.path.abspath(__file__))), 'libs'))

from typing import Callable, List, Union, Dict
import aqt
from aqt import mw
import aqt.gui_hooks
from aqt.main import AnkiQt
from aqt.overview import Overview, OverviewContent
from aqt.utils import showInfo
from aqt.operations import QueryOp
from anki.collection import Collection
from openai import OpenAI
import openai

AI_BUTTON_URI = "anki_storytime__ai_button";

DEFAULT_PROMPT_BASE = """Create a story in Japanese with the following vocabulary words that will be listed individually on separate lines starting after the first empty newline. The story can be about anything in particular, but should provide a reasonable amount of context, not every sentence has to have one of the vocabulary words in it, but you must utilize every single vocabulary word provided. The length of the story can be as long as needed to encompass all of the vocabulary words. Do not respond with any other text other than the story. Following are the vocabulary words:

"""
MAX_VOCAB_WORDS = 100
    

CONFIG: Dict = mw.addonManager.getConfig(__name__) or {}

def main():
    aqt.gui_hooks.overview_will_render_bottom.append(add_ai_button)
    return 

def get_forgotten_vocab(mw: AnkiQt) -> List[str]:
    col: Union[Collection, None] = mw.col 
    if col is None:
        return []
    return list(map(lambda x: col.get_note(x).fields[1], col.find_notes("rated:1:1")))



def prepare_story_on_success(story: str) -> None:
    showInfo("Story from today's mistakes\n\n" + story, title="AI Storytime")


def prepare_story() -> str:
    vocab: List[str]= get_forgotten_vocab(mw)
    if len(vocab) > 0:
        if CONFIG.get("MOCK_API_RESPONSE") is True:
            # So we don't run up the bill while testing :) 
            return "ここに何かがありますよ"
        api_key = CONFIG.get('OpenAI API Key', '')
        if api_key:
            client = OpenAI(api_key=CONFIG.get('OpenAI API Key', ''))
            prompt: str = DEFAULT_PROMPT_BASE + "\n".join(vocab)
            try:
                return client.responses.create(input=prompt, model="gpt-4o").output_text
            except openai.RateLimitError:
                raise Exception("The account associated with the provided API key may have run out of credits")
            except openai.BadRequestError as e:
                raise Exception(f"Failed to retrieve response from OpenAI: {e}")
        else:
            raise Exception("No API Key set for OpenAI, please add this key in this addon's config")
    else:
        raise Exception("No notes found matching your query")


def add_ai_button(link_handler: Callable[[str], bool], links: List[List[str]]) -> Callable[[str], bool]:
    links.append(['A', AI_BUTTON_URI, "AI Button"])
    def ai_button_link_handler(url: str):
        handler = link_handler(url)
        if url == AI_BUTTON_URI:
            op = QueryOp(
                    parent=mw,
                    op=lambda col: prepare_story(),
                    success=prepare_story_on_success,
            )

            op.with_progress().run_in_background()


        return handler

    return ai_button_link_handler


main()
