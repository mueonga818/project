import os
import re
import sqlite3
import tkinter as tk
import requests
import json
from datetime import date, datetime
from collections import Counter
from tkinter import filedialog, messagebox, simpledialog, ttk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
ROOT_DB = os.path.abspath(os.path.join(BASE_DIR, os.pardir, "vocab.db"))
DEFAULT_DB = os.path.join(DATA_DIR, "vocab.db")


def choose_db_path():
    if os.path.exists(ROOT_DB):
        if os.access(ROOT_DB, os.W_OK):
            return ROOT_DB
        if os.access(DATA_DIR, os.W_OK):
            return DEFAULT_DB
        return ROOT_DB
    if os.access(DATA_DIR, os.W_OK):
        return DEFAULT_DB
    return ROOT_DB


DB_FILE = choose_db_path()
PAGE_CHARS = 1800

CEFR_WORDS = {
    "A1": {
        "book", "read", "page", "word", "easy", "write", "see", "go", "come", "like",
        "start", "play", "school", "family", "friend", "work", "home", "happy", "big", "small",
        "good", "bad", "have", "know", "want", "need", "look", "think", "help", "day",
    },
    "A2": {
        "travel", "lesson", "answer", "question", "change", "river", "market", "minute", "object",
        "place", "letter", "answer", "study", "teacher", "story", "picture", "family", "music",
        "country", "summer", "winter", "kitchen", "garden", "letter", "problem", "level", "chance",
    },
    "B1": {
        "context", "culture", "process", "project", "experience", "purpose", "resource", "device",
        "condition", "either", "policy", "network", "detail", "program", "comment", "section", "chapter",
        "opinion", "result", "measure", "feature", "describe", "discussion", "event", "pattern",
    },
    "B2": {
        "analysis", "concept", "complex", "creative", "function", "generation", "impact", "method",
        "policy", "strategy", "structure", "technology", "tradition", "variation", "contextual",
        "environment", "characteristic", "challenge", "communication", "demonstrate",
    },
    "C1": {
        "abstract", "comprehensive", "consequence", "constituent", "initiative", "interpretation",
        "investment", "negotiation", "perspective", "priority", "promotion", "reinforcement", "scope",
        "significant", "subsequent", "transformation", "vocabulary", "visually",
    },
    "C2": {
        "accommodation", "advocacy", "belligerent", "coincidence", "discrepancy", "enhancement",
        "formulation", "hypothesis", "meticulous", "phenomenon", "predominantly", "speculation",
        "substantiation", "transcendence", "ubiquitous", "veneration",
    },
}

COMMON_STOPWORDS = {
    "the", "and", "that", "with", "from", "this", "have", "were", "been", "what",
    "when", "where", "which", "their", "there", "would", "could", "should", "about",
}


class ReadingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("영어 독서 기록장")
        self.geometry("1180x760")
        self.configure(bg="#F4F7FF")
        self.resizable(True, True)

        self.conn = sqlite3.connect(DB_FILE)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.init_db()

        self.selected_book_id = None
        self.current_quiz_words = []
        self.current_quiz_index = 0
        self.current_quiz_answer = ""

        self.create_ui()
        self.load_books()
        self.load_vocab()
        self.load_history()
        self.load_word_lists()

    def init_db(self):
        self.cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                file_path TEXT,
                shelf TEXT,
                finished INTEGER DEFAULT 0,
                note TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                book_id INTEGER,
                start_page INTEGER,
                end_page INTEGER,
                summary TEXT,
                created_at TEXT,
                FOREIGN KEY(book_id) REFERENCES books(id)
            );
            CREATE TABLE IF NOT EXISTS vocab (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT,
                meaning TEXT,
                pos TEXT,
                example TEXT,
                source TEXT,
                book_id INTEGER,
                date TEXT,
                cefr TEXT,
                FOREIGN KEY(book_id) REFERENCES books(id)
            );
            CREATE TABLE IF NOT EXISTS word_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS list_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER,
                vocab_id INTEGER,
                FOREIGN KEY(list_id) REFERENCES word_lists(id),
                FOREIGN KEY(vocab_id) REFERENCES vocab(id)
            );
            """
        )
        self.conn.commit()
        self.apply_migrations()

    def table_columns(self, table_name):
        rows = self.cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        return [row["name"] for row in rows]

    def apply_migrations(self):
        tables = [row[0] for row in self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "vocab" in tables:
            vocab_cols = self.table_columns("vocab")
            if "source" not in vocab_cols:
                self.cursor.execute("ALTER TABLE vocab ADD COLUMN source TEXT")
            if "book_id" not in vocab_cols:
                self.cursor.execute("ALTER TABLE vocab ADD COLUMN book_id INTEGER")
            if "cefr" not in vocab_cols:
                self.cursor.execute("ALTER TABLE vocab ADD COLUMN cefr TEXT")
        if "sessions" in tables:
            session_cols = self.table_columns("sessions")
            if "book_id" not in session_cols:
                if "book" in session_cols:
                    self.cursor.execute("ALTER TABLE sessions RENAME TO sessions_old")
                    self.cursor.execute(
                        """
                        CREATE TABLE sessions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            date TEXT,
                            book_id INTEGER,
                            start_page INTEGER,
                            end_page INTEGER,
                            summary TEXT,
                            created_at TEXT,
                            FOREIGN KEY(book_id) REFERENCES books(id)
                        );
                        """
                    )
                    self.cursor.execute(
                        "INSERT INTO sessions (id, date, book_id, start_page, end_page, summary, created_at) "
                        "SELECT id, date, (SELECT id FROM books WHERE title = sessions_old.book LIMIT 1), "
                        "start_page, end_page, summary, created_at FROM sessions_old"
                    )
                    self.cursor.execute("DROP TABLE sessions_old")
                else:
                    self.cursor.execute("ALTER TABLE sessions ADD COLUMN book_id INTEGER")
                session_cols = self.table_columns("sessions")
            if "summary" not in session_cols:
                self.cursor.execute("ALTER TABLE sessions ADD COLUMN summary TEXT")
            if "created_at" not in session_cols:
                self.cursor.execute("ALTER TABLE sessions ADD COLUMN created_at TEXT")
        self.conn.commit()

    def create_ui(self):
        outer = tk.Frame(self, bg="#F4F7FF")
        outer.pack(fill="both", expand=True)

        nav = tk.Frame(outer, bg="#E8EFFF", width=220)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)

        self.content = tk.Frame(outer, bg="#F4F7FF")
        self.content.pack(side="left", fill="both", expand=True)

        title = tk.Label(nav, text="영어 독서 도우미", bg="#E8EFFF", fg="#1F3B8B", font=("Segoe UI", 16, "bold"))
        title.pack(pady=(20, 12), padx=16, anchor="w")

        self.nav_buttons = []
        for text, command in [("🏠 홈", self.show_home), ("📖 단어장", self.show_vocab), ("✏️ 퀴즈", self.show_quiz)]:
            btn = tk.Button(
                nav,
                text=text,
                command=command,
                anchor="w",
                relief="flat",
                bg="#FFFFFF",
                fg="#2D3A6A",
                padx=14,
                pady=12,
                font=("Segoe UI", 12, "bold"),
            )
            btn.pack(fill="x", padx=14, pady=6)
            self.nav_buttons.append(btn)

        self.frames = {
            "home": tk.Frame(self.content, bg="#F4F7FF"),
            "vocab": tk.Frame(self.content, bg="#F4F7FF"),
            "quiz": tk.Frame(self.content, bg="#F4F7FF"),
        }
        for frame in self.frames.values():
            frame.place(relwidth=1, relheight=1)

        self.build_home_frame()
        self.build_vocab_frame()
        self.build_quiz_frame()
        self.show_home()

    def build_home_frame(self):
        frame = self.frames["home"]
        header = tk.Label(frame, text="홈", bg="#F4F7FF", fg="#1F3B8B", font=("Segoe UI", 20, "bold"))
        header.pack(anchor="nw", padx=24, pady=(24, 8))

        subtitle = tk.Label(frame, text="책, 독서기록, 단어장을 한 곳에서 관리합니다.", bg="#F4F7FF", fg="#5A6279", font=("Segoe UI", 11))
        subtitle.pack(anchor="nw", padx=24)

        top_area = tk.Frame(frame, bg="#F4F7FF")
        top_area.pack(fill="x", padx=24, pady=18)

        book_panel = tk.LabelFrame(top_area, text="책장", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 11, "bold"))
        book_panel.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=4)

        self.book_listbox = tk.Listbox(book_panel, activestyle="dotbox", bd=0, highlightthickness=0, selectbackground="#D5E4FF", font=("Segoe UI", 10))
        self.book_listbox.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        self.book_listbox.bind("<<ListboxSelect>>", self.on_book_select)

        book_scroll = tk.Scrollbar(book_panel, orient="vertical", command=self.book_listbox.yview)
        book_scroll.pack(side="left", fill="y", pady=10, padx=(4, 10))
        self.book_listbox.config(yscrollcommand=book_scroll.set)

        book_right = tk.Frame(book_panel, bg="#F4F7FF")
        book_right.pack(side="left", fill="y", padx=10, pady=10)

        tk.Label(book_right, text="새 책 추가", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.new_book_title = tk.Entry(book_right, font=("Segoe UI", 10))
        self.new_book_title.pack(fill="x", pady=4)
        self.new_shelf = tk.Entry(book_right, font=("Segoe UI", 10))
        self.new_shelf.insert(0, "기본")
        self.new_shelf.pack(fill="x", pady=4)

        tk.Button(book_right, text="텍스트 파일 선택", command=self.add_book_file, bg="#4B6FFB", fg="#FFFFFF", relief="flat", font=("Segoe UI", 10, "bold"), padx=12, pady=8).pack(fill="x", pady=6)
        tk.Button(book_right, text="선택한 책 수정", command=self.update_book_info, bg="#FFFFFF", fg="#2D3A6A", relief="groove", font=("Segoe UI", 10, "bold"), padx=12, pady=8).pack(fill="x", pady=6)

        self.book_detail_text = tk.Text(book_right, width=34, height=10, wrap="word", font=("Segoe UI", 9), bd=1, relief="solid")
        self.book_detail_text.pack(fill="both", pady=(8, 0))
        self.book_detail_text.insert("1.0", "책을 선택하면 독서 기록 요약과 상태가 표시됩니다.")
        self.book_detail_text.configure(state="disabled")

        session_panel = tk.LabelFrame(top_area, text="오늘 기록", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 11, "bold"))
        session_panel.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=4)

        session_form = tk.Frame(session_panel, bg="#F4F7FF")
        session_form.pack(fill="x", padx=12, pady=12)

        tk.Label(session_form, text="책 선택", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        self.selected_book_label = tk.Label(session_form, text="선택된 책 없음", bg="#F4F7FF", fg="#4A5568", font=("Segoe UI", 10))
        self.selected_book_label.grid(row=0, column=1, sticky="w", padx=6)

        tk.Label(session_form, text="페이지 범위", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=(10, 0))
        page_frame = tk.Frame(session_form, bg="#F4F7FF")
        page_frame.grid(row=1, column=1, sticky="w", pady=(10, 0))
        self.page_start = tk.Entry(page_frame, width=8, font=("Segoe UI", 10))
        self.page_start.pack(side="left")
        tk.Label(page_frame, text="~", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 12, "bold")).pack(side="left", padx=4)
        self.page_end = tk.Entry(page_frame, width=8, font=("Segoe UI", 10))
        self.page_end.pack(side="left")

        tk.Label(session_form, text="CEFR 수준", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.cefr_level = tk.StringVar(value="B1")
        level_menu = ttk.Combobox(session_form, textvariable=self.cefr_level, values=["A1", "A2", "B1", "B2", "C1", "C2"], state="readonly", width=8)
        level_menu.grid(row=2, column=1, sticky="w", pady=(10, 0))

        button_row = tk.Frame(session_form, bg="#F4F7FF")
        button_row.grid(row=3, column=0, columnspan=2, pady=14, sticky="w")
        tk.Button(button_row, text="단어 생성", command=self.generate_vocab_from_pages, bg="#4B6FFB", fg="#FFFFFF", relief="flat", font=("Segoe UI", 10, "bold"), padx=14, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(button_row, text="기록 저장", command=self.save_session, bg="#FFFFFF", fg="#2D3A6A", relief="groove", font=("Segoe UI", 10, "bold"), padx=14, pady=8).pack(side="left")

        tk.Label(session_panel, text="오늘 요약 / 디스커션", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12)
        self.summary_text = tk.Text(session_panel, height=7, wrap="word", font=("Segoe UI", 10), bd=1, relief="solid")
        self.summary_text.pack(fill="both", padx=12, pady=(6, 10))

        tk.Button(session_panel, text="문법/표현 검사", command=self.check_summary_grammar, bg="#FFFFFF", fg="#2D3A6A", relief="groove", font=("Segoe UI", 10, "bold"), padx=14, pady=8).pack(padx=12, pady=(0, 10), anchor="w")
        self.grammar_result = tk.Text(session_panel, height=5, wrap="word", font=("Segoe UI", 9), bd=1, relief="solid", state="disabled", bg="#F7FAFF")
        self.grammar_result.pack(fill="both", padx=12, pady=(0, 12))

        bottom_area = tk.Frame(frame, bg="#F4F7FF")
        bottom_area.pack(fill="both", expand=True, padx=24, pady=(0, 18))

        history_panel = tk.LabelFrame(bottom_area, text="독서 기록 / 검색", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 11, "bold"))
        history_panel.pack(fill="both", expand=True, pady=(0, 10))

        search_bar = tk.Frame(history_panel, bg="#F4F7FF")
        search_bar.pack(fill="x", padx=12, pady=10)
        self.history_search = tk.Entry(search_bar, font=("Segoe UI", 10))
        self.history_search.pack(side="left", fill="x", expand=True)
        tk.Button(search_bar, text="검색", command=self.load_history, bg="#FFFFFF", fg="#2D3A6A", relief="groove", font=("Segoe UI", 10, "bold"), padx=14, pady=8).pack(side="left", padx=8)

        self.history_listbox = tk.Listbox(history_panel, bd=0, highlightthickness=0, selectbackground="#D5E4FF", font=("Segoe UI", 10))
        self.history_listbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.history_listbox.bind("<<ListboxSelect>>", self.on_history_select)

    def build_vocab_frame(self):
        frame = self.frames["vocab"]
        header = tk.Label(frame, text="단어장", bg="#F4F7FF", fg="#1F3B8B", font=("Segoe UI", 20, "bold"))
        header.pack(anchor="nw", padx=24, pady=(24, 8))

        subtitle = tk.Label(frame, text="단어장을 검색하고, 나만의 리스트를 생성하거나 출력할 수 있습니다.", bg="#F4F7FF", fg="#5A6279", font=("Segoe UI", 11))
        subtitle.pack(anchor="nw", padx=24)

        search_frame = tk.Frame(frame, bg="#F4F7FF")
        search_frame.pack(fill="x", padx=24, pady=14)
        self.vocab_search = tk.Entry(search_frame, font=("Segoe UI", 10))
        self.vocab_search.pack(side="left", fill="x", expand=True)
        tk.Button(search_frame, text="검색", command=self.load_vocab, bg="#4B6FFB", fg="#FFFFFF", relief="flat", font=("Segoe UI", 10, "bold"), padx=14, pady=8).pack(side="left", padx=8)

        mid = tk.Frame(frame, bg="#F4F7FF")
        mid.pack(fill="both", expand=True, padx=24, pady=(0, 18))

        left_vocab = tk.Frame(mid, bg="#F4F7FF")
        left_vocab.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.vocab_listbox = tk.Listbox(left_vocab, bd=0, highlightthickness=0, selectbackground="#D5E4FF", font=("Segoe UI", 10))
        self.vocab_listbox.pack(fill="both", expand=True)

        right_panel = tk.Frame(mid, bg="#F4F7FF", width=320)
        right_panel.pack(side="left", fill="y")
        right_panel.pack_propagate(False)

        tk.Label(right_panel, text="나의 단어장들", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        self.listgroup_listbox = tk.Listbox(right_panel, bd=0, highlightthickness=0, selectbackground="#D5E4FF", font=("Segoe UI", 10))
        self.listgroup_listbox.pack(fill="both", expand=True, pady=(0, 10))
        self.listgroup_listbox.bind("<<ListboxSelect>>", self.on_list_group_select)

        tk.Button(right_panel, text="선택 단어로 리스트 만들기", command=self.create_word_list, bg="#4B6FFB", fg="#FFFFFF", relief="flat", font=("Segoe UI", 10, "bold"), padx=14, pady=10).pack(fill="x", pady=4)
        tk.Button(right_panel, text="리스트 내보내기", command=self.export_selected_list, bg="#FFFFFF", fg="#2D3A6A", relief="groove", font=("Segoe UI", 10, "bold"), padx=14, pady=10).pack(fill="x", pady=4)

    def build_quiz_frame(self):
        frame = self.frames["quiz"]
        header = tk.Label(frame, text="퀴즈", bg="#F4F7FF", fg="#1F3B8B", font=("Segoe UI", 20, "bold"))
        header.pack(anchor="nw", padx=24, pady=(24, 8))

        subtitle = tk.Label(frame, text="단어 복습, 책별 퀴즈, 오늘의 독서 내용을 확인하는 퀴즈를 제공합니다.", bg="#F4F7FF", fg="#5A6279", font=("Segoe UI", 11))
        subtitle.pack(anchor="nw", padx=24)

        control_frame = tk.Frame(frame, bg="#F4F7FF")
        control_frame.pack(fill="x", padx=24, pady=14)

        self.quiz_type = tk.StringVar(value="복습 퀴즈")
        tk.Label(control_frame, text="퀴즈 종류", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        ttk.Combobox(control_frame, textvariable=self.quiz_type, values=["복습 퀴즈", "책별 단어 퀴즈", "디스커션 퀴즈"], state="readonly", width=18).grid(row=0, column=1, padx=10)

        tk.Label(control_frame, text="책 선택", bg="#F4F7FF", fg="#2D3A6A", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.quiz_book_combo = ttk.Combobox(control_frame, state="readonly", width=20)
        self.quiz_book_combo.grid(row=1, column=1, pady=(10, 0), padx=10)
        tk.Button(control_frame, text="새로고침", command=self.refresh_quiz_books, bg="#FFFFFF", fg="#2D3A6A", relief="groove", font=("Segoe UI", 10, "bold"), padx=14, pady=6).grid(row=1, column=2, padx=10, pady=(10, 0))

        tk.Button(frame, text="퀴즈 시작", command=self.start_quiz, bg="#4B6FFB", fg="#FFFFFF", relief="flat", font=("Segoe UI", 10, "bold"), padx=16, pady=10).pack(anchor="w", padx=24, pady=(0, 12))

        self.quiz_label = tk.Label(frame, text="여기서 퀴즈 문항이 표시됩니다.", bg="#F4F7FF", fg="#2F3A57", font=("Segoe UI", 14), wraplength=820, justify="left")
        self.quiz_label.pack(fill="x", padx=24, pady=(0, 18))

        answer_frame = tk.Frame(frame, bg="#F4F7FF")
        answer_frame.pack(fill="x", padx=24)
        self.quiz_answer = tk.Entry(answer_frame, font=("Segoe UI", 11))
        self.quiz_answer.pack(side="left", fill="x", expand=True, pady=4)
        tk.Button(answer_frame, text="확인", command=self.check_quiz_answer, bg="#FFFFFF", fg="#2D3A6A", relief="groove", font=("Segoe UI", 10, "bold"), padx=16, pady=8).pack(side="left", padx=10)

        control_buttons = tk.Frame(frame, bg="#F4F7FF")
        control_buttons.pack(fill="x", padx=24, pady=14)
        tk.Button(control_buttons, text="알다", command=lambda: self.mark_quiz_result(True), bg="#4B6FFB", fg="#FFFFFF", relief="flat", font=("Segoe UI", 10, "bold"), padx=16, pady=8).pack(side="left", padx=(0, 10))
        tk.Button(control_buttons, text="모르다", command=lambda: self.mark_quiz_result(False), bg="#FFFFFF", fg="#2D3A6A", relief="groove", font=("Segoe UI", 10, "bold"), padx=16, pady=8).pack(side="left")

        self.quiz_status = tk.Label(frame, text="퀴즈 진행 상태가 표시됩니다.", bg="#F4F7FF", fg="#4A5568", font=("Segoe UI", 10))
        self.quiz_status.pack(anchor="w", padx=24, pady=(4, 0))

    def show_home(self):
        self.frames["home"].lift()
        self.highlight_nav(0)

    def show_vocab(self):
        self.frames["vocab"].lift()
        self.highlight_nav(1)

    def show_quiz(self):
        self.frames["quiz"].lift()
        self.highlight_nav(2)
        self.refresh_quiz_books()

    def highlight_nav(self, index):
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.configure(bg="#4B6FFB", fg="#FFFFFF")
            else:
                btn.configure(bg="#FFFFFF", fg="#2D3A6A")

    def add_book_file(self):
        filepath = filedialog.askopenfilename(title="텍스트 파일 선택", filetypes=[("Text files", "*.txt")])
        if not filepath:
            return
        title = self.new_book_title.get().strip() or os.path.basename(filepath)
        shelf = self.new_shelf.get().strip() or "기본"
        self.cursor.execute(
            "INSERT INTO books (title, file_path, shelf, finished, note) VALUES (?, ?, ?, ?, ?)",
            (title, filepath, shelf, 0, ""),
        )
        self.conn.commit()
        self.new_book_title.delete(0, "end")
        self.load_books()
        messagebox.showinfo("추가됨", "새 책이 책장에 추가되었습니다.")

    def update_book_info(self):
        if not self.selected_book_id:
            messagebox.showwarning("선택 필요", "수정할 책을 먼저 선택하세요.")
            return
        shelf = self.new_shelf.get().strip() or "기본"
        title = self.new_book_title.get().strip()
        if title:
            self.cursor.execute("UPDATE books SET title = ?, shelf = ? WHERE id = ?", (title, shelf, self.selected_book_id))
            self.conn.commit()
            self.load_books()
            messagebox.showinfo("수정됨", "책 정보가 저장되었습니다.")

    def load_books(self):
        self.book_listbox.delete(0, "end")
        self.books = self.cursor.execute("SELECT * FROM books ORDER BY shelf, title").fetchall()
        for book in self.books:
            label = f"[{book['shelf']}] {book['title']}"
            self.book_listbox.insert("end", label)
        self.refresh_quiz_books()

    def on_book_select(self, event):
        selection = self.book_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        book = self.books[index]
        self.selected_book_id = book["id"]
        self.selected_book_label.configure(text=book["title"])
        self.new_book_title.delete(0, "end")
        self.new_book_title.insert(0, book["title"])
        self.new_shelf.delete(0, "end")
        self.new_shelf.insert(0, book["shelf"])
        history = self.cursor.execute(
            "SELECT COUNT(*) as count, SUM(end_page - start_page + 1) as pages FROM sessions WHERE book_id = ?",
            (self.selected_book_id,),
        ).fetchone()
        book_summary = f"제목: {book['title']}\n책장: {book['shelf']}\n완독 여부: {'완독' if book['finished'] else '읽는 중'}\n총 기록: {history['count']}회\n총 읽은 쪽수: {history['pages'] or 0}쪽\n\n메모:\n{book['note'] or '없음'}"
        self.book_detail_text.configure(state="normal")
        self.book_detail_text.delete("1.0", "end")
        self.book_detail_text.insert("1.0", book_summary)
        self.book_detail_text.configure(state="disabled")

    def load_history(self):
        self.history_listbox.delete(0, "end")
        keyword = self.history_search.get().strip()
        sql = "SELECT s.id, s.date, b.title, s.start_page, s.end_page FROM sessions s LEFT JOIN books b ON s.book_id = b.id"
        params = []
        if keyword:
            sql += " WHERE b.title LIKE ? OR s.date LIKE ?"
            params = [f"%{keyword}%", f"%{keyword}%"]
        sql += " ORDER BY s.date DESC"
        rows = self.cursor.execute(sql, params).fetchall()
        for row in rows:
            label = f"{row['date']} | {row['title'] or '알 수 없음'} | {row['start_page']}~{row['end_page']}"
            self.history_listbox.insert("end", label)

    def on_history_select(self, event):
        selection = self.history_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        keyword = self.history_search.get().strip()
        sql = "SELECT s.*, b.title FROM sessions s LEFT JOIN books b ON s.book_id = b.id"
        params = []
        if keyword:
            sql += " WHERE b.title LIKE ? OR s.date LIKE ?"
            params = [f"%{keyword}%", f"%{keyword}%"]
        sql += " ORDER BY s.date DESC"
        rows = self.cursor.execute(sql, params).fetchall()
        row = rows[index]
        summary = row["summary"] or "요약이 없습니다."
        messagebox.showinfo("기록 상세", f"날짜: {row['date']}\n책: {row['title'] or '알 수 없음'}\n페이지: {row['start_page']}~{row['end_page']}\n\n요약:\n{summary}")

    def generate_vocab_from_pages(self):
        if not self.selected_book_id:
            messagebox.showwarning("책 선택", "단어를 생성하려면 왼쪽 책장에서 책을 선택하세요.")
            return
        try:
            start = int(self.page_start.get().strip())
            end = int(self.page_end.get().strip())
            if start < 1 or end < start:
                raise ValueError
        except ValueError:
            messagebox.showwarning("페이지 오류", "올바른 페이지 범위를 입력해주세요. 예: 10 ~ 20")
            return

        page_text = self.extract_page_text(start, end)
        if not page_text:
            messagebox.showwarning("파일 없음", "선택한 책의 텍스트 파일을 읽을 수 없습니다.")
            return

        try:
            response_text = self.getLLM(page_text)
            response_json = self.parse_llm_response(response_text)

            if isinstance(response_json, list):
                response_json = response_json[0] if response_json else {}
            answer_data = response_json.get("answer") if isinstance(response_json, dict) else None

            if answer_data is None:
                raise ValueError("LLM 응답에 'answer' 필드가 없습니다.")

            if isinstance(answer_data, str):
                answer_data = self.normalize_json_text(answer_data)
                answer_data = json.loads(answer_data)

            if isinstance(answer_data, dict) and "words" in answer_data:
                vocab_list = answer_data["words"]
            elif isinstance(answer_data, list):
                vocab_list = answer_data
            else:
                raise ValueError("LLM 응답에서 단어 목록을 찾을 수 없습니다.")

            inserted = 0
            today = date.today().isoformat()
            for item in vocab_list:
                if not isinstance(item, dict) or "word" not in item:
                    continue
                self.cursor.execute(
                    "INSERT INTO vocab (word, meaning, pos, example, source, book_id, date, cefr) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        item.get("word", ""),
                        item.get("meaning", ""),
                        item.get("pos", ""),
                        item.get("example", ""),
                        "llm_generated",
                        self.selected_book_id,
                        today,
                        self.cefr_level.get(),
                    ),
                )
                inserted += 1
            self.conn.commit()
            self.load_vocab()
            messagebox.showinfo("생성 완료", f"{inserted}개의 단어가 단어장에 추가되었습니다.")
        except json.JSONDecodeError:
            messagebox.showerror("오류", "LLM 응답을 JSON으로 해석할 수 없습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"단어 생성 중 오류가 발생했습니다.\n{str(e)}")

    def normalize_json_text(self, text):
        text = text.strip()
        if "HIHIHIHI" in text:
            idx = text.find("HIHIHIHI")
            text = text[idx + len("HIHIHIHI") :].strip()

        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z0-9]*\n", "", text)
        if text.endswith("```"):
            text = re.sub(r"\n```$", "", text)

        start_idx = min(
            [pos for pos in (text.find("["), text.find("{")) if pos != -1] or [0]
        )
        text = text[start_idx:]
        return text.strip()

    def parse_llm_response(self, text):
        text = self.normalize_json_text(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"(\[.*\]|\{.*\})", text, re.S)
            if match:
                return json.loads(match.group(1))
            raise

    def getLLM(self, text):
        """LLM API를 호출하여 텍스트에서 단어 정보 추출"""
        url = "http://192.168.0.31:5678/webhook/78b260b2-316d-4dcd-bf48-4f1e048004ff"
        payload = {"message": text}
        response = requests.post(url, json=payload)
        print("LLM 응답:", response.text)
        return response.text

    def getPage(self, start, end):
        start = int(start)
        end = int(end)
        start += 1
        end += 1
        fnd = 1
        ret = ""
        with open("zxcv.txt", "r") as w:
            while True:
                line = w.readline()
                if not line:
                    break
                if line.strip().isdecimal() and int(line.strip()) == fnd:
                    fnd += 1
                if start <= fnd <= end:
                    ret += line
                if fnd > end:
                    break
        return ret

    def save_session(self):
        if not self.selected_book_id:
            messagebox.showwarning("책 선택", "기록을 저장하려면 책을 먼저 선택하세요.")
            return
        try:
            start = int(self.page_start.get().strip())
            end = int(self.page_end.get().strip())
            if start < 1 or end < start:
                raise ValueError
        except ValueError:
            messagebox.showwarning("페이지 오류", "올바른 페이지 범위를 입력해주세요. 예: 10 ~ 20")
            return

        summary = self.summary_text.get("1.0", "end").strip()
        if not summary:
            if not messagebox.askyesno("요약 없음", "요약이 비어 있습니다. 그래도 저장하시겠습니까?"):
                return

        now = datetime.now().isoformat()
        self.cursor.execute(
            "INSERT INTO sessions (date, book_id, start_page, end_page, summary, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (date.today().isoformat(), self.selected_book_id, start, end, summary, now),
        )
        self.conn.commit()
        self.load_history()
        messagebox.showinfo("저장됨", "오늘 독서 기록이 저장되었습니다.")

    def check_summary_grammar(self):
        summary = self.summary_text.get("1.0", "end").strip()
        if not summary:
            messagebox.showwarning("입력 필요", "검사할 내용을 입력해주세요.")
            return
        result = self.grammar_review(summary)
        self.grammar_result.configure(state="normal")
        self.grammar_result.delete("1.0", "end")
        self.grammar_result.insert("1.0", result)
        self.grammar_result.configure(state="disabled")

    def grammar_review(self, text):
        suggestions = []
        if re.search(r"\bi\b", text):
            suggestions.append("I는 항상 대문자로 쓰세요.")
        if " could of " in text.lower() or " should of " in text.lower() or " would of " in text.lower():
            suggestions.append("'could have', 'should have', 'would have'를 사용하세요.")
        if " a apple" in text.lower():
            suggestions.append("'an apple'처럼 a/an 사용을 확인하세요.")
        if "  " in text:
            suggestions.append("연속 공백이 있습니다. 한 칸씩 띄워 쓰세요.")
        repeats = re.findall(r"\b(\w+) \1\b", text.lower())
        if repeats:
            suggestions.append(f"'{', '.join(set(repeats))}' 같은 단어가 연속으로 반복되었습니다.")
        sentences = re.split(r"(?<=[.!?]) +", text)
        for sentence in sentences:
            if sentence and sentence[0].islower():
                suggestions.append("문장은 대문자로 시작해야 합니다.")
                break
        if not suggestions:
            return "문법과 표현이 대체로 자연스럽습니다. 계속해서 요약을 발전시켜보세요."
        return "\n".join(suggestions)

    def get_book_text(self, book_id):
        book = self.cursor.execute("SELECT file_path FROM books WHERE id = ?", (book_id,)).fetchone()
        if not book:
            return ""
        try:
            with open(book["file_path"], "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def extract_page_text(self, start, end):
        book = self.cursor.execute("SELECT file_path FROM books WHERE id = ?", (self.selected_book_id,)).fetchone()
        if not book:
            return ""
        
        start = int(start)
        end = int(end)
        start += 1
        end += 1
        fnd = 1
        ret = ""
        try:
            with open(book["file_path"], "r", encoding="utf-8", errors="ignore") as w:
                while True:
                    line = w.readline()
                    if not line:
                        break
                    if line.strip().isdecimal() and int(line.strip()) == fnd:
                        fnd += 1
                    if start <= fnd <= end:
                        ret += line
                    if fnd > end:
                        break
        except FileNotFoundError:
            pass
        return ret

    def extract_words(self, text):
        words = re.findall(r"[A-Za-z']{2,}", text.lower())
        return [w for w in words if w not in COMMON_STOPWORDS]

    def pick_candidate_words(self, text):
        words = self.extract_words(text)
        counts = Counter(words)
        candidates = [w for w, _ in counts.most_common(40) if len(w) > 2]
        return candidates

    def filter_words_by_cefr(self, candidates, level):
        known = CEFR_WORDS.get(level, set())
        result = [w for w in candidates if w in known]
        if len(result) < 12:
            result.extend([w for w in candidates if w not in result])
        return result[:15]

    def guess_pos(self, word):
        if word.endswith("ing"):
            return "verb"
        if word.endswith("ly"):
            return "adverb"
        if word.endswith("ed"):
            return "verb"
        if word.endswith("ion") or word.endswith("ment"):
            return "noun"
        if word.endswith("able") or word.endswith("ful"):
            return "adjective"
        return "noun"

    def find_example(self, word, text):
        pattern = re.compile(r"([A-Z][^.!?]*\b" + re.escape(word) + r"\b[^.!?]*[.!?])", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return match.group(1).strip().replace("\n", " ")
        return f"This sentence uses {word}."

    def load_vocab(self):
        self.vocab_listbox.delete(0, "end")
        keyword = self.vocab_search.get().strip()
        sql = "SELECT v.word, v.meaning, v.pos, v.example, b.title, v.date FROM vocab v LEFT JOIN books b ON v.book_id = b.id"
        params = []
        if keyword:
            sql += " WHERE v.word LIKE ? OR v.meaning LIKE ? OR v.example LIKE ? OR b.title LIKE ?"
            params = [f"%{keyword}%"] * 4
        sql += " ORDER BY v.date DESC"
        rows = self.cursor.execute(sql, params).fetchall()
        for row in rows:
            label = f"{row['word']} | {row['meaning']} | {row['pos']} | {row['example']} | {row['title'] or '기본'} | {row['date']}"
            self.vocab_listbox.insert("end", label)

    def load_word_lists(self):
        self.listgroup_listbox.delete(0, "end")
        rows = self.cursor.execute("SELECT id, name FROM word_lists ORDER BY created_at DESC").fetchall()
        self.word_lists = rows
        for row in rows:
            self.listgroup_listbox.insert("end", row["name"])

    def on_list_group_select(self, event):
        selection = self.listgroup_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        list_id = self.word_lists[index]["id"]
        rows = self.cursor.execute(
            "SELECT v.word, v.meaning, v.example FROM list_items l JOIN vocab v ON l.vocab_id = v.id WHERE l.list_id = ?",
            (list_id,),
        ).fetchall()
        content = "\n".join([f"{row['word']} - {row['meaning']} - {row['example']}" for row in rows]) or "단어가 없습니다."
        messagebox.showinfo("단어장 상세", content)

    def create_word_list(self):
        selections = self.vocab_listbox.curselection()
        if not selections:
            messagebox.showwarning("선택 필요", "단어를 먼저 선택하세요.")
            return
        name = tk.simpledialog.askstring("단어장 이름", "단어장 이름을 입력하세요.")
        if not name:
            return
        description = ""
        now = datetime.now().isoformat()
        self.cursor.execute("INSERT INTO word_lists (name, description, created_at) VALUES (?, ?, ?)", (name, description, now))
        list_id = self.cursor.lastrowid
        for index in selections:
            row = self.cursor.execute(
                "SELECT id FROM vocab ORDER BY date DESC LIMIT 1 OFFSET ?", (index,),
            ).fetchone()
            if row:
                self.cursor.execute("INSERT INTO list_items (list_id, vocab_id) VALUES (?, ?)", (list_id, row["id"]))
        self.conn.commit()
        self.load_word_lists()
        messagebox.showinfo("단어장 생성", "새 단어장이 생성되었습니다.")

    def export_selected_list(self):
        selection = self.listgroup_listbox.curselection()
        if not selection:
            messagebox.showwarning("선택 필요", "내보낼 단어장을 선택하세요.")
            return
        list_id = self.word_lists[selection[0]]["id"]
        rows = self.cursor.execute(
            "SELECT v.word, v.meaning, v.example FROM list_items l JOIN vocab v ON l.vocab_id = v.id WHERE l.list_id = ?",
            (list_id,),
        ).fetchall()
        if not rows:
            messagebox.showwarning("비어 있음", "단어장이 비어 있습니다.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(f"{row['word']}\t{row['meaning']}\t{row['example']}\n")
        messagebox.showinfo("내보내기 완료", f"{path}에 단어장이 저장되었습니다.")

    def refresh_quiz_books(self):
        books = self.cursor.execute("SELECT title FROM books ORDER BY title").fetchall()
        values = [row["title"] for row in books]
        self.quiz_book_combo["values"] = values
        if values:
            self.quiz_book_combo.current(0)

    def start_quiz(self):
        self.current_quiz_index = 0
        quiz_type = self.quiz_type.get()
        if quiz_type == "복습 퀴즈":
            rows = self.cursor.execute("SELECT word, meaning FROM vocab ORDER BY RANDOM() LIMIT 20").fetchall()
            self.current_quiz_words = [{'word': row['word'], 'meaning': row['meaning']} for row in rows]
        elif quiz_type == "책별 단어 퀴즈":
            book_title = self.quiz_book_combo.get().strip()
            if not book_title:
                messagebox.showwarning("책 선택", "책별 퀴즈를 하려면 책을 선택하세요.")
                return
            book = self.cursor.execute("SELECT id FROM books WHERE title = ?", (book_title,)).fetchone()
            if not book:
                messagebox.showwarning("책 없음", "선택한 책을 찾을 수 없습니다.")
                return
            rows = self.cursor.execute(
                "SELECT word, meaning FROM vocab WHERE book_id = ? ORDER BY RANDOM() LIMIT 20",
                (book['id'],),
            ).fetchall()
            self.current_quiz_words = [{'word': row['word'], 'meaning': row['meaning']} for row in rows]
        else:
            rows = self.cursor.execute(
                "SELECT summary FROM sessions WHERE date = ? AND summary IS NOT NULL ORDER BY id DESC LIMIT 1",
                (date.today().isoformat(),),
            ).fetchall()
            if not rows:
                messagebox.showwarning("요약 없음", "오늘의 요약이 없어 디스커션 퀴즈를 시작할 수 없습니다.")
                return
            summary = rows[0]['summary']
            keywords = self.extract_words(summary)
            if not keywords:
                messagebox.showwarning("키워드 없음", "요약에서 퀴즈 항목을 생성할 수 없습니다.")
                return
            self.current_quiz_words = [{'word': kw, 'meaning': '', 'summary': summary} for kw in keywords[:15]]

        if not self.current_quiz_words:
            messagebox.showinfo("단어 없음", "퀴즈를 시작할 조건이 부족합니다. 단어장을 먼저 채워주세요.")
            return

        self.show_current_quiz_question()
        self.quiz_status.configure(text=f"총 {len(self.current_quiz_words)}문제 중 1번")
        self.quiz_answer.delete(0, "end")

    def show_current_quiz_question(self):
        if self.current_quiz_index >= len(self.current_quiz_words):
            messagebox.showinfo("퀴즈 완료", "퀴즈를 모두 완료했습니다!")
            self.quiz_label.configure(text="퀴즈를 다시 시작하거나 다른 유형을 선택하세요.")
            return
        item = self.current_quiz_words[self.current_quiz_index]
        if self.quiz_type.get() == "디스커션 퀴즈":
            question = f"다음 요약에서 빠진 단어를 추측하세요:\n{item['summary'][:120]}..."
        else:
            question = f"{item['word']}의 뜻을 입력하세요."
        self.quiz_label.configure(text=question)
        self.current_quiz_answer = item.get('meaning', '')
        self.quiz_answer.delete(0, "end")

    def check_quiz_answer(self):
        if not self.current_quiz_words or self.current_quiz_index >= len(self.current_quiz_words):
            messagebox.showwarning("시작 필요", "먼저 퀴즈를 시작해주세요.")
            return
        user_answer = self.quiz_answer.get().strip().lower()
        if not self.current_quiz_answer:
            messagebox.showinfo("정보", "이 문제는 디스커션 퀴즈입니다. '알다' 또는 '모르다'를 눌러주세요.")
            return
        if user_answer == self.current_quiz_answer.lower() or self.current_quiz_answer.lower() in user_answer:
            messagebox.showinfo("정답", "정답입니다!")
        else:
            messagebox.showinfo("오답", f"정답 예시: {self.current_quiz_answer}")

    def mark_quiz_result(self, known):
        if not self.current_quiz_words or self.current_quiz_index >= len(self.current_quiz_words):
            messagebox.showwarning("시작 필요", "먼저 퀴즈를 시작해주세요.")
            return
        item = self.current_quiz_words[self.current_quiz_index]
        if not known and self.quiz_type.get() != "디스커션 퀴즈":
            today = date.today().isoformat()
            self.cursor.execute(
                "INSERT OR IGNORE INTO vocab (word, meaning, pos, example, source, book_id, date, cefr) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (item['word'], f"{item['word']} 의미", self.guess_pos(item['word']), "모르는 단어", "quiz", self.selected_book_id, today, self.cefr_level.get()),
            )
            self.conn.commit()
        self.current_quiz_index += 1
        if self.current_quiz_index < len(self.current_quiz_words):
            self.show_current_quiz_question()
            self.quiz_status.configure(text=f"총 {len(self.current_quiz_words)}문제 중 {self.current_quiz_index + 1}번")
        else:
            self.quiz_label.configure(text="모든 퀴즈를 완료했습니다! 오늘의 학습을 축하합니다.")
            self.quiz_status.configure(text="퀴즈가 모두 끝났습니다.")


if __name__ == "__main__":
    app = ReadingApp()
    app.mainloop()
