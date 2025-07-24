"""
Система управления библиотекой
Автор: Тимченко Игорь Васильевич
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import json
import csv
import datetime
import os
import hashlib
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import threading
import logging
import re
from typing import List, Dict, Optional, Tuple
import random
import string
from dataclasses import dataclass
from enum import Enum
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('library_system.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """Роли пользователей в системе"""
    ADMIN = "admin"
    LIBRARIAN = "librarian"
    MEMBER = "member"
    GUEST = "guest"


class BookStatus(Enum):
    """Статусы книг"""
    AVAILABLE = "available"
    BORROWED = "borrowed"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"
    LOST = "lost"


class TransactionType(Enum):
    """Типы транзакций"""
    BORROW = "borrow"
    RETURN = "return"
    RESERVE = "reserve"
    CANCEL_RESERVATION = "cancel_reservation"
    FINE_PAYMENT = "fine_payment"


@dataclass
class Book:
    """Класс для представления книги"""
    id: Optional[int] = None
    title: str = ""
    author: str = ""
    isbn: str = ""
    publication_year: int = 0
    genre: str = ""
    publisher: str = ""
    pages: int = 0
    language: str = "ru"
    description: str = ""
    status: BookStatus = BookStatus.AVAILABLE
    location: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class User:
    """Класс для представления пользователя"""
    id: Optional[int] = None
    username: str = ""
    email: str = ""
    password_hash: str = ""
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    address: str = ""
    role: UserRole = UserRole.MEMBER
    registration_date: str = ""
    last_login: str = ""
    is_active: bool = True


@dataclass
class Transaction:
    """Класс для представления транзакции"""
    id: Optional[int] = None
    user_id: int = 0
    book_id: int = 0
    transaction_type: TransactionType = TransactionType.BORROW
    transaction_date: str = ""
    due_date: str = ""
    return_date: str = ""
    fine_amount: float = 0.0
    notes: str = ""


@dataclass
class Fine:
    """Класс для представления штрафа"""
    id: Optional[int] = None
    user_id: int = 0
    book_id: int = 0
    amount: float = 0.0
    reason: str = ""
    date_issued: str = ""
    date_paid: str = ""
    is_paid: bool = False


class DatabaseManager:
    """Менеджер базы данных"""
    
    def __init__(self, db_path: str = "library.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Получение соединения с базой данных"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Инициализация базы данных"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Создание таблицы книг
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS books (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        author TEXT NOT NULL,
                        isbn TEXT UNIQUE,
                        publication_year INTEGER,
                        genre TEXT,
                        publisher TEXT,
                        pages INTEGER,
                        language TEXT DEFAULT 'ru',
                        description TEXT,
                        status TEXT DEFAULT 'available',
                        location TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Создание таблицы пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        phone TEXT,
                        address TEXT,
                        role TEXT DEFAULT 'member',
                        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                
                # Создание таблицы транзакций
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        book_id INTEGER NOT NULL,
                        transaction_type TEXT NOT NULL,
                        transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        due_date TIMESTAMP,
                        return_date TIMESTAMP,
                        fine_amount REAL DEFAULT 0.0,
                        notes TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        FOREIGN KEY (book_id) REFERENCES books (id)
                    )
                ''')
                
                # Создание таблицы штрафов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS fines (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        book_id INTEGER NOT NULL,
                        amount REAL NOT NULL,
                        reason TEXT NOT NULL,
                        date_issued TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        date_paid TIMESTAMP,
                        is_paid BOOLEAN DEFAULT 0,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        FOREIGN KEY (book_id) REFERENCES books (id)
                    )
                ''')
                
                # Создание индексов для оптимизации
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_author ON books(author)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_status ON books(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_book_id ON transactions(book_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type)')
                
                # Создание администратора по умолчанию
                self.create_default_admin(cursor)
                
                conn.commit()
                logger.info("База данных инициализирована успешно")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    def create_default_admin(self, cursor):
        """Создание администратора по умолчанию"""
        try:
            # Проверяем, существует ли администратор
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            admin_count = cursor.fetchone()[0]
            
            if admin_count == 0:
                # Создаем администратора
                admin_password = self.hash_password("admin123")
                cursor.execute('''
                    INSERT INTO users (
                        username, email, password_hash, first_name, last_name, role
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', ("admin", "admin@library.com", admin_password, "Admin", "Administrator", "admin"))
                logger.info("Создан администратор по умолчанию")
                
        except Exception as e:
            logger.error(f"Ошибка создания администратора: {e}")
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Хеширование пароля"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str, hash_password: str) -> bool:
        """Проверка пароля"""
        return self.hash_password(password) == hash_password


class BookManager:
    """Менеджер книг"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def add_book(self, book: Book) -> bool:
        """Добавление книги"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO books (
                        title, author, isbn, publication_year, genre, publisher,
                        pages, language, description, status, location
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    book.title, book.author, book.isbn, book.publication_year,
                    book.genre, book.publisher, book.pages, book.language,
                    book.description, book.status.value, book.location
                ))
                conn.commit()
                logger.info(f"Добавлена книга: {book.title}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка добавления книги: {e}")
            return False
    
    def update_book(self, book: Book) -> bool:
        """Обновление информации о книге"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE books SET
                        title = ?, author = ?, isbn = ?, publication_year = ?,
                        genre = ?, publisher = ?, pages = ?, language = ?,
                        description = ?, status = ?, location = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    book.title, book.author, book.isbn, book.publication_year,
                    book.genre, book.publisher, book.pages, book.language,
                    book.description, book.status.value, book.location, book.id
                ))
                conn.commit()
                logger.info(f"Обновлена книга ID {book.id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка обновления книги: {e}")
            return False
    
    def delete_book(self, book_id: int) -> bool:
        """Удаление книги"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
                conn.commit()
                logger.info(f"Удалена книга ID {book_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка удаления книги: {e}")
            return False
    
    def get_book_by_id(self, book_id: int) -> Optional[Book]:
        """Получение книги по ID"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
                row = cursor.fetchone()
                if row:
                    return Book(**dict(row))
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения книги: {e}")
            return None
    
    def search_books(self, query: str, limit: int = 50) -> List[Book]:
        """Поиск книг"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                search_query = f"%{query}%"
                cursor.execute('''
                    SELECT * FROM books 
                    WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ? OR genre LIKE ?
                    ORDER BY title
                    LIMIT ?
                ''', (search_query, search_query, search_query, search_query, limit))
                
                books = []
                for row in cursor.fetchall():
                    books.append(Book(**dict(row)))
                return books
                
        except Exception as e:
            logger.error(f"Ошибка поиска книг: {e}")
            return []
    
    def get_all_books(self, limit: int = 100) -> List[Book]:
        """Получение всех книг"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM books ORDER BY title LIMIT ?', (limit,))
                books = []
                for row in cursor.fetchall():
                    books.append(Book(**dict(row)))
                return books
                
        except Exception as e:
            logger.error(f"Ошибка получения всех книг: {e}")
            return []
    
    def get_books_by_status(self, status: BookStatus) -> List[Book]:
        """Получение книг по статусу"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM books WHERE status = ? ORDER BY title', (status.value,))
                books = []
                for row in cursor.fetchall():
                    books.append(Book(**dict(row)))
                return books
                
        except Exception as e:
            logger.error(f"Ошибка получения книг по статусу: {e}")
            return []


class UserManager:
    """Менеджер пользователей"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def add_user(self, user: User) -> bool:
        """Добавление пользователя"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (
                        username, email, password_hash, first_name, last_name,
                        phone, address, role
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user.username, user.email, user.password_hash,
                    user.first_name, user.last_name, user.phone,
                    user.address, user.role.value
                ))
                conn.commit()
                logger.info(f"Добавлен пользователь: {user.username}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return False
    
    def update_user(self, user: User) -> bool:
        """Обновление информации о пользователе"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET
                        username = ?, email = ?, first_name = ?, last_name = ?,
                        phone = ?, address = ?, role = ?, is_active = ?
                    WHERE id = ?
                ''', (
                    user.username, user.email, user.first_name, user.last_name,
                    user.phone, user.address, user.role.value, user.is_active, user.id
                ))
                conn.commit()
                logger.info(f"Обновлен пользователь ID {user.id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка обновления пользователя: {e}")
            return False
    
    def delete_user(self, user_id: int) -> bool:
        """Удаление пользователя"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                logger.info(f"Удален пользователь ID {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка удаления пользователя: {e}")
            return False
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получение пользователя по ID"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    user_data = dict(row)
                    user_data['role'] = UserRole(user_data['role'])
                    return User(**user_data)
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Получение пользователя по имени"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                if row:
                    user_data = dict(row)
                    user_data['role'] = UserRole(user_data['role'])
                    return User(**user_data)
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения пользователя по имени: {e}")
            return None
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Аутентификация пользователя"""
        try:
            user = self.get_user_by_username(username)
            if user and self.db_manager.verify_password(password, user.password_hash):
                # Обновляем дату последнего входа
                with self.db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                        (user.id,)
                    )
                    conn.commit()
                return user
            return None
            
        except Exception as e:
            logger.error(f"Ошибка аутентификации: {e}")
            return None
    
    def search_users(self, query: str, limit: int = 50) -> List[User]:
        """Поиск пользователей"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                search_query = f"%{query}%"
                cursor.execute('''
                    SELECT * FROM users 
                    WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email LIKE ?
                    ORDER BY username
                    LIMIT ?
                ''', (search_query, search_query, search_query, search_query, limit))
                
                users = []
                for row in cursor.fetchall():
                    user_data = dict(row)
                    user_data['role'] = UserRole(user_data['role'])
                    users.append(User(**user_data))
                return users
                
        except Exception as e:
            logger.error(f"Ошибка поиска пользователей: {e}")
            return []
    
    def get_all_users(self, limit: int = 100) -> List[User]:
        """Получение всех пользователей"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users ORDER BY username LIMIT ?', (limit,))
                users = []
                for row in cursor.fetchall():
                    user_data = dict(row)
                    user_data['role'] = UserRole(user_data['role'])
                    users.append(User(**user_data))
                return users
                
        except Exception as e:
            logger.error(f"Ошибка получения всех пользователей: {e}")
            return []


class TransactionManager:
    """Менеджер транзакций"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def create_transaction(self, transaction: Transaction) -> bool:
        """Создание транзакции"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO transactions (
                        user_id, book_id, transaction_type, transaction_date,
                        due_date, return_date, fine_amount, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    transaction.user_id, transaction.book_id,
                    transaction.transaction_type.value, transaction.transaction_date,
                    transaction.due_date, transaction.return_date,
                    transaction.fine_amount, transaction.notes
                ))
                conn.commit()
                logger.info(f"Создана транзакция: {transaction.transaction_type.value}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка создания транзакции: {e}")
            return False
    
    def get_transaction_by_id(self, transaction_id: int) -> Optional[Transaction]:
        """Получение транзакции по ID"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
                row = cursor.fetchone()
                if row:
                    transaction_data = dict(row)
                    transaction_data['transaction_type'] = TransactionType(transaction_data['transaction_type'])
                    return Transaction(**transaction_data)
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения транзакции: {e}")
            return None
    
    def get_user_transactions(self, user_id: int) -> List[Transaction]:
        """Получение транзакций пользователя"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM transactions 
                    WHERE user_id = ? 
                    ORDER BY transaction_date DESC
                ''', (user_id,))
                
                transactions = []
                for row in cursor.fetchall():
                    transaction_data = dict(row)
                    transaction_data['transaction_type'] = TransactionType(transaction_data['transaction_type'])
                    transactions.append(Transaction(**transaction_data))
                return transactions
                
        except Exception as e:
            logger.error(f"Ошибка получения транзакций пользователя: {e}")
            return []
    
    def get_book_transactions(self, book_id: int) -> List[Transaction]:
        """Получение транзакций книги"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM transactions 
                    WHERE book_id = ? 
                    ORDER BY transaction_date DESC
                ''', (book_id,))
                
                transactions = []
                for row in cursor.fetchall():
                    transaction_data = dict(row)
                    transaction_data['transaction_type'] = TransactionType(transaction_data['transaction_type'])
                    transactions.append(Transaction(**transaction_data))
                return transactions
                
        except Exception as e:
            logger.error(f"Ошибка получения транзакций книги: {e}")
            return []
    
    def get_overdue_transactions(self) -> List[Transaction]:
        """Получение просроченных транзакций"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM transactions 
                    WHERE transaction_type = 'borrow' 
                    AND due_date < CURRENT_TIMESTAMP 
                    AND return_date IS NULL
                    ORDER BY due_date
                ''')
                
                transactions = []
                for row in cursor.fetchall():
                    transaction_data = dict(row)
                    transaction_data['transaction_type'] = TransactionType(transaction_data['transaction_type'])
                    transactions.append(Transaction(**transaction_data))
                return transactions
                
        except Exception as e:
            logger.error(f"Ошибка получения просроченных транзакций: {e}")
            return []


class FineManager:
    """Менеджер штрафов"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def add_fine(self, fine: Fine) -> bool:
        """Добавление штрафа"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO fines (
                        user_id, book_id, amount, reason, date_issued
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    fine.user_id, fine.book_id, fine.amount,
                    fine.reason, fine.date_issued
                ))
                conn.commit()
                logger.info(f"Добавлен штраф для пользователя ID {fine.user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка добавления штрафа: {e}")
            return False
    
    def pay_fine(self, fine_id: int) -> bool:
        """Оплата штрафа"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE fines SET
                        date_paid = CURRENT_TIMESTAMP,
                        is_paid = 1
                    WHERE id = ?
                ''', (fine_id,))
                conn.commit()
                logger.info(f"Оплачен штраф ID {fine_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка оплаты штрафа: {e}")
            return False
    
    def get_user_fines(self, user_id: int) -> List[Fine]:
        """Получение штрафов пользователя"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM fines 
                    WHERE user_id = ? 
                    ORDER BY date_issued DESC
                ''', (user_id,))
                
                fines = []
                for row in cursor.fetchall():
                    fines.append(Fine(**dict(row)))
                return fines
                
        except Exception as e:
            logger.error(f"Ошибка получения штрафов пользователя: {e}")
            return []
    
    def get_unpaid_fines(self) -> List[Fine]:
        """Получение неоплаченных штрафов"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM fines 
                    WHERE is_paid = 0 
                    ORDER BY date_issued
                ''')
                
                fines = []
                for row in cursor.fetchall():
                    fines.append(Fine(**dict(row)))
                return fines
                
        except Exception as e:
            logger.error(f"Ошибка получения неоплаченных штрафов: {e}")
            return []


class ReportGenerator:
    """Генератор отчетов"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def generate_books_report(self) -> Dict:
        """Генерация отчета по книгам"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Общее количество книг
                cursor.execute("SELECT COUNT(*) FROM books")
                total_books = cursor.fetchone()[0]
                
                # Количество книг по статусам
                cursor.execute('''
                    SELECT status, COUNT(*) as count 
                    FROM books 
                    GROUP BY status
                ''')
                books_by_status = dict(cursor.fetchall())
                
                # Топ 10 авторов
                cursor.execute('''
                    SELECT author, COUNT(*) as count 
                    FROM books 
                    GROUP BY author 
                    ORDER BY count DESC 
                    LIMIT 10
                ''')
                top_authors = dict(cursor.fetchall())
                
                # Топ 10 жанров
                cursor.execute('''
                    SELECT genre, COUNT(*) as count 
                    FROM books 
                    WHERE genre IS NOT NULL AND genre != ''
                    GROUP BY genre 
                    ORDER BY count DESC 
                    LIMIT 10
                ''')
                top_genres = dict(cursor.fetchall())
                
                return {
                    'total_books': total_books,
                    'books_by_status': books_by_status,
                    'top_authors': top_authors,
                    'top_genres': top_genres
                }
                
        except Exception as e:
            logger.error(f"Ошибка генерации отчета по книгам: {e}")
            return {}
    
    def generate_users_report(self) -> Dict:
        """Генерация отчета по пользователям"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Общее количество пользователей
                cursor.execute("SELECT COUNT(*) FROM users")
                total_users = cursor.fetchone()[0]
                
                # Количество пользователей по ролям
                cursor.execute('''
                    SELECT role, COUNT(*) as count 
                    FROM users 
                    GROUP BY role
                ''')
                users_by_role = dict(cursor.fetchall())
                
                # Активные пользователи за последний месяц
                cursor.execute('''
                    SELECT COUNT(*) 
                    FROM users 
                    WHERE last_login >= datetime('now', '-1 month')
                ''')
                active_users = cursor.fetchone()[0]
                
                return {
                    'total_users': total_users,
                    'users_by_role': users_by_role,
                    'active_users': active_users
                }
                
        except Exception as e:
            logger.error(f"Ошибка генерации отчета по пользователям: {e}")
            return {}
    
    def generate_transactions_report(self) -> Dict:
        """Генерация отчета по транзакциям"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Общее количество транзакций
                cursor.execute("SELECT COUNT(*) FROM transactions")
                total_transactions = cursor.fetchone()[0]
                
                # Транзакции по типам
                cursor.execute('''
                    SELECT transaction_type, COUNT(*) as count 
                    FROM transactions 
                    GROUP BY transaction_type
                ''')
                transactions_by_type = dict(cursor.fetchall())
                
                # Активные займы
                cursor.execute('''
                    SELECT COUNT(*) 
                    FROM transactions 
                    WHERE transaction_type = 'borrow' 
                    AND return_date IS NULL
                ''')
                active_borrows = cursor.fetchone()[0]
                
                # Просроченные книги
                cursor.execute('''
                    SELECT COUNT(*) 
                    FROM transactions 
                    WHERE transaction_type = 'borrow' 
                    AND due_date < CURRENT_TIMESTAMP 
                    AND return_date IS NULL
                ''')
                overdue_books = cursor.fetchone()[0]
                
                return {
                    'total_transactions': total_transactions,
                    'transactions_by_type': transactions_by_type,
                    'active_borrows': active_borrows,
                    'overdue_books': overdue_books
                }
                
        except Exception as e:
            logger.error(f"Ошибка генерации отчета по транзакциям: {e}")
            return {}


class EmailService:
    """Сервис отправки email"""
    
    def __init__(self, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email = ""
        self.password = ""
    
    def configure(self, email: str, password: str):
        """Настройка параметров email"""
        self.email = email
        self.password = password
    
    def send_email(self, to_email: str, subject: str, message: str) -> bool:
        """Отправка email"""
        try:
            if not self.email or not self.password:
                logger.warning("Email сервис не настроен")
                return False
            
            msg = MimeMultipart()
            msg['From'] = self.email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MimeText(message, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email, self.password)
            text = msg.as_string()
            server.sendmail(self.email, to_email, text)
            server.quit()
            
            logger.info(f"Email отправлен на {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}")
            return False


class LibrarySystem:
    """Основная система управления библиотекой"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.book_manager = BookManager(self.db_manager)
        self.user_manager = UserManager(self.db_manager)
        self.transaction_manager = TransactionManager(self.db_manager)
        self.fine_manager = FineManager(self.db_manager)
        self.report_generator = ReportGenerator(self.db_manager)
        self.email_service = EmailService()
        self.current_user: Optional[User] = None
        self.root = None
        self.setup_gui()
    
    def setup_gui(self):
        """Настройка графического интерфейса"""
        self.root = tk.Tk()
        self.root.title("Система управления библиотекой")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Создание стилей
        self.create_styles()
        
        # Создание меню
        self.create_menu()
        
        # Создание основных фреймов
        self.create_main_frames()
        
        # Создание виджетов
        self.create_widgets()
        
        # Загрузка начальных данных
        self.load_initial_data()
    
    def create_styles(self):
        """Создание стилей для интерфейса"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Стили для кнопок
        style.configure('Large.TButton', font=('Arial', 12, 'bold'), padding=10)
        style.configure('Small.TButton', font=('Arial', 10), padding=5)
        
        # Стили для заголовков
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Subtitle.TLabel', font=('Arial', 12, 'bold'))
        
        # Стили для таблиц
        style.configure('Treeview', rowheight=25)
        style.configure('Treeview.Heading', font=('Arial', 10, 'bold'))
    
    def create_menu(self):
        """Создание меню приложения"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Меню файл
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Экспорт данных", command=self.export_data)
        file_menu.add_command(label="Импорт данных", command=self.import_data)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.root.quit)
        
        # Меню отчеты
        reports_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Отчеты", menu=reports_menu)
        reports_menu.add_command(label="Отчет по книгам", command=self.show_books_report)
        reports_menu.add_command(label="Отчет по пользователям", command=self.show_users_report)
        reports_menu.add_command(label="Отчет по транзакциям", command=self.show_transactions_report)
        
        # Меню справка
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self.show_about)
        help_menu.add_command(label="Документация", command=self.show_documentation)
    
    def create_main_frames(self):
        """Создание основных фреймов"""
        # Верхний фрейм для навигации
        self.top_frame = ttk.Frame(self.root)
        self.top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Основной фрейм для контента
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Нижний фрейм для статуса
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Создание notebook для вкладок
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
    
    def create_widgets(self):
        """Создание виджетов"""
        # Создание вкладок
        self.create_login_tab()
        self.create_books_tab()
        self.create_users_tab()
        self.create_transactions_tab()
        self.create_reports_tab()
        
        # Создание статусной строки
        self.status_label = ttk.Label(
            self.status_frame, 
            text="Готов к работе", 
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        self.status_label.pack(fill=tk.X)
    
    def create_login_tab(self):
        """Создание вкладки входа"""
        self.login_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.login_frame, text="Вход в систему")
        
        # Центрирование элементов
        center_frame = ttk.Frame(self.login_frame)
        center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Заголовок
        ttk.Label(
            center_frame, 
            text="Вход в систему управления библиотекой", 
            style='Title.TLabel'
        ).pack(pady=(0, 20))
        
        # Форма входа
        login_form = ttk.LabelFrame(center_frame, text="Авторизация", padding=20)
        login_form.pack()
        
        # Имя пользователя
        ttk.Label(login_form, text="Имя пользователя:").pack(anchor=tk.W)
        self.username_entry = ttk.Entry(login_form, width=30)
        self.username_entry.pack(pady=(0, 10))
        
        # Пароль
        ttk.Label(login_form, text="Пароль:").pack(anchor=tk.W)
        self.password_entry = ttk.Entry(login_form, width=30, show="*")
        self.password_entry.pack(pady=(0, 20))
        
        # Кнопки
        buttons_frame = ttk.Frame(login_form)
        buttons_frame.pack()
        
        ttk.Button(
            buttons_frame, 
            text="Войти", 
            style='Large.TButton',
            command=self.login
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            buttons_frame, 
            text="Регистрация", 
            style='Large.TButton',
            command=self.show_registration
        ).pack(side=tk.LEFT)
        
        # Привязка Enter к входу
        self.password_entry.bind('<Return>', lambda e: self.login())
    
    def create_books_tab(self):
        """Создание вкладки книг"""
        self.books_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.books_frame, text="Книги", state='disabled')
        
        # Панель инструментов
        toolbar = ttk.Frame(self.books_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            toolbar, 
            text="Добавить книгу", 
            command=self.show_add_book_dialog
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            toolbar, 
            text="Редактировать", 
            command=self.show_edit_book_dialog
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            toolbar, 
            text="Удалить", 
            command=self.delete_book
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Label(toolbar, text="Поиск:").pack(side=tk.LEFT, padx=(10, 5))
        self.book_search_var = tk.StringVar()
        self.book_search_var.trace('w', self.search_books)
        self.book_search_entry = ttk.Entry(toolbar, textvariable=self.book_search_var, width=30)
        self.book_search_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        # Таблица книг
        table_frame = ttk.Frame(self.books_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Создание таблицы
        columns = ('ID', 'Название', 'Автор', 'ISBN', 'Год', 'Жанр', 'Статус')
        self.books_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        
        # Настройка заголовков
        for col in columns:
            self.books_tree.heading(col, text=col)
            self.books_tree.column(col, width=100)
        
        # Настройка размеров колонок
        self.books_tree.column('ID', width=50)
        self.books_tree.column('Название', width=250)
        self.books_tree.column('Автор', width=150)
        self.books_tree.column('ISBN', width=120)
        self.books_tree.column('Год', width=80)
        self.books_tree.column('Жанр', width=120)
        self.books_tree.column('Статус', width=100)
        
        # Полосы прокрутки
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.books_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.books_tree.xview)
        self.books_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Размещение элементов
        self.books_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Привязка двойного клика
        self.books_tree.bind('<Double-1>', self.show_book_details)
    
    def create_users_tab(self):
        """Создание вкладки пользователей"""
        self.users_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.users_frame, text="Пользователи", state='disabled')
        
        # Панель инструментов
        toolbar = ttk.Frame(self.users_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            toolbar, 
            text="Добавить пользователя", 
            command=self.show_add_user_dialog
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            toolbar, 
            text="Редактировать", 
            command=self.show_edit_user_dialog
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            toolbar, 
            text="Удалить", 
            command=self.delete_user
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Label(toolbar, text="Поиск:").pack(side=tk.LEFT, padx=(10, 5))
        self.user_search_var = tk.StringVar()
        self.user_search_var.trace('w', self.search_users)
        self.user_search_entry = ttk.Entry(toolbar, textvariable=self.user_search_var, width=30)
        self.user_search_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        # Таблица пользователей
        table_frame = ttk.Frame(self.users_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Создание таблицы
        columns = ('ID', 'Имя пользователя', 'Email', 'Имя', 'Фамилия', 'Роль', 'Активен')
        self.users_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        
        # Настройка заголовков
        for col in columns:
            self.users_tree.heading(col, text=col)
            self.users_tree.column(col, width=100)
        
        # Настройка размеров колонок
        self.users_tree.column('ID', width=50)
        self.users_tree.column('Имя пользователя', width=150)
        self.users_tree.column('Email', width=200)
        self.users_tree.column('Имя', width=120)
        self.users_tree.column('Фамилия', width=120)
        self.users_tree.column('Роль', width=100)
        self.users_tree.column('Активен', width=80)
        
        # Полосы прокрутки
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.users_tree.xview)
        self.users_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Размещение элементов
        self.users_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
    
    def create_transactions_tab(self):
        """Создание вкладки транзакций"""
        self.transactions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.transactions_frame, text="Транзакции", state='disabled')
        
        # Панель инструментов
        toolbar = ttk.Frame(self.transactions_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            toolbar, 
            text="Выдать книгу", 
            command=self.show_borrow_dialog
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            toolbar, 
            text="Вернуть книгу", 
            command=self.show_return_dialog
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            toolbar, 
            text="Зарезервировать", 
            command=self.show_reserve_dialog
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Button(
            toolbar, 
            text="Просроченные", 
            command=self.show_overdue_transactions
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        # Таблица транзакций
        table_frame = ttk.Frame(self.transactions_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Создание таблицы
        columns = ('ID', 'Пользователь', 'Книга', 'Тип', 'Дата', 'Срок', 'Возврат', 'Штраф')
        self.transactions_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        
        # Настройка заголовков
        for col in columns:
            self.transactions_tree.heading(col, text=col)
            self.transactions_tree.column(col, width=100)
        
        # Настройка размеров колонок
        self.transactions_tree.column('ID', width=50)
        self.transactions_tree.column('Пользователь', width=150)
        self.transactions_tree.column('Книга', width=200)
        self.transactions_tree.column('Тип', width=100)
        self.transactions_tree.column('Дата', width=120)
        self.transactions_tree.column('Срок', width=120)
        self.transactions_tree.column('Возврат', width=120)
        self.transactions_tree.column('Штраф', width=80)
        
        # Полосы прокрутки
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.transactions_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.transactions_tree.xview)
        self.transactions_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Размещение элементов
        self.transactions_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
    
    def create_reports_tab(self):
        """Создание вкладки отчетов"""
        self.reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.reports_frame, text="Отчеты", state='disabled')
        
        # Создание notebook для отчетов
        reports_notebook = ttk.Notebook(self.reports_frame)
        reports_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Вкладка отчета по книгам
        self.books_report_frame = ttk.Frame(reports_notebook)
        reports_notebook.add(self.books_report_frame, text="Книги")
        
        # Вкладка отчета по пользователям
        self.users_report_frame = ttk.Frame(reports_notebook)
        reports_notebook.add(self.users_report_frame, text="Пользователи")
        
        # Вкладка отчета по транзакциям
        self.transactions_report_frame = ttk.Frame(reports_notebook)
        reports_notebook.add(self.transactions_report_frame, text="Транзакции")
        
        # Кнопка обновления отчетов
        update_frame = ttk.Frame(self.reports_frame)
        update_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            update_frame,
            text="Обновить все отчеты",
            command=self.update_all_reports
        ).pack(side=tk.RIGHT)
    
    def load_initial_data(self):
        """Загрузка начальных данных"""
        self.update_status("Загрузка данных...")
        self.root.after(100, self.load_books_data)
        self.root.after(200, self.load_users_data)
        self.root.after(300, self.load_transactions_data)
        self.root.after(400, lambda: self.update_status("Готов к работе"))
    
    def load_books_data(self):
        """Загрузка данных о книгах"""
        try:
            books = self.book_manager.get_all_books()
            self.update_books_table(books)
        except Exception as e:
            logger.error(f"Ошибка загрузки книг: {e}")
    
    def load_users_data(self):
        """Загрузка данных о пользователях"""
        try:
            users = self.user_manager.get_all_users()
            self.update_users_table(users)
        except Exception as e:
            logger.error(f"Ошибка загрузки пользователей: {e}")
    
    def load_transactions_data(self):
        """Загрузка данных о транзакциях"""
        try:
            # Для демонстрации загружаем последние 100 транзакций
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT t.*, u.username, b.title 
                    FROM transactions t
                    JOIN users u ON t.user_id = u.id
                    JOIN books b ON t.book_id = b.id
                    ORDER BY t.transaction_date DESC
                    LIMIT 100
                ''')
                
                transactions = []
                for row in cursor.fetchall():
                    transaction_data = dict(row)
                    transaction_data['transaction_type'] = TransactionType(transaction_data['transaction_type'])
                    transactions.append(transaction_data)
                
                self.update_transactions_table(transactions)
                
        except Exception as e:
            logger.error(f"Ошибка загрузки транзакций: {e}")
    
    def update_books_table(self, books: List[Book]):
        """Обновление таблицы книг"""
        # Очистка таблицы
        for item in self.books_tree.get_children():
            self.books_tree.delete(item)
        
        # Добавление данных
        for book in books:
            self.books_tree.insert('', tk.END, values=(
                book.id,
                book.title,
                book.author,
                book.isbn,
                book.publication_year,
                book.genre,
                book.status.value
            ))
    
    def update_users_table(self, users: List[User]):
        """Обновление таблицы пользователей"""
        # Очистка таблицы
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        
        # Добавление данных
        for user in users:
            self.users_tree.insert('', tk.END, values=(
                user.id,
                user.username,
                user.email,
                user.first_name,
                user.last_name,
                user.role.value,
                "Да" if user.is_active else "Нет"
            ))
    
    def update_transactions_table(self, transactions: List[Dict]):
        """Обновление таблицы транзакций"""
        # Очистка таблицы
        for item in self.transactions_tree.get_children():
            self.transactions_tree.delete(item)
        
        # Добавление данных
        for transaction in transactions:
            # Форматирование дат
            transaction_date = transaction.get('transaction_date', '')[:10] if transaction.get('transaction_date') else ''
            due_date = transaction.get('due_date', '')[:10] if transaction.get('due_date') else ''
            return_date = transaction.get('return_date', '')[:10] if transaction.get('return_date') else ''
            
            self.transactions_tree.insert('', tk.END, values=(
                transaction.get('id', ''),
                transaction.get('username', ''),
                transaction.get('title', ''),
                transaction.get('transaction_type', ''),
                transaction_date,
                due_date,
                return_date,
                f"{transaction.get('fine_amount', 0):.2f}"
            ))
    
    def login(self):
        """Обработка входа в систему"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        
        if not username or not password:
            messagebox.showerror("Ошибка", "Введите имя пользователя и пароль")
            return
        
        user = self.user_manager.authenticate_user(username, password)
        if user:
            self.current_user = user
            self.on_login_success()
            self.update_status(f"Пользователь {user.username} вошел в систему")
            logger.info(f"Пользователь {username} успешно вошел в систему")
        else:
            messagebox.showerror("Ошибка", "Неверное имя пользователя или пароль")
            self.update_status("Ошибка входа")
            logger.warning(f"Неудачная попытка входа: {username}")
    
    def on_login_success(self):
        """Действия после успешного входа"""
        # Активируем все вкладки
        for i in range(1, self.notebook.index('end')):  # Пропускаем первую вкладку (вход)
            self.notebook.tab(i, state='normal')
        
        # Переключаемся на вкладку книг
        self.notebook.select(1)
        
        # Обновляем интерфейс в зависимости от роли пользователя
        self.update_interface_for_role()
    
    def update_interface_for_role(self):
        """Обновление интерфейса в зависимости от роли пользователя"""
        if not self.current_user:
            return
        
        # Для обычных пользователей ограничиваем доступ
        if self.current_user.role == UserRole.MEMBER:
            # Скрываем некоторые кнопки
            for widget in self.books_frame.winfo_children():
                if isinstance(widget, ttk.Frame) and widget.winfo_children():
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Button) and child['text'] in ['Добавить книгу', 'Редактировать', 'Удалить']:
                            child.configure(state='disabled')
    
    def logout(self):
        """Выход из системы"""
        self.current_user = None
        # Деактивируем все вкладки кроме входа
        for i in range(1, self.notebook.index('end')):
            self.notebook.tab(i, state='disabled')
        # Переключаемся на вкладку входа
        self.notebook.select(0)
        self.update_status("Выполнен выход из системы")
    
    def show_add_book_dialog(self):
        """Показ диалога добавления книги"""
        dialog = BookDialog(self.root, self.book_manager, "Добавить книгу")
        self.root.wait_window(dialog.top)
        if dialog.result:
            self.load_books_data()
    
    def show_edit_book_dialog(self):
        """Показ диалога редактирования книги"""
        selection = self.books_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите книгу для редактирования")
            return
        
        item = self.books_tree.item(selection[0])
        book_id = item['values'][0]
        book = self.book_manager.get_book_by_id(book_id)
        
        if book:
            dialog = BookDialog(self.root, self.book_manager, "Редактировать книгу", book)
            self.root.wait_window(dialog.top)
            if dialog.result:
                self.load_books_data()
        else:
            messagebox.showerror("Ошибка", "Книга не найдена")
    
    def delete_book(self):
        """Удаление книги"""
        selection = self.books_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите книгу для удаления")
            return
        
        if messagebox.askyesno("Подтверждение", "Вы уверены, что хотите удалить выбранную книгу?"):
            item = self.books_tree.item(selection[0])
            book_id = item['values'][0]
            
            if self.book_manager.delete_book(book_id):
                messagebox.showinfo("Успех", "Книга успешно удалена")
                self.load_books_data()
            else:
                messagebox.showerror("Ошибка", "Не удалось удалить книгу")
    
    def search_books(self, *args):
        """Поиск книг"""
        query = self.book_search_var.get().strip()
        if query:
            books = self.book_manager.search_books(query)
        else:
            books = self.book_manager.get_all_books()
        self.update_books_table(books)
    
    def show_book_details(self, event):
        """Показ деталей книги"""
        selection = self.books_tree.selection()
        if selection:
            item = self.books_tree.item(selection[0])
            book_id = item['values'][0]
            book = self.book_manager.get_book_by_id(book_id)
            if book:
                BookDetailsDialog(self.root, book)
    
    def show_add_user_dialog(self):
        """Показ диалога добавления пользователя"""
        dialog = UserDialog(self.root, self.user_manager, "Добавить пользователя")
        self.root.wait_window(dialog.top)
        if dialog.result:
            self.load_users_data()
    
    def show_edit_user_dialog(self):
        """Показ диалога редактирования пользователя"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите пользователя для редактирования")
            return
        
        item = self.users_tree.item(selection[0])
        user_id = item['values'][0]
        user = self.user_manager.get_user_by_id(user_id)
        
        if user:
            dialog = UserDialog(self.root, self.user_manager, "Редактировать пользователя", user)
            self.root.wait_window(dialog.top)
            if dialog.result:
                self.load_users_data()
        else:
            messagebox.showerror("Ошибка", "Пользователь не найден")
    
    def delete_user(self):
        """Удаление пользователя"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите пользователя для удаления")
            return
        
        if messagebox.askyesno("Подтверждение", "Вы уверены, что хотите удалить выбранного пользователя?"):
            item = self.users_tree.item(selection[0])
            user_id = item['values'][0]
            
            if self.user_manager.delete_user(user_id):
                messagebox.showinfo("Успех", "Пользователь успешно удален")
                self.load_users_data()
            else:
                messagebox.showerror("Ошибка", "Не удалось удалить пользователя")
    
    def search_users(self, *args):
        """Поиск пользователей"""
        query = self.user_search_var.get().strip()
        if query:
            users = self.user_manager.search_users(query)
        else:
            users = self.user_manager.get_all_users()
        self.update_users_table(users)
    
    def show_borrow_dialog(self):
        """Показ диалога выдачи книги"""
        dialog = TransactionDialog(self.root, self, "Выдача книги", TransactionType.BORROW)
        self.root.wait_window(dialog.top)
        if dialog.result:
            self.load_transactions_data()
    
    def show_return_dialog(self):
        """Показ диалога возврата книги"""
        dialog = TransactionDialog(self.root, self, "Возврат книги", TransactionType.RETURN)
        self.root.wait_window(dialog.top)
        if dialog.result:
            self.load_transactions_data()
    
    def show_reserve_dialog(self):
        """Показ диалога резервирования книги"""
        dialog = TransactionDialog(self.root, self, "Резервирование книги", TransactionType.RESERVE)
        self.root.wait_window(dialog.top)
        if dialog.result:
            self.load_transactions_data()
    
    def show_overdue_transactions(self):
        """Показ просроченных транзакций"""
        overdue_transactions = self.transaction_manager.get_overdue_transactions()
        if overdue_transactions:
            OverdueDialog(self.root, overdue_transactions, self.user_manager, self.book_manager)
        else:
            messagebox.showinfo("Информация", "Нет просроченных транзакций")
    
    def show_books_report(self):
        """Показ отчета по книгам"""
        report = self.report_generator.generate_books_report()
        BooksReportDialog(self.root, report)
    
    def show_users_report(self):
        """Показ отчета по пользователям"""
        report = self.report_generator.generate_users_report()
        UsersReportDialog(self.root, report)
    
    def show_transactions_report(self):
        """Показ отчета по транзакциям"""
        report = self.report_generator.generate_transactions_report()
        TransactionsReportDialog(self.root, report)
    
    def update_all_reports(self):
        """Обновление всех отчетов"""
        self.update_status("Обновление отчетов...")
        try:
            # Обновляем отчеты по книгам
            books_report = self.report_generator.generate_books_report()
            self.display_books_report(books_report)
            
            # Обновляем отчеты по пользователям
            users_report = self.report_generator.generate_users_report()
            self.display_users_report(users_report)
            
            # Обновляем отчеты по транзакциям
            transactions_report = self.report_generator.generate_transactions_report()
            self.display_transactions_report(transactions_report)
            
            self.update_status("Отчеты обновлены")
        except Exception as e:
            logger.error(f"Ошибка обновления отчетов: {e}")
            self.update_status("Ошибка обновления отчетов")
    
    def display_books_report(self, report: Dict):
        """Отображение отчета по книгам"""
        # Очистка фрейма
        for widget in self.books_report_frame.winfo_children():
            widget.destroy()
        
        # Создание виджетов для отображения отчета
        main_frame = ttk.Frame(self.books_report_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Заголовок
        ttk.Label(main_frame, text="Отчет по книгам", style='Title.TLabel').pack(pady=(0, 20))
        
        # Основные показатели
        stats_frame = ttk.LabelFrame(main_frame, text="Основные показатели", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(stats_frame, text=f"Всего книг: {report.get('total_books', 0)}").pack(anchor=tk.W)
        
        # Статусы книг
        status_frame = ttk.LabelFrame(main_frame, text="Книги по статусам", padding=10)
        status_frame.pack(fill=tk.X, pady=(0, 20))
        
        for status, count in report.get('books_by_status', {}).items():
            ttk.Label(status_frame, text=f"{status}: {count}").pack(anchor=tk.W)
        
        # Топ авторов
        authors_frame = ttk.LabelFrame(main_frame, text="Топ 10 авторов", padding=10)
        authors_frame.pack(fill=tk.X, pady=(0, 20))
        
        for author, count in list(report.get('top_authors', {}).items())[:10]:
            ttk.Label(authors_frame, text=f"{author}: {count}").pack(anchor=tk.W)
    
    def display_users_report(self, report: Dict):
        """Отображение отчета по пользователям"""
        # Очистка фрейма
        for widget in self.users_report_frame.winfo_children():
            widget.destroy()
        
        # Создание виджетов для отображения отчета
        main_frame = ttk.Frame(self.users_report_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Заголовок
        ttk.Label(main_frame, text="Отчет по пользователям", style='Title.TLabel').pack(pady=(0, 20))
        
        # Основные показатели
        stats_frame = ttk.LabelFrame(main_frame, text="Основные показатели", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(stats_frame, text=f"Всего пользователей: {report.get('total_users', 0)}").pack(anchor=tk.W)
        ttk.Label(stats_frame, text=f"Активных пользователей (месяц): {report.get('active_users', 0)}").pack(anchor=tk.W)
        
        # Пользователи по ролям
        roles_frame = ttk.LabelFrame(main_frame, text="Пользователи по ролям", padding=10)
        roles_frame.pack(fill=tk.X, pady=(0, 20))
        
        for role, count in report.get('users_by_role', {}).items():
            ttk.Label(roles_frame, text=f"{role}: {count}").pack(anchor=tk.W)
    
    def display_transactions_report(self, report: Dict):
        """Отображение отчета по транзакциям"""
        # Очистка фрейма
        for widget in self.transactions_report_frame.winfo_children():
            widget.destroy()
        
        # Создание виджетов для отображения отчета
        main_frame = ttk.Frame(self.transactions_report_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Заголовок
        ttk.Label(main_frame, text="Отчет по транзакциям", style='Title.TLabel').pack(pady=(0, 20))
        
        # Основные показатели
        stats_frame = ttk.LabelFrame(main_frame, text="Основные показатели", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(stats_frame, text=f"Всего транзакций: {report.get('total_transactions', 0)}").pack(anchor=tk.W)
        ttk.Label(stats_frame, text=f"Активных займов: {report.get('active_borrows', 0)}").pack(anchor=tk.W)
        ttk.Label(stats_frame, text=f"Просроченных книг: {report.get('overdue_books', 0)}").pack(anchor=tk.W)
        
        # Транзакции по типам
        types_frame = ttk.LabelFrame(main_frame, text="Транзакции по типам", padding=10)
        types_frame.pack(fill=tk.X, pady=(0, 20))
        
        for transaction_type, count in report.get('transactions_by_type', {}).items():
            ttk.Label(types_frame, text=f"{transaction_type}: {count}").pack(anchor=tk.W)
    
    def show_registration(self):
        """Показ диалога регистрации"""
        dialog = RegistrationDialog(self.root, self.user_manager)
        self.root.wait_window(dialog.top)
    
    def export_data(self):
        """Экспорт данных"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if filename:
                # Экспорт данных в CSV
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    # Заголовки
                    writer.writerow(['ID', 'Название', 'Автор', 'ISBN', 'Год', 'Жанр', 'Издатель'])
                    # Данные книг
                    books = self.book_manager.get_all_books()
                    for book in books:
                        writer.writerow([
                            book.id, book.title, book.author, book.isbn,
                            book.publication_year, book.genre, book.publisher
                        ])
                messagebox.showinfo("Успех", f"Данные экспортированы в {filename}")
        except Exception as e:
            logger.error(f"Ошибка экспорта данных: {e}")
            messagebox.showerror("Ошибка", "Не удалось экспортировать данные")
    
    def import_data(self):
        """Импорт данных"""
        try:
            filename = filedialog.askopenfilename(
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if filename:
                # Импорт данных из CSV
                with open(filename, 'r', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    next(reader)  # Пропускаем заголовки
                    imported_count = 0
                    for row in reader:
                        if len(row) >= 7:
                            book = Book(
                                title=row[1],
                                author=row[2],
                                isbn=row[3],
                                publication_year=int(row[4]) if row[4].isdigit() else 0,
                                genre=row[5],
                                publisher=row[6]
                            )
                            if self.book_manager.add_book(book):
                                imported_count += 1
                messagebox.showinfo("Успех", f"Импортировано {imported_count} книг")
                self.load_books_data()
        except Exception as e:
            logger.error(f"Ошибка импорта данных: {e}")
            messagebox.showerror("Ошибка", "Не удалось импортировать данные")
    
    def show_about(self):
        """Показ информации о программе"""
        about_text = """
        Система управления библиотекой
        Версия: 1.0
        
        Разработана с использованием Python и Tkinter
        
        Основные возможности:
        - Управление книгами
        - Управление пользователями
        - Учет выдачи и возврата книг
        - Генерация отчетов
        - Система штрафов
        
        © 2024 Все права защищены
        """
        messagebox.showinfo("О программе", about_text)
    
    def show_documentation(self):
        """Показ документации"""
        doc_text = """
        Документация системы управления библиотекой
        
        Основные разделы:
        
        1. Вход в систему
        - Введите имя пользователя и пароль
        - По умолчанию доступен администратор: admin / admin123
        
        2. Управление книгами
        - Добавление, редактирование, удаление книг
        - Поиск по различным критериям
        - Просмотр детальной информации
        
        3. Управление пользователями
        - Регистрация новых пользователей
        - Назначение ролей (администратор, библиотекарь, член)
        - Активация/деактивация учетных записей
        
        4. Транзакции
        - Выдача книг пользователям
        - Возврат книг
        - Резервирование книг
        - Автоматический расчет штрафов
        
        5. Отчеты
        - Статистика по книгам
        - Аналитика по пользователям
        - Отчеты по транзакциям
        
        Для получения дополнительной помощи обратитесь к администратору.
        """
        DocumentationDialog(self.root, doc_text)
    
    def update_status(self, message: str):
        """Обновление статусной строки"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def run(self):
        """Запуск приложения"""
        logger.info("Запуск системы управления библиотекой")
        self.root.mainloop()
        logger.info("Система завершена")


class BookDialog:
    """Диалоговое окно для работы с книгами"""
    
    def __init__(self, parent, book_manager: BookManager, title: str, book: Book = None):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("500x600")
        self.top.transient(parent)
        self.top.grab_set()
        
        self.book_manager = book_manager
        self.book = book or Book()
        self.result = False
        
        self.create_widgets()
        self.populate_fields()
        
        # Центрирование окна
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        # Основная рамка
        main_frame = ttk.Frame(self.top, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Форма ввода данных
        form_frame = ttk.LabelFrame(main_frame, text="Информация о книге", padding=10)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Название
        ttk.Label(form_frame, text="Название:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.title_entry = ttk.Entry(form_frame, width=40)
        self.title_entry.grid(row=0, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Автор
        ttk.Label(form_frame, text="Автор:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.author_entry = ttk.Entry(form_frame, width=40)
        self.author_entry.grid(row=1, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # ISBN
        ttk.Label(form_frame, text="ISBN:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.isbn_entry = ttk.Entry(form_frame, width=40)
        self.isbn_entry.grid(row=2, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Год публикации
        ttk.Label(form_frame, text="Год публикации:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.year_entry = ttk.Entry(form_frame, width=40)
        self.year_entry.grid(row=3, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Жанр
        ttk.Label(form_frame, text="Жанр:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.genre_entry = ttk.Entry(form_frame, width=40)
        self.genre_entry.grid(row=4, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Издатель
        ttk.Label(form_frame, text="Издатель:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.publisher_entry = ttk.Entry(form_frame, width=40)
        self.publisher_entry.grid(row=5, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Количество страниц
        ttk.Label(form_frame, text="Страниц:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.pages_entry = ttk.Entry(form_frame, width=40)
        self.pages_entry.grid(row=6, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Язык
        ttk.Label(form_frame, text="Язык:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.language_entry = ttk.Entry(form_frame, width=40)
        self.language_entry.grid(row=7, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Расположение
        ttk.Label(form_frame, text="Расположение:").grid(row=8, column=0, sticky=tk.W, pady=2)
        self.location_entry = ttk.Entry(form_frame, width=40)
        self.location_entry.grid(row=8, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Статус
        ttk.Label(form_frame, text="Статус:").grid(row=9, column=0, sticky=tk.W, pady=2)
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(
            form_frame, 
            textvariable=self.status_var,
            values=[status.value for status in BookStatus],
            width=37,
            state="readonly"
        )
        status_combo.grid(row=9, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        status_combo.set(BookStatus.AVAILABLE.value)
        
        # Описание
        ttk.Label(form_frame, text="Описание:").grid(row=10, column=0, sticky=tk.NW, pady=2)
        self.description_text = tk.Text(form_frame, width=40, height=5)
        self.description_text.grid(row=10, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(
            button_frame, 
            text="Сохранить", 
            command=self.save_book
        ).pack(side=tk.RIGHT, padx=(10, 0))
        
        ttk.Button(
            button_frame, 
            text="Отмена", 
            command=self.cancel
        ).pack(side=tk.RIGHT)
    
    def populate_fields(self):
        """Заполнение полей данными книги"""
        self.title_entry.insert(0, self.book.title)
        self.author_entry.insert(0, self.book.author)
        self.isbn_entry.insert(0, self.book.isbn)
        self.year_entry.insert(0, str(self.book.publication_year) if self.book.publication_year else "")
        self.genre_entry.insert(0, self.book.genre)
        self.publisher_entry.insert(0, self.book.publisher)
        self.pages_entry.insert(0, str(self.book.pages) if self.book.pages else "")
        self.language_entry.insert(0, self.book.language)
        self.location_entry.insert(0, self.book.location)
        self.status_var.set(self.book.status.value if self.book.status else BookStatus.AVAILABLE.value)
        self.description_text.insert("1.0", self.book.description)
    
    def save_book(self):
        """Сохранение книги"""
        try:
            # Получение данных из полей
            title = self.title_entry.get().strip()
            author = self.author_entry.get().strip()
            
            if not title or not author:
                messagebox.showerror("Ошибка", "Название и автор обязательны для заполнения")
                return
            
            # Обновление данных книги
            self.book.title = title
            self.book.author = author
            self.book.isbn = self.isbn_entry.get().strip()
            self.book.publication_year = int(self.year_entry.get().strip() or 0)
            self.book.genre = self.genre_entry.get().strip()
            self.book.publisher = self.publisher_entry.get().strip()
            self.book.pages = int(self.pages_entry.get().strip() or 0)
            self.book.language = self.language_entry.get().strip() or "ru"
            self.book.location = self.location_entry.get().strip()
            self.book.status = BookStatus(self.status_var.get())
            self.book.description = self.description_text.get("1.0", tk.END).strip()
            
            # Сохранение в базу данных
            if self.book.id:
                # Обновление существующей книги
                if self.book_manager.update_book(self.book):
                    messagebox.showinfo("Успех", "Книга успешно обновлена")
                    self.result = True
                    self.top.destroy()
                else:
                    messagebox.showerror("Ошибка", "Не удалось обновить книгу")
            else:
                # Добавление новой книги
                if self.book_manager.add_book(self.book):
                    messagebox.showinfo("Успех", "Книга успешно добавлена")
                    self.result = True
                    self.top.destroy()
                else:
                    messagebox.showerror("Ошибка", "Не удалось добавить книгу")
                    
        except ValueError as e:
            messagebox.showerror("Ошибка", "Проверьте правильность введенных данных")
        except Exception as e:
            logger.error(f"Ошибка сохранения книги: {e}")
            messagebox.showerror("Ошибка", "Произошла ошибка при сохранении книги")
    
    def cancel(self):
        """Отмена операции"""
        self.top.destroy()


class UserDialog:
    """Диалоговое окно для работы с пользователями"""
    
    def __init__(self, parent, user_manager: UserManager, title: str, user: User = None):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("400x500")
        self.top.transient(parent)
        self.top.grab_set()
        
        self.user_manager = user_manager
        self.user = user or User()
        self.result = False
        
        self.create_widgets()
        self.populate_fields()
        
        # Центрирование окна
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        # Основная рамка
        main_frame = ttk.Frame(self.top, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Форма ввода данных
        form_frame = ttk.LabelFrame(main_frame, text="Информация о пользователе", padding=10)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Имя пользователя
        ttk.Label(form_frame, text="Имя пользователя:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.username_entry = ttk.Entry(form_frame, width=30)
        self.username_entry.grid(row=0, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Email
        ttk.Label(form_frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.email_entry = ttk.Entry(form_frame, width=30)
        self.email_entry.grid(row=1, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Пароль
        ttk.Label(form_frame, text="Пароль:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.password_entry = ttk.Entry(form_frame, width=30, show="*")
        self.password_entry.grid(row=2, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Имя
        ttk.Label(form_frame, text="Имя:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.first_name_entry = ttk.Entry(form_frame, width=30)
        self.first_name_entry.grid(row=3, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Фамилия
        ttk.Label(form_frame, text="Фамилия:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.last_name_entry = ttk.Entry(form_frame, width=30)
        self.last_name_entry.grid(row=4, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Телефон
        ttk.Label(form_frame, text="Телефон:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.phone_entry = ttk.Entry(form_frame, width=30)
        self.phone_entry.grid(row=5, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Адрес
        ttk.Label(form_frame, text="Адрес:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.address_entry = ttk.Entry(form_frame, width=30)
        self.address_entry.grid(row=6, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Роль
        ttk.Label(form_frame, text="Роль:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.role_var = tk.StringVar()
        role_combo = ttk.Combobox(
            form_frame, 
            textvariable=self.role_var,
            values=[role.value for role in UserRole],
            width=27,
            state="readonly"
        )
        role_combo.grid(row=7, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        role_combo.set(UserRole.MEMBER.value)
        
        # Активен
        self.active_var = tk.BooleanVar(value=True)
        active_check = ttk.Checkbutton(
            form_frame, 
            text="Активен", 
            variable=self.active_var
        )
        active_check.grid(row=8, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(
            button_frame, 
            text="Сохранить", 
            command=self.save_user
        ).pack(side=tk.RIGHT, padx=(10, 0))
        
        ttk.Button(
            button_frame, 
            text="Отмена", 
            command=self.cancel
        ).pack(side=tk.RIGHT)
    
    def populate_fields(self):
        """Заполнение полей данными пользователя"""
        self.username_entry.insert(0, self.user.username)
        self.email_entry.insert(0, self.user.email)
        # Пароль не заполняем для безопасности
        self.first_name_entry.insert(0, self.user.first_name)
        self.last_name_entry.insert(0, self.user.last_name)
        self.phone_entry.insert(0, self.user.phone)
        self.address_entry.insert(0, self.user.address)
        self.role_var.set(self.user.role.value if self.user.role else UserRole.MEMBER.value)
        self.active_var.set(self.user.is_active)
    
    def save_user(self):
        """Сохранение пользователя"""
        try:
            # Получение данных из полей
            username = self.username_entry.get().strip()
            email = self.email_entry.get().strip()
            password = self.password_entry.get()
            first_name = self.first_name_entry.get().strip()
            last_name = self.last_name_entry.get().strip()
            
            if not username or not email or not first_name or not last_name:
                messagebox.showerror("Ошибка", "Все обязательные поля должны быть заполнены")
                return
            
            # Проверка email
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                messagebox.showerror("Ошибка", "Неверный формат email")
                return
            
            # Обновление данных пользователя
            self.user.username = username
            self.user.email = email
            if password:  # Обновляем пароль только если он введен
                self.user.password_hash = self.user_manager.db_manager.hash_password(password)
            self.user.first_name = first_name
            self.user.last_name = last_name
            self.user.phone = self.phone_entry.get().strip()
            self.user.address = self.address_entry.get().strip()
            self.user.role = UserRole(self.role_var.get())
            self.user.is_active = self.active_var.get()
            
            # Сохранение в базу данных
            if self.user.id:
                # Обновление существующего пользователя
                if self.user_manager.update_user(self.user):
                    messagebox.showinfo("Успех", "Пользователь успешно обновлен")
                    self.result = True
                    self.top.destroy()
                else:
                    messagebox.showerror("Ошибка", "Не удалось обновить пользователя")
            else:
                # Добавление нового пользователя
                if not password:
                    messagebox.showerror("Ошибка", "Пароль обязателен для нового пользователя")
                    return
                
                if self.user_manager.add_user(self.user):
                    messagebox.showinfo("Успех", "Пользователь успешно добавлен")
                    self.result = True
                    self.top.destroy()
                else:
                    messagebox.showerror("Ошибка", "Не удалось добавить пользователя")
                    
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователя: {e}")
            messagebox.showerror("Ошибка", "Произошла ошибка при сохранении пользователя")
    
    def cancel(self):
        """Отмена операции"""
        self.top.destroy()


class TransactionDialog:
    """Диалоговое окно для работы с транзакциями"""
    
    def __init__(self, parent, library_system: LibrarySystem, title: str, transaction_type: TransactionType):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("400x350")
        self.top.transient(parent)
        self.top.grab_set()
        
        self.library_system = library_system
        self.transaction_type = transaction_type
        self.result = False
        
        self.create_widgets()
        
        # Центрирование окна
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        # Основная рамка
        main_frame = ttk.Frame(self.top, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Форма ввода данных
        form_frame = ttk.LabelFrame(main_frame, text="Информация о транзакции", padding=10)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Пользователь
        ttk.Label(form_frame, text="Пользователь:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.user_var = tk.StringVar()
        self.user_combo = ttk.Combobox(
            form_frame, 
            textvariable=self.user_var,
            width=30,
            state="readonly"
        )
        self.user_combo.grid(row=0, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        self.load_users()
        
        # Книга
        ttk.Label(form_frame, text="Книга:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.book_var = tk.StringVar()
        self.book_combo = ttk.Combobox(
            form_frame, 
            textvariable=self.book_var,
            width=30,
            state="readonly"
        )
        self.book_combo.grid(row=1, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        self.load_books()
        
        # Дата возврата (для выдачи)
        if self.transaction_type == TransactionType.BORROW:
            ttk.Label(form_frame, text="Срок возврата:").grid(row=2, column=0, sticky=tk.W, pady=2)
            self.due_date_entry = ttk.Entry(form_frame, width=30)
            self.due_date_entry.grid(row=2, column=1, sticky=tk.W, pady=2, padx=(10, 0))
            self.due_date_entry.insert(0, (datetime.datetime.now() + datetime.timedelta(days=14)).strftime("%Y-%m-%d"))
        
        # Примечания
        ttk.Label(form_frame, text="Примечания:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.notes_text = tk.Text(form_frame, width=30, height=3)
        self.notes_text.grid(row=3, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(
            button_frame, 
            text="Выполнить", 
            command=self.execute_transaction
        ).pack(side=tk.RIGHT, padx=(10, 0))
        
        ttk.Button(
            button_frame, 
            text="Отмена", 
            command=self.cancel
        ).pack(side=tk.RIGHT)
    
    def load_users(self):
        """Загрузка списка пользователей"""
        try:
            users = self.library_system.user_manager.get_all_users()
            user_names = [f"{user.first_name} {user.last_name} ({user.username})" for user in users]
            self.user_combo['values'] = user_names
            if user_names:
                self.user_combo.current(0)
            self.users = users
        except Exception as e:
            logger.error(f"Ошибка загрузки пользователей: {e}")
    
    def load_books(self):
        """Загрузка списка книг"""
        try:
            books = self.library_system.book_manager.get_all_books()
            book_titles = [f"{book.title} ({book.author})" for book in books]
            self.book_combo['values'] = book_titles
            if book_titles:
                self.book_combo.current(0)
            self.books = books
        except Exception as e:
            logger.error(f"Ошибка загрузки книг: {e}")
    
    def execute_transaction(self):
        """Выполнение транзакции"""
        try:
            # Получение выбранных значений
            user_index = self.user_combo.current()
            book_index = self.book_combo.current()
            
            if user_index == -1 or book_index == -1:
                messagebox.showerror("Ошибка", "Выберите пользователя и книгу")
                return
            
            user = self.users[user_index]
            book = self.books[book_index]
            
            # Создание транзакции
            transaction = Transaction()
            transaction.user_id = user.id
            transaction.book_id = book.id
            transaction.transaction_type = self.transaction_type
            transaction.transaction_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            transaction.notes = self.notes_text.get("1.0", tk.END).strip()
            
            # Установка даты возврата для выдачи
            if self.transaction_type == TransactionType.BORROW:
                due_date_str = self.due_date_entry.get().strip()
                if due_date_str:
                    transaction.due_date = due_date_str
            
            # Выполнение транзакции в базе данных
            if self.library_system.transaction_manager.create_transaction(transaction):
                # Обновление статуса книги
                if self.transaction_type == TransactionType.BORROW:
                    book.status = BookStatus.BORROWED
                    self.library_system.book_manager.update_book(book)
                elif self.transaction_type == TransactionType.RETURN:
                    book.status = BookStatus.AVAILABLE
                    self.library_system.book_manager.update_book(book)
                
                messagebox.showinfo("Успех", "Транзакция выполнена успешно")
                self.result = True
                self.top.destroy()
            else:
                messagebox.showerror("Ошибка", "Не удалось выполнить транзакцию")
                
        except Exception as e:
            logger.error(f"Ошибка выполнения транзакции: {e}")
            messagebox.showerror("Ошибка", "Произошла ошибка при выполнении транзакции")
    
    def cancel(self):
        """Отмена операции"""
        self.top.destroy()


class BookDetailsDialog:
    """Диалоговое окно с деталями книги"""
    
    def __init__(self, parent, book: Book):
        self.top = tk.Toplevel(parent)
        self.top.title(f"Детали книги: {book.title}")
        self.top.geometry("500x400")
        self.top.transient(parent)
        self.top.grab_set()
        
        self.book = book
        self.create_widgets()
        
        # Центрирование окна
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        # Основная рамка
        main_frame = ttk.Frame(self.top, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        ttk.Label(
            main_frame, 
            text=self.book.title, 
            style='Title.TLabel'
        ).pack(pady=(0, 20))
        
        # Информация о книге
        info_frame = ttk.LabelFrame(main_frame, text="Информация о книге", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        # Создание пар ключ-значение
        info_pairs = [
            ("Автор:", self.book.author),
            ("ISBN:", self.book.isbn),
            ("Год публикации:", str(self.book.publication_year) if self.book.publication_year else ""),
            ("Жанр:", self.book.genre),
            ("Издатель:", self.book.publisher),
            ("Страниц:", str(self.book.pages) if self.book.pages else ""),
            ("Язык:", self.book.language),
            ("Расположение:", self.book.location),
            ("Статус:", self.book.status.value if self.book.status else ""),
        ]
        
        for i, (label, value) in enumerate(info_pairs):
            ttk.Label(info_frame, text=label, font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky=tk.W, pady=2
            )
            ttk.Label(info_frame, text=value or "Не указано").grid(
                row=i, column=1, sticky=tk.W, pady=2, padx=(10, 0)
            )
        
        # Описание
        if self.book.description:
            ttk.Label(info_frame, text="Описание:", font=('Arial', 10, 'bold')).grid(
                row=len(info_pairs), column=0, sticky=tk.NW, pady=2
            )
            description_text = tk.Text(
                info_frame, 
                width=40, 
                height=5, 
                wrap=tk.WORD,
                state='disabled'
            )
            description_text.grid(
                row=len(info_pairs), column=1, 
                sticky=tk.W, pady=2, padx=(10, 0)
            )
            description_text.config(state='normal')
            description_text.insert("1.0", self.book.description)
            description_text.config(state='disabled')
        
        # Кнопка закрытия
        ttk.Button(
            main_frame, 
            text="Закрыть", 
            command=self.top.destroy
        ).pack(pady=(20, 0))


class RegistrationDialog:
    """Диалоговое окно регистрации"""
    
    def __init__(self, parent, user_manager: UserManager):
        self.top = tk.Toplevel(parent)
        self.top.title("Регистрация нового пользователя")
        self.top.geometry("400x400")
        self.top.transient(parent)
        self.top.grab_set()
        
        self.user_manager = user_manager
        self.result = False
        
        self.create_widgets()
        
        # Центрирование окна
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        # Основная рамка
        main_frame = ttk.Frame(self.top, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Форма регистрации
        form_frame = ttk.LabelFrame(main_frame, text="Регистрационная информация", padding=10)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Имя пользователя
        ttk.Label(form_frame, text="Имя пользователя:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.username_entry = ttk.Entry(form_frame, width=30)
        self.username_entry.grid(row=0, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Email
        ttk.Label(form_frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.email_entry = ttk.Entry(form_frame, width=30)
        self.email_entry.grid(row=1, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Пароль
        ttk.Label(form_frame, text="Пароль:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.password_entry = ttk.Entry(form_frame, width=30, show="*")
        self.password_entry.grid(row=2, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Подтверждение пароля
        ttk.Label(form_frame, text="Подтвердите пароль:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.confirm_password_entry = ttk.Entry(form_frame, width=30, show="*")
        self.confirm_password_entry.grid(row=3, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Имя
        ttk.Label(form_frame, text="Имя:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.first_name_entry = ttk.Entry(form_frame, width=30)
        self.first_name_entry.grid(row=4, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Фамилия
        ttk.Label(form_frame, text="Фамилия:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.last_name_entry = ttk.Entry(form_frame, width=30)
        self.last_name_entry.grid(row=5, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Телефон
        ttk.Label(form_frame, text="Телефон:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.phone_entry = ttk.Entry(form_frame, width=30)
        self.phone_entry.grid(row=6, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Адрес
        ttk.Label(form_frame, text="Адрес:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.address_entry = ttk.Entry(form_frame, width=30)
        self.address_entry.grid(row=7, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(
            button_frame, 
            text="Зарегистрироваться", 
            command=self.register_user
        ).pack(side=tk.RIGHT, padx=(10, 0))
        
        ttk.Button(
            button_frame, 
            text="Отмена", 
            command=self.cancel
        ).pack(side=tk.RIGHT)
    
    def register_user(self):
        """Регистрация пользователя"""
        try:
            # Получение данных из полей
            username = self.username_entry.get().strip()
            email = self.email_entry.get().strip()
            password = self.password_entry.get()
            confirm_password = self.confirm_password_entry.get()
            first_name = self.first_name_entry.get().strip()
            last_name = self.last_name_entry.get().strip()
            
            # Проверка обязательных полей
            if not username or not email or not password or not first_name or not last_name:
                messagebox.showerror("Ошибка", "Все обязательные поля должны быть заполнены")
                return
            
            # Проверка совпадения паролей
            if password != confirm_password:
                messagebox.showerror("Ошибка", "Пароли не совпадают")
                return
            
            # Проверка email
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                messagebox.showerror("Ошибка", "Неверный формат email")
                return
            
            # Проверка уникальности имени пользователя и email
            if self.user_manager.get_user_by_username(username):
                messagebox.showerror("Ошибка", "Пользователь с таким именем уже существует")
                return
            
            existing_user = self.user_manager.get_user_by_username(username)
            if existing_user:
                messagebox.showerror("Ошибка", "Пользователь с таким именем уже существует")
                return
            
            # Создание нового пользователя
            user = User()
            user.username = username
            user.email = email
            user.password_hash = self.user_manager.db_manager.hash_password(password)
            user.first_name = first_name
            user.last_name = last_name
            user.phone = self.phone_entry.get().strip()
            user.address = self.address_entry.get().strip()
            user.role = UserRole.MEMBER  # По умолчанию обычный пользователь
            user.is_active = True
            
            # Сохранение в базу данных
            if self.user_manager.add_user(user):
                messagebox.showinfo("Успех", "Регистрация прошла успешно")
                self.result = True
                self.top.destroy()
            else:
                messagebox.showerror("Ошибка", "Не удалось зарегистрировать пользователя")
                
        except Exception as e:
            logger.error(f"Ошибка регистрации пользователя: {e}")
            messagebox.showerror("Ошибка", "Произошла ошибка при регистрации")
    
    def cancel(self):
        """Отмена операции"""
        self.top.destroy()


class OverdueDialog:
    """Диалоговое окно просроченных транзакций"""
    
    def __init__(self, parent, transactions: List[Transaction], user_manager: UserManager, book_manager: BookManager):
        self.top = tk.Toplevel(parent)
        self.top.title("Просроченные транзакции")
        self.top.geometry("800x500")
        self.top.transient(parent)
        self.top.grab_set()
        
        self.transactions = transactions
        self.user_manager = user_manager
        self.book_manager = book_manager
        
        self.create_widgets()
        
        # Центрирование окна
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        # Основная рамка
        main_frame = ttk.Frame(self.top, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        ttk.Label(
            main_frame, 
            text="Просроченные транзакции", 
            style='Title.TLabel'
        ).pack(pady=(0, 10))
        
        # Таблица просроченных транзакций
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Создание таблицы
        columns = ('ID', 'Пользователь', 'Книга', 'Дата выдачи', 'Срок возврата', 'Просрочка', 'Штраф')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        # Настройка заголовков
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        # Настройка размеров колонок
        self.tree.column('ID', width=50)
        self.tree.column('Пользователь', width=150)
        self.tree.column('Книга', width=200)
        self.tree.column('Дата выдачи', width=120)
        self.tree.column('Срок возврата', width=120)
        self.tree.column('Просрочка', width=100)
        self.tree.column('Штраф', width=80)
        
        # Полосы прокрутки
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Размещение элементов
        self.tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Заполнение таблицы данными
        self.populate_table()
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            button_frame, 
            text="Закрыть", 
            command=self.top.destroy
        ).pack(side=tk.RIGHT)
    
    def populate_table(self):
        """Заполнение таблицы данными"""
        # Очистка таблицы
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Добавление данных
        for transaction in self.transactions:
            # Получение информации о пользователе и книге
            user = self.user_manager.get_user_by_id(transaction.user_id)
            book = self.book_manager.get_book_by_id(transaction.book_id)
            
            if user and book:
                # Расчет просрочки
                due_date = datetime.datetime.strptime(transaction.due_date, "%Y-%m-%d %H:%M:%S")
                days_overdue = (datetime.datetime.now() - due_date).days
                
                # Расчет штрафа (например, 10 рублей в день)
                fine_amount = max(0, days_overdue * 10.0)
                
                self.tree.insert('', tk.END, values=(
                    transaction.id,
                    f"{user.first_name} {user.last_name}",
                    book.title,
                    transaction.transaction_date[:10],
                    transaction.due_date[:10],
                    f"{days_overdue} дней",
                    f"{fine_amount:.2f} руб."
                ))


class BooksReportDialog:
    """Диалоговое окно отчета по книгам"""
    
    def __init__(self, parent, report: Dict):
        self.top = tk.Toplevel(parent)
        self.top.title("Отчет по книгам")
        self.top.geometry("600x500")
        self.top.transient(parent)
        self.top.grab_set()
        
        self.report = report
        self.create_widgets()
        
        # Центрирование окна
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        # Основная рамка
        main_frame = ttk.Frame(self.top, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        ttk.Label(
            main_frame, 
            text="Отчет по книгам", 
            style='Title.TLabel'
        ).pack(pady=(0, 20))
        
        # Основные показатели
        stats_frame = ttk.LabelFrame(main_frame, text="Основные показатели", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(stats_frame, text=f"Всего книг: {self.report.get('total_books', 0)}").pack(anchor=tk.W)
        
        # Статусы книг
        status_frame = ttk.LabelFrame(main_frame, text="Книги по статусам", padding=10)
        status_frame.pack(fill=tk.X, pady=(0, 20))
        
        for status, count in self.report.get('books_by_status', {}).items():
            ttk.Label(status_frame, text=f"{status}: {count}").pack(anchor=tk.W)
        
        # Топ авторов
        authors_frame = ttk.LabelFrame(main_frame, text="Топ 10 авторов", padding=10)
        authors_frame.pack(fill=tk.X, pady=(0, 20))
        
        for author, count in list(self.report.get('top_authors', {}).items())[:10]:
            ttk.Label(authors_frame, text=f"{author}: {count}").pack(anchor=tk.W)
        
        # Кнопка закрытия
        ttk.Button(
            main_frame, 
            text="Закрыть", 
            command=self.top.destroy
        ).pack(pady=(20, 0))


class UsersReportDialog:
    """Диалоговое окно отчета по пользователям"""
    
    def __init__(self, parent, report: Dict):
        self.top = tk.Toplevel(parent)
        self.top.title("Отчет по пользователям")
        self.top.geometry("500x400")
        self.top.transient(parent)
        self.top.grab_set()
        
        self.report = report
        self.create_widgets()
        
        # Центрирование окна
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        # Основная рамка
        main_frame = ttk.Frame(self.top, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        ttk.Label(
            main_frame, 
            text="Отчет по пользователям", 
            style='Title.TLabel'
        ).pack(pady=(0, 20))
        
        # Основные показатели
        stats_frame = ttk.LabelFrame(main_frame, text="Основные показатели", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(stats_frame, text=f"Всего пользователей: {self.report.get('total_users', 0)}").pack(anchor=tk.W)
        ttk.Label(stats_frame, text=f"Активных пользователей (месяц): {self.report.get('active_users', 0)}").pack(anchor=tk.W)
        
        # Пользователи по ролям
        roles_frame = ttk.LabelFrame(main_frame, text="Пользователи по ролям", padding=10)
        roles_frame.pack(fill=tk.X, pady=(0, 20))
        
        for role, count in self.report.get('users_by_role', {}).items():
            ttk.Label(roles_frame, text=f"{role}: {count}").pack(anchor=tk.W)
        
        # Кнопка закрытия
        ttk.Button(
            main_frame, 
            text="Закрыть", 
            command=self.top.destroy
        ).pack(pady=(20, 0))


class TransactionsReportDialog:
    """Диалоговое окно отчета по транзакциям"""
    
    def __init__(self, parent, report: Dict):
        self.top = tk.Toplevel(parent)
        self.top.title("Отчет по транзакциям")
        self.top.geometry("500x400")
        self.top.transient(parent)
        self.top.grab_set()
        
        self.report = report
        self.create_widgets()
        
        # Центрирование окна
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        # Основная рамка
        main_frame = ttk.Frame(self.top, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        ttk.Label(
            main_frame, 
            text="Отчет по транзакциям", 
            style='Title.TLabel'
        ).pack(pady=(0, 20))
        
        # Основные показатели
        stats_frame = ttk.LabelFrame(main_frame, text="Основные показатели", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(stats_frame, text=f"Всего транзакций: {self.report.get('total_transactions', 0)}").pack(anchor=tk.W)
        ttk.Label(stats_frame, text=f"Активных займов: {self.report.get('active_borrows', 0)}").pack(anchor=tk.W)
        ttk.Label(stats_frame, text=f"Просроченных книг: {self.report.get('overdue_books', 0)}").pack(anchor=tk.W)
        
        # Транзакции по типам
        types_frame = ttk.LabelFrame(main_frame, text="Транзакции по типам", padding=10)
        types_frame.pack(fill=tk.X, pady=(0, 20))
        
        for transaction_type, count in self.report.get('transactions_by_type', {}).items():
            ttk.Label(types_frame, text=f"{transaction_type}: {count}").pack(anchor=tk.W)
        
        # Кнопка закрытия
        ttk.Button(
            main_frame, 
            text="Закрыть", 
            command=self.top.destroy
        ).pack(pady=(20, 0))


class DocumentationDialog:
    """Диалоговое окно документации"""
    
    def __init__(self, parent, documentation: str):
        self.top = tk.Toplevel(parent)
        self.top.title("Документация")
        self.top.geometry("700x500")
        self.top.transient(parent)
        self.top.grab_set()
        
        self.documentation = documentation
        self.create_widgets()
        
        # Центрирование окна
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        # Основная рамка
        main_frame = ttk.Frame(self.top, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Текст документации
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # Создание текстового виджета с прокруткой
        text_widget = tk.Text(
            text_frame, 
            wrap=tk.WORD, 
            state='disabled',
            font=('Arial', 10)
        )
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # Размещение элементов
        text_widget.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        
        # Вставка текста документации
        text_widget.config(state='normal')
        text_widget.insert('1.0', self.documentation)
        text_widget.config(state='disabled')
        
        # Кнопка закрытия
        ttk.Button(
            main_frame, 
            text="Закрыть", 
            command=self.top.destroy
        ).pack(pady=(10, 0))


def main():
    """Основная функция запуска приложения"""
    try:
        # Создание и запуск системы
        library_system = LibrarySystem()
        library_system.run()
    except Exception as e:
        logger.error(f"Критическая ошибка приложения: {e}")
        messagebox.showerror(
            "Критическая ошибка", 
            f"Произошла критическая ошибка приложения:\n{e}\n\nПриложение будет закрыто."
        )


if __name__ == "__main__":
    main()
