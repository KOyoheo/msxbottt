import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class Database:
    def __init__(self):
        self.users_file = "users.json"
        self.orders_file = "orders.json"
        self.users = self.load_users()
        self.orders = self.load_orders()
    
    def load_users(self) -> Dict:
        """Завантаження користувачів з файлу"""
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_users(self):
        """Збереження користувачів у файл"""
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)
    
    def load_orders(self) -> Dict:
        """Завантаження замовлень з файлу"""
        if os.path.exists(self.orders_file):
            try:
                with open(self.orders_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_orders(self):
        """Збереження замовлень у файл"""
        with open(self.orders_file, 'w', encoding='utf-8') as f:
            json.dump(self.orders, f, ensure_ascii=False, indent=2)
    
    def add_user(self, user_id: int, username: str, first_name: str):
        """Додавання нового користувача"""
        if str(user_id) not in self.users:
            self.users[str(user_id)] = {
                'username': username,
                'first_name': first_name,
                'joined_date': datetime.now().isoformat(),
                'orders': []
            }
            self.save_users()
    
    def add_order(self, user_id: int, order_data: Dict) -> str:
        """Додавання нового замовлення"""
        order_id = f"ORDER_{len(self.orders) + 1:06d}"
        
        # Отримуємо поточну інформацію про користувача
        user_info = self.users.get(str(user_id), {})
        
        order = {
            'id': order_id,
            'user_id': user_id,
            'username': order_data.get('username') or user_info.get('username', 'Невідомий'),
            'first_name': order_data.get('first_name') or user_info.get('first_name', 'Невідомий'),
            'order_data': order_data,
            'status': 'Новий',
            'created_date': datetime.now().isoformat()
        }
        
        self.orders[order_id] = order
        
        # Додаємо замовлення до користувача
        if str(user_id) in self.users:
            self.users[str(user_id)]['orders'].append(order_id)
        
        self.save_orders()
        self.save_users()
        
        return order_id
    
    def get_user_orders(self, user_id: int) -> List[Dict]:
        """Отримання замовлень користувача"""
        user_orders = []
        for order_id in self.users.get(str(user_id), {}).get('orders', []):
            if order_id in self.orders:
                user_orders.append(self.orders[order_id])
        return user_orders
    
    def get_recent_orders(self, limit: int = 10) -> List[Dict]:
        """Отримання останніх замовлень"""
        sorted_orders = sorted(
            self.orders.values(),
            key=lambda x: x['created_date'],
            reverse=True
        )
        return sorted_orders[:limit]
    
    def get_order(self, order_id: str) -> Optional[Dict]:
        """Отримання конкретного замовлення"""
        return self.orders.get(order_id)
    
    def get_all_users(self) -> List[Dict]:
        """Отримання всіх користувачів"""
        return [
            {
                'user_id': user_id,
                'username': user_data.get('username'),
                'first_name': user_data.get('first_name'),
                'joined_date': user_data.get('joined_date'),
                'orders_count': len(user_data.get('orders', []))
            }
            for user_id, user_data in self.users.items()
        ]
