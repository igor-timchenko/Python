import json
import os
import datetime
from uuid import uuid4
from typing import List, Dict, Optional, Tuple

class Book:
    def __init__(
        self, 
        title: str, 
        author: str, 
        isbn: str, 
        year: int,
        book_id: str = None,
        status: str = "available"
    ):
        self.id = book_id or str(uuid4())
        self.title = title
        self.author = author
        self.isbn = isbn
        self.year = year
        self.status = status  # available, reserved, borrowed, archived
        self.borrow_history = []
        self.reserved_by = None
        self.due_date = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "isbn": self.isbn,
            "year": self.year,
            "status": self.status,
            "borrow_history": self.borrow_history,
            "reserved_by": self.reserved_by,
            "due_date": self.due_date.isoformat() if self.due_date else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Book':
        book = cls(
            title=data["title"],
            author=data["author"],
            isbn=data["isbn"],
            year=data["year"],
            book_id=data["id"],
            status=data["status"]
        )
        book.borrow_history = data["borrow_history"]
        book.reserved_by = data["reserved_by"]
        if data["due_date"]:
            book.due_date = datetime.datetime.fromisoformat(data["due_date"])
        return book

    def __str__(self) -> str:
        return f"{self.title} by {self.author} ({self.year}) [{self.status.upper()}]"

class User:
    def __init__(
        self,
        name: str,
        email: str,
        user_type: str = "member",  # member, librarian, admin
        user_id: str = None
    ):
        self.id = user_id or str(uuid4())
        self.name = name
        self.email = email
        self.user_type = user_type
        self.borrowed_books = []
        self.reserved_books = []
        self.fines = 0.0  # in currency units
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "user_type": self.user_type,
            "borrowed_books": self.borrowed_books,
            "reserved_books": self.reserved_books,
            "fines": self.fines
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        user = cls(
            name=data["name"],
            email=data["email"],
            user_type=data["user_type"],
            user_id=data["id"]
        )
        user.borrowed_books = data["borrowed_books"]
        user.reserved_books = data["reserved_books"]
        user.fines = data["fines"]
        return user

    def __str__(self) -> str:
        return f"{self.name} ({self.email}) - {self.user_type}"

