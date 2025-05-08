# utils/button_utils.py

import logging
from typing import List, Tuple # Use List and Tuple for type hinting clarity
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

def build_single_button_keyboard(
    button_text: str,
    callback_data: str
) -> InlineKeyboardMarkup:
    """
    Builds and returns an InlineKeyboardMarkup with a single button.

    Args:
        button_text: The text displayed on the button.
        callback_data: The callback data associated with the button press.

    Returns:
        An InlineKeyboardMarkup object containing the single button.
    """
    if not button_text or not callback_data:
        logger.warning("build_single_button_keyboard called with empty text or callback_data.")
        # Return an empty keyboard or raise error, depending on desired strictness
        return InlineKeyboardMarkup([]) # Return empty keyboard to avoid error

    keyboard = [[InlineKeyboardButton(text=button_text, callback_data=callback_data)]]
    return InlineKeyboardMarkup(keyboard)


def build_dual_button_keyboard(
    button1_text: str, button1_callback: str,
    button2_text: str, button2_callback: str,
    layout: str = 'horizontal' # Added layout option: 'horizontal' or 'vertical'
) -> InlineKeyboardMarkup:
    """
    Builds and returns an InlineKeyboardMarkup with two buttons.

    Args:
        button1_text: Text for the first button.
        button1_callback: Callback data for the first button.
        button2_text: Text for the second button.
        button2_callback: Callback data for the second button.
        layout: 'horizontal' (default) for buttons side-by-side,
                'vertical' for buttons on separate rows.

    Returns:
        An InlineKeyboardMarkup object containing the two buttons.
    """
    if not all([button1_text, button1_callback, button2_text, button2_callback]):
        logger.warning("build_dual_button_keyboard called with empty text or callback_data for one or both buttons.")
        return InlineKeyboardMarkup([]) # Return empty

    button1 = InlineKeyboardButton(text=button1_text, callback_data=button1_callback)
    button2 = InlineKeyboardButton(text=button2_text, callback_data=button2_callback)

    if layout == 'vertical':
        keyboard = [[button1], [button2]] # Buttons on separate rows
    else: # Default to horizontal
        keyboard = [[button1, button2]] # Buttons on the same row

    return InlineKeyboardMarkup(keyboard)


def build_yes_no_buttons(
    yes_callback: str,
    no_callback: str,
    yes_text: str = "✅ Yes", # Keep defaults, but allow override via args if ever needed
    no_text: str = "❌ No"
) -> InlineKeyboardMarkup:
    """
    Builds and returns an InlineKeyboardMarkup with standard Yes/No buttons.

    Args:
        yes_callback: Callback data for the 'Yes' button.
        no_callback: Callback data for the 'No' button.
        yes_text: Text for the 'Yes' button (defaults to "✅ Yes").
        no_text: Text for the 'No' button (defaults to "❌ No").

    Returns:
        An InlineKeyboardMarkup object containing the Yes/No buttons side-by-side.
    """
    if not yes_callback or not no_callback:
        logger.warning("build_yes_no_buttons called with empty callback_data.")
        return InlineKeyboardMarkup([])

    # Using build_dual_button_keyboard for consistency and layout handling
    return build_dual_button_keyboard(
        button1_text=yes_text, button1_callback=yes_callback,
        button2_text=no_text, button2_callback=no_callback,
        layout='horizontal' # Default Yes/No usually looks better horizontally
    )


def build_dynamic_choice_buttons(
    choices: List[Tuple[str, str]] # Use List and Tuple for clarity
) -> InlineKeyboardMarkup:
    """
    Builds an InlineKeyboardMarkup with multiple buttons, each on its own row.

    Args:
        choices: A list of tuples, where each tuple is (button_text: str, callback_data: str).

    Returns:
        An InlineKeyboardMarkup object with buttons arranged vertically,
        or an empty one if input is invalid.
    """
    keyboard: List[List[InlineKeyboardButton]] = [] # Explicit typing

    # ✅ Item 3 (from review): Added basic validation for robustness
    if not isinstance(choices, list):
        logger.error(f"build_dynamic_choice_buttons received non-list input: {type(choices)}. Returning empty keyboard.")
        return InlineKeyboardMarkup([])

    if not choices:
        logger.warning("build_dynamic_choice_buttons called with an empty list of choices.")
        # Return empty keyboard, which Telegram handles gracefully (no buttons shown)
        return InlineKeyboardMarkup([])

    for item in choices:
        if not (isinstance(item, tuple) and len(item) == 2 and
                isinstance(item[0], str) and isinstance(item[1], str)):
            logger.warning(f"Invalid item format in choices list for build_dynamic_choice_buttons: {item}. Skipping this item.")
            continue # Skip invalid items
        if not item[0] or not item[1]: # Check for empty text or callback
             logger.warning(f"Empty text or callback_data found in choice: {item}. Skipping.")
             continue

        button_text, callback_data = item
        keyboard.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])

    if not keyboard: # If all items were invalid
        logger.warning("build_dynamic_choice_buttons resulted in an empty keyboard after filtering invalid choices.")

    return InlineKeyboardMarkup(keyboard)

# Example Usage (can be removed or kept for testing/documentation):
if __name__ == "__main__":
    # Demonstrates how to use the functions
    single_kb = build_single_button_keyboard("Click Me", "click_me_callback")
    dual_horizontal_kb = build_dual_button_keyboard("Option A", "cb_a", "Option B", "cb_b")
    dual_vertical_kb = build_dual_button_keyboard("Choice X", "cb_x", "Choice Y", "cb_y", layout='vertical')
    yes_no_kb = build_yes_no_buttons("confirm_action", "cancel_action")
    dynamic_kb = build_dynamic_choice_buttons([
        ("View Details", "details_1"),
        ("Next Page", "page_2"),
        ("Go Back", "back_0")
    ])
    invalid_dynamic = build_dynamic_choice_buttons([("Valid", "ok"), "invalid_item", ("", "empty_text")])

    print("Single Button:\n", single_kb)
    print("\nDual Horizontal:\n", dual_horizontal_kb)
    print("\nDual Vertical:\n", dual_vertical_kb)
    print("\nYes/No Buttons:\n", yes_no_kb)
    print("\nDynamic Choices:\n", dynamic_kb)
    print("\nDynamic with Invalid Choices (should be only 'Valid'):\n", invalid_dynamic)
