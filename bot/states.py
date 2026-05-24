from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    choosing_delivery_type = State()
    entering_address = State()
    choosing_date = State()        # Calendar date picker
    entering_phone = State()
    confirming_order = State()     # Review before submitting


class CartStates(StatesGroup):
    entering_promo = State()
    waiting_for_quantity = State()


class AdminStates(StatesGroup):
    changing_status = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_category = State()
    waiting_for_image = State()
    waiting_for_edit_value = State()
    browsing_orders = State()      # Paginating through all orders


class SupportStates(StatesGroup):
    waiting_for_message = State()  # User typing a support message