class Library:
    MAX_BOOKS_PER_USER = 5
    BORROW_PERIOD_DAYS = 14
    FINE_PER_DAY = 1.0
    
    def __init__(self, storage_file: str = "library_data.json"):
        self.storage_file = storage_file
        self.books: Dict[str, Book] = {}
        self.users: Dict[str, User] = {}
        self.load_data()
    
    def add_book(self, title: str, author: str, isbn: str, year: int) -> Book:
        book = Book(title, author, isbn, year)
        self.books[book.id] = book
        self.save_data()
        return book
    
    def register_user(self, name: str, email: str, user_type: str = "member") -> User:
        user = User(name, email, user_type)
        self.users[user.id] = user
        self.save_data()
        return user
    
    def find_book(self, **kwargs) -> List[Book]:
        results = []
        for book in self.books.values():
            match = True
            for key, value in kwargs.items():
                if getattr(book, key, None) != value:
                    match = False
                    break
            if match:
                results.append(book)
        return results
    
    def find_user(self, **kwargs) -> List[User]:
        results = []
        for user in self.users.values():
            match = True
            for key, value in kwargs.items():
                if getattr(user, key, None) != value:
                    match = False
                    break
            if match:
                results.append(user)
        return results
    
    def borrow_book(self, user_id: str, book_id: str) -> Tuple[bool, str]:
        user = self.users.get(user_id)
        book = self.books.get(book_id)
        
        if not user or not book:
            return False, "User or book not found"
        
        if book.status != "available":
            return False, "Book is not available"
        
        if len(user.borrowed_books) >= self.MAX_BOOKS_PER_USER:
            return False, "User has reached the borrowing limit"
        
        if user.fines > 0:
            return False, "User has outstanding fines"
        
        book.status = "borrowed"
        book.due_date = datetime.datetime.now() + datetime.timedelta(days=self.BORROW_PERIOD_DAYS)
        book.borrow_history.append({
            "user_id": user_id,
            "borrow_date": datetime.datetime.now().isoformat(),
            "due_date": book.due_date.isoformat()
        })
        
        user.borrowed_books.append(book_id)
        
        self.save_data()
        return True, "Book borrowed successfully"
    
    def return_book(self, user_id: str, book_id: str) -> Tuple[bool, str]:
        user = self.users.get(user_id)
        book = self.books.get(book_id)
        
        if not user or not book:
            return False, "User or book not found"
        
        if book_id not in user.borrowed_books:
            return False, "This book is not borrowed by this user"
        
        # Calculate fines if any
        if datetime.datetime.now() > book.due_date:
            days_overdue = (datetime.datetime.now() - book.due_date).days
            fine = days_overdue * self.FINE_PER_DAY
            user.fines += fine
        
        book.status = "available"
        book.due_date = None
        
        # Update borrow history
        for record in book.borrow_history:
            if record["user_id"] == user_id and not record.get("return_date"):
                record["return_date"] = datetime.datetime.now().isoformat()
        
        user.borrowed_books.remove(book_id)
        self.save_data()
        return True, "Book returned successfully"
    
    def reserve_book(self, user_id: str, book_id: str) -> Tuple[bool, str]:
        user = self.users.get(user_id)
        book = self.books.get(book_id)
        
        if not user or not book:
            return False, "User or book not found"
        
        if book.status != "available":
            return False, "Book is not available for reservation"
        
        if book_id in user.reserved_books:
            return False, "Book already reserved by this user"
        
        book.status = "reserved"
        book.reserved_by = user_id
        user.reserved_books.append(book_id)
        
        self.save_data()
        return True, "Book reserved successfully"
    
    def cancel_reservation(self, user_id: str, book_id: str) -> Tuple[bool, str]:
        user = self.users.get(user_id)
        book = self.books.get(book_id)
        
        if not user or not book:
            return False, "User or book not found"
        
        if book_id not in user.reserved_books:
            return False, "Book not reserved by this user"
        
        book.status = "available"
        book.reserved_by = None
        user.reserved_books.remove(book_id)
        
        self.save_data()
        return True, "Reservation cancelled successfully"
    
    def pay_fine(self, user_id: str, amount: float) -> Tuple[bool, str]:
        user = self.users.get(user_id)
        if not user:
            return False, "User not found"
        
        if amount > user.fines:
            return False, "Payment exceeds outstanding fines"
        
        user.fines -= amount
        self.save_data()
        return True, f"Payment successful. Remaining fines: {user.fines}"
    
    def generate_report(self, report_type: str = "all") -> Dict:
        report = {
            "total_books": len(self.books),
            "available_books": 0,
            "borrowed_books": 0,
            "reserved_books": 0,
            "overdue_books": 0,
            "total_users": len(self.users),
            "users_with_fines": 0,
            "total_fines": 0.0
        }
        
        for book in self.books.values():
            if book.status == "available":
                report["available_books"] += 1
            elif book.status == "borrowed":
                report["borrowed_books"] += 1
                if book.due_date and datetime.datetime.now() > book.due_date:
                    report["overdue_books"] += 1
            elif book.status == "reserved":
                report["reserved_books"] += 1
        
        for user in self.users.values():
            report["total_fines"] += user.fines
            if user.fines > 0:
                report["users_with_fines"] += 1
        
        return report
    
    def save_data(self):
        data = {
            "books": [book.to_dict() for book in self.books.values()],
            "users": [user.to_dict() for user in self.users.values()]
        }
        with open(self.storage_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def load_data(self):
        if not os.path.exists(self.storage_file):
            return
        
        try:
            with open(self.storage_file, "r") as f:
                data = json.load(f)
            
            self.books = {}
            for book_data in data.get("books", []):
                book = Book.from_dict(book_data)
                self.books[book.id] = book
            
            self.users = {}
            for user_data in data.get("users", []):
                user = User.from_dict(user_data)
                self.users[user.id] = user
        except Exception as e:
            print(f"Error loading data: {str(e)}")

class LibraryCLI:
    def __init__(self):
        self.library = Library()
        self.current_user = None
    
    def run(self):
        while True:
            if not self.current_user:
                self.show_main_menu()
            elif self.current_user.user_type == "member":
                self.show_member_menu()
            else:
                self.show_staff_menu()
    
    def show_main_menu(self):
        print("\n===== Library Management System =====")
        print("1. Login")
        print("2. Register")
        print("3. Search Books")
        print("4. Exit")
        
        choice = input("Enter your choice: ")
        
        if choice == "1":
            self.login()
        elif choice == "2":
            self.register_user()
        elif choice == "3":
            self.search_books()
        elif choice == "4":
            print("Goodbye!")
            exit()
        else:
            print("Invalid choice. Please try again.")
    
    def show_member_menu(self):
        print(f"\n===== Welcome, {self.current_user.name} =====")
        print("1. Search Books")
        print("2. Borrow Book")
        print("3. Return Book")
        print("4. Reserve Book")
        print("5. Cancel Reservation")
        print("6. Pay Fines")
        print("7. View My Books")
        print("8. Logout")
        
        choice = input("Enter your choice: ")
        
        if choice == "1":
            self.search_books()
        elif choice == "2":
            self.borrow_book()
        elif choice == "3":
            self.return_book()
        elif choice == "4":
            self.reserve_book()
        elif choice == "5":
            self.cancel_reservation()
        elif choice == "6":
            self.pay_fines()
        elif choice == "7":
            self.view_user_books()
        elif choice == "8":
            self.current_user = None
        else:
            print("Invalid choice. Please try again.")
    
    def show_staff_menu(self):
        print(f"\n===== Staff Portal: {self.current_user.name} =====")
        print("1. Search Books")
        print("2. Add Book")
        print("3. Manage Users")
        print("4. Generate Report")
        print("5. View All Books")
        print("6. Logout")
        
        choice = input("Enter your choice: ")
        
        if choice == "1":
            self.search_books()
        elif choice == "2":
            self.add_book()
        elif choice == "3":
            self.manage_users()
        elif choice == "4":
            self.generate_report()
        elif choice == "5":
            self.view_all_books()
        elif choice == "6":
            self.current_user = None
        else:
            print("Invalid choice. Please try again.")
    
    def login(self):
        email = input("Enter email: ")
        users = self.library.find_user(email=email)
        
        if not users:
            print("User not found")
            return
        
        self.current_user = users[0]
        print(f"Welcome, {self.current_user.name}!")
    
    def register_user(self):
        name = input("Name: ")
        email = input("Email: ")
        user_type = input("User type (member/librarian/admin): ").lower()
        
        if user_type not in ["member", "librarian", "admin"]:
            print("Invalid user type")
            return
        
        user = self.library.register_user(name, email, user_type)
        print(f"User registered successfully! ID: {user.id}")
    
    def add_book(self):
        if not self.current_user or self.current_user.user_type == "member":
            print("Permission denied")
            return
        
        title = input("Title: ")
        author = input("Author: ")
        isbn = input("ISBN: ")
        year = int(input("Year: "))
        
        book = self.library.add_book(title, author, isbn, year)
        print(f"Book added successfully! ID: {book.id}")
    
    def search_books(self):
        print("\n===== Search Books =====")
        print("1. By Title")
        print("2. By Author")
        print("3. By ISBN")
        print("4. By Year")
        print("5. By Status")
        print("6. Back")
        
        choice = input("Enter your choice: ")
        
        if choice == "6":
            return
        
        search_field = {
            "1": "title",
            "2": "author",
            "3": "isbn",
            "4": "year",
            "5": "status"
        }.get(choice)
        
        if not search_field:
            print("Invalid choice")
            return
        
        value = input(f"Enter {search_field}: ")
        
        if search_field == "year":
            try:
                value = int(value)
            except ValueError:
                print("Invalid year")
                return
        
        books = self.library.find_book(**{search_field: value})
        
        if not books:
            print("No books found")
            return
        
        print("\nSearch Results:")
        for i, book in enumerate(books, 1):
            status_info = f" - Due: {book.due_date.strftime('%Y-%m-%d')}" if book.due_date else ""
            print(f"{i}. {book} {status_info}")
    
    def borrow_book(self):
        if not self.current_user:
            print("Please login first")
            return
        
        book_id = input("Enter book ID: ")
        success, message = self.library.borrow_book(self.current_user.id, book_id)
        print(message)
    
    def return_book(self):
        if not self.current_user:
            print("Please login first")
            return
        
        book_id = input("Enter book ID: ")
        success, message = self.library.return_book(self.current_user.id, book_id)
        print(message)
    
    def reserve_book(self):
        if not self.current_user:
            print("Please login first")
            return
        
        book_id = input("Enter book ID: ")
        success, message = self.library.reserve_book(self.current_user.id, book_id)
        print(message)
    
    def cancel_reservation(self):
        if not self.current_user:
            print("Please login first")
            return
        
        book_id = input("Enter book ID: ")
        success, message = self.library.cancel_reservation(self.current_user.id, book_id)
        print(message)
    
    def pay_fines(self):
        if not self.current_user:
            print("Please login first")
            return
        
        print(f"Current fines: ${self.current_user.fines:.2f}")
        amount = float(input("Enter amount to pay: "))
        success, message = self.library.pay_fine(self.current_user.id, amount)
        print(message)
    
    def view_user_books(self):
        if not self.current_user:
            print("Please login first")
            return
        
        print("\n===== Your Books =====")
        print("Borrowed Books:")
        for book_id in self.current_user.borrowed_books:
            book = self.library.books.get(book_id)
            if book:
                due_info = f" - Due: {book.due_date.strftime('%Y-%m-%d')}" if book.due_date else ""
                print(f"- {book.title} by {book.author}{due_info}")
        
        print("\nReserved Books:")
        for book_id in self.current_user.reserved_books:
            book = self.library.books.get(book_id)
            if book:
                print(f"- {book.title} by {book.author}")
    
    def view_all_books(self):
        if not self.current_user or self.current_user.user_type == "member":
            print("Permission denied")
            return
        
        print("\n===== All Books in Library =====")
        for book in self.library.books.values():
            status_info = ""
            if book.status == "borrowed" and book.due_date:
                status_info = f" - Due: {book.due_date.strftime('%Y-%m-%d')}"
            elif book.status == "reserved":
                user = self.library.users.get(book.reserved_by)
                if user:
                    status_info = f" - Reserved by: {user.name}"
            
            print(f"- [{book.id}] {book}{status_info}")
    
    def generate_report(self):
        if not self.current_user or self.current_user.user_type == "member":
            print("Permission denied")
            return
        
        report = self.library.generate_report()
        print("\n===== Library Report =====")
        print(f"Total Books: {report['total_books']}")
        print(f"Available Books: {report['available_books']}")
        print(f"Borrowed Books: {report['borrowed_books']}")
        print(f"Reserved Books: {report['reserved_books']}")
        print(f"Overdue Books: {report['overdue_books']}")
        print(f"Total Users: {report['total_users']}")
        print(f"Users with Fines: {report['users_with_fines']}")
        print(f"Total Fines: ${report['total_fines']:.2f}")
    
    def manage_users(self):
        if not self.current_user or self.current_user.user_type not in ["librarian", "admin"]:
            print("Permission denied")
            return
        
        print("\n===== User Management =====")
        print("1. Search Users")
        print("2. View User Details")
        print("3. Back")
        
        choice = input("Enter your choice: ")
        
        if choice == "3":
            return
        
        if choice == "1":
            search_term = input("Search by name or email: ")
            found_users = []
            for user in self.library.users.values():
                if search_term.lower() in user.name.lower() or search_term.lower() in user.email.lower():
                    found_users.append(user)
            
            if not found_users:
                print("No users found")
                return
            
            print("\nSearch Results:")
            for i, user in enumerate(found_users, 1):
                print(f"{i}. {user.name} - {user.email} ({user.user_type})")
        
        elif choice == "2":
            user_id = input("Enter user ID: ")
            user = self.library.users.get(user_id)
            if not user:
                print("User not found")
                return
            
            print("\n===== User Details =====")
            print(f"ID: {user.id}")
            print(f"Name: {user.name}")
            print(f"Email: {user.email}")
            print(f"Type: {user.user_type}")
            print(f"Fines: ${user.fines:.2f}")
            
            print("\nBorrowed Books:")
            for book_id in user.borrowed_books:
                book = self.library.books.get(book_id)
                if book:
                    due_info = f" - Due: {book.due_date.strftime('%Y-%m-%d')}" if book.due_date else ""
                    print(f"- {book.title}{due_info}")
            
            print("\nReserved Books:")
            for book_id in user.reserved_books:
                book = self.library.books.get(book_id)
                if book:
                    print(f"- {book.title}")

if __name__ == "__main__":
    cli = LibraryCLI()
    cli.run()
