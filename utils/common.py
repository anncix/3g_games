from models.models import Wallet, WalletLog, InventoryItem, InventoryTab, Notification, PlatformEvent
from sqlalchemy.orm import Session
from datetime import datetime
import json


def change_currency(
    user_id: int,
    currency_type: str,
    amount: int,
    source_type: str,
    source_id: int = None,
    remark: str = "",
    db: Session = None
):
    """
    货币变动通用函数，自动记录流水
    currency_type: g_coin, gold_coin, premium_coin, silver_coin
    """
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    if not wallet:
        wallet = Wallet(user_id=user_id)
        db.add(wallet)
        db.flush()
    
    before = getattr(wallet, currency_type, 0) or 0
    after = before + amount
    if after < 0:
        after = 0
        amount = -before
    
    setattr(wallet, currency_type, after)
    wallet.updated_at = datetime.utcnow()
    
    log = WalletLog(
        user_id=user_id,
        currency_type=currency_type,
        change_amount=amount,
        before_amount=before,
        after_amount=after,
        source_type=source_type,
        source_id=source_id,
        remark=remark
    )
    db.add(log)
    return wallet


def add_item(
    user_id: int,
    module_key: str,
    item_code: str,
    item_name: str,
    quantity: int = 1,
    item_type: str = "item",
    quality: str = "common",
    icon: str = "📦",
    description: str = "",
    extra: dict = None,
    db: Session = None
):
    """添加物品到背包"""
    existing = db.query(InventoryItem).filter(
        InventoryItem.user_id == user_id,
        InventoryItem.module_key == module_key,
        InventoryItem.item_code == item_code
    ).first()
    
    if existing:
        existing.quantity += quantity
    else:
        item = InventoryItem(
            user_id=user_id,
            module_key=module_key,
            item_type=item_type,
            item_code=item_code,
            item_name=item_name,
            quantity=quantity,
            quality=quality,
            icon=icon,
            description=description,
            extra_json=json.dumps(extra) if extra else None
        )
        db.add(item)


def remove_item(
    user_id: int,
    module_key: str,
    item_code: str,
    quantity: int = 1,
    db: Session = None
) -> bool:
    """从背包移除物品，返回是否成功"""
    item = db.query(InventoryItem).filter(
        InventoryItem.user_id == user_id,
        InventoryItem.module_key == module_key,
        InventoryItem.item_code == item_code,
        InventoryItem.quantity >= quantity
    ).first()
    
    if not item:
        return False
    
    item.quantity -= quantity
    if item.quantity <= 0:
        db.delete(item)
    return True


def add_notification(
    user_id: int,
    type: str,
    title: str,
    content: str,
    module_key: str = None,
    db: Session = None
):
    """发送消息通知"""
    msg = Notification(
        user_id=user_id,
        type=type,
        module_key=module_key,
        title=title,
        content=content
    )
    db.add(msg)


def fire_event(
    user_id: int,
    module_key: str,
    event_type: str,
    payload: dict = None,
    db: Session = None
):
    """触发平台事件"""
    event = PlatformEvent(
        user_id=user_id,
        module_key=module_key,
        event_type=event_type,
        event_payload_json=json.dumps(payload) if payload else None,
        processed_status=0
    )
    db.add(event)
