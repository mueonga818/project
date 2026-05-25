"""
영어책 독서 기록장 - Tkinter GUI
n8n 백엔드 연동 버전
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import os
import requests
from datetime import datetime
from PIL import Image, ImageTk
import threading

# ── 설정 ──────────────────────────────────────────────────
N8N_BASE = "http://localhost:5678/webhook"
DATA_DIR  = os.path.join(os.path.dirname(__file__), "data")
BOOKS_DIR = os.path.join(os.path.dirname(__file__), "books")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BOOKS_DIR, exist_ok=True)

DATA_FILE  = os.path.join(DATA_DIR, "reading_log.json")
VOCAB_FILE = os.path.join(DATA_DIR, "vocabulary.json")
QUIZ_FILE  = os.path.join(DATA_DIR, "quizzes.json")

# CEFR 레벨 목록
CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# ── 데이터 로드/저장 유틸 ─────────────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── n8n API 헬퍼 ──────────────────────────────────────────
def call_n8n(endpoint: str, payload: dict) -> dict:
    """n8n webhook 호출. 오류 시 빈 dict 반환."""
    try:
        r = requests.post(f"{N8N_BASE}/{endpoint}", json=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        messagebox.showerror("n8n 연결 오류", str(e))
        return {}

# ── 메인 앱 ───────────────────────────────────────────────
class ReadingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("📚 영어 독서 기록장")
        self.geometry("1100x750")
        self.configure(bg="#1a1a2e")
        self.resizable(True, True)

        # 앱 상태
        self.reading_log  = load_json(DATA_FILE, {"books": {}, "sessions": [], "shelves": [{"name": "내 책장", "books": []}]})
        self.vocabulary   = load_json(VOCAB_FILE, {"words": [], "lists": {}})
        self.quizzes      = load_json(QUIZ_FILE,  {"quizzes": []})
        self.user_cefr    = tk.StringVar(value="B1")
        self.current_session = {}

        self._build_ui()

    # ── UI 빌드 ───────────────────────────────────────────
    def _build_ui(self):
        # 색상 팔레트
        self.colors = {
            "bg_dark":   "#1a1a2e",
            "bg_mid":    "#16213e",
            "bg_card":   "#0f3460",
            "accent":    "#e94560",
            "accent2":   "#533483",
            "text":      "#eaeaea",
            "text_muted":"#a0a0b0",
            "success":   "#4ecca3",
            "warning":   "#f5a623",
        }
        c = self.colors

        # ── 왼쪽 사이드바 ─────────────────────────────────
        sidebar = tk.Frame(self, bg=c["bg_mid"], width=180)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # 로고
        logo = tk.Label(sidebar, text="📚", font=("Helvetica", 36),
                        bg=c["bg_mid"], fg=c["accent"])
        logo.pack(pady=(28, 4))
        tk.Label(sidebar, text="독서 기록장", font=("Helvetica", 13, "bold"),
                 bg=c["bg_mid"], fg=c["text"]).pack()
        tk.Label(sidebar, text="English Reader", font=("Helvetica", 9),
                 bg=c["bg_mid"], fg=c["text_muted"]).pack(pady=(0, 24))

        # CEFR 선택
        tk.Label(sidebar, text="내 CEFR 레벨", font=("Helvetica", 9),
                 bg=c["bg_mid"], fg=c["text_muted"]).pack()
        cefr_cb = ttk.Combobox(sidebar, textvariable=self.user_cefr,
                               values=CEFR_LEVELS, width=8, state="readonly")
        cefr_cb.pack(pady=(2, 20))

        # 탭 버튼
        self.tab_buttons = []
        self.notebook_frame = tk.Frame(self, bg=c["bg_dark"])
        self.notebook_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.frames = {}
        tabs = [
            ("🏠  홈",   "home",  HomeTab),
            ("📖  단어장", "vocab", VocabTab),
            ("🧠  퀴즈",  "quiz",  QuizTab),
        ]
        for label, key, cls in tabs:
            frame = cls(self.notebook_frame, self)
            self.frames[key] = frame
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)

            btn = tk.Button(
                sidebar, text=label, font=("Helvetica", 11),
                bg=c["bg_mid"], fg=c["text_muted"],
                bd=0, cursor="hand2", anchor="w", padx=20,
                activebackground=c["bg_card"],
                command=lambda k=key: self._show_tab(k)
            )
            btn.pack(fill=tk.X, pady=2)
            self.tab_buttons.append((key, btn))

        # 하단 설정
        tk.Label(sidebar, text="─" * 20, bg=c["bg_mid"], fg=c["text_muted"]).pack(side=tk.BOTTOM, pady=4)
        tk.Label(sidebar, text="v1.0  ·  n8n 연동",
                 font=("Helvetica", 8), bg=c["bg_mid"],
                 fg=c["text_muted"]).pack(side=tk.BOTTOM)

        self._show_tab("home")

    def _show_tab(self, key):
        c = self.colors
        for k, btn in self.tab_buttons:
            if k == key:
                btn.config(bg=self.colors["bg_card"], fg=self.colors["accent"])
            else:
                btn.config(bg=self.colors["bg_mid"], fg=self.colors["text_muted"])
        self.frames[key].tkraise()
        if hasattr(self.frames[key], "refresh"):
            self.frames[key].refresh()

    def save_all(self):
        save_json(DATA_FILE,  self.reading_log)
        save_json(VOCAB_FILE, self.vocabulary)
        save_json(QUIZ_FILE,  self.quizzes)


# ═══════════════════════════════════════════════════════════
#  탭 A : 홈
# ═══════════════════════════════════════════════════════════
class HomeTab(tk.Frame):
    def __init__(self, parent, app: ReadingApp):
        super().__init__(parent, bg=app.colors["bg_dark"])
        self.app = app
        self._build()

    def _build(self):
        c = self.app.colors

        # 상단 바
        top = tk.Frame(self, bg=c["bg_mid"])
        top.pack(fill=tk.X, padx=0, pady=0)
        tk.Label(top, text="🏠 홈 — 나의 책장", font=("Helvetica", 16, "bold"),
                 bg=c["bg_mid"], fg=c["text"], pady=12).pack(side=tk.LEFT, padx=20)
        tk.Button(top, text="+ 책 추가", bg=c["accent"], fg="white",
                  bd=0, padx=12, pady=6, cursor="hand2",
                  command=self._add_book).pack(side=tk.RIGHT, padx=8, pady=8)
        tk.Button(top, text="+ 책장 추가", bg=c["accent2"], fg="white",
                  bd=0, padx=12, pady=6, cursor="hand2",
                  command=self._add_shelf).pack(side=tk.RIGHT, padx=0, pady=8)

        # 검색 바
        search_bar = tk.Frame(self, bg=c["bg_dark"])
        search_bar.pack(fill=tk.X, padx=20, pady=8)
        tk.Label(search_bar, text="🔍", bg=c["bg_dark"], fg=c["text"]).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *_: self._filter_books())
        tk.Entry(search_bar, textvariable=self.search_var,
                 bg=c["bg_mid"], fg=c["text"], insertbackground=c["text"],
                 bd=0, font=("Helvetica", 11), width=40).pack(side=tk.LEFT, padx=8, ipady=4)

        # 메인 영역 (책장 + 기록 패널)
        main = tk.Frame(self, bg=c["bg_dark"])
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # 왼쪽: 책장
        self.shelf_frame = tk.Frame(main, bg=c["bg_dark"])
        self.shelf_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 오른쪽: 오늘 독서 기록 패널
        record_panel = tk.Frame(main, bg=c["bg_mid"], width=300)
        record_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        record_panel.pack_propagate(False)
        self._build_record_panel(record_panel)

        self._render_shelves()

    # ── 책장 렌더링 ───────────────────────────────────────
    def _render_shelves(self, filter_text=""):
        c = self.app.colors
        for w in self.shelf_frame.winfo_children():
            w.destroy()

        shelves = self.app.reading_log.get("shelves", [])
        for shelf_idx, shelf in enumerate(shelves):
            # 책장 헤더
            hdr = tk.Frame(self.shelf_frame, bg=c["bg_mid"])
            hdr.pack(fill=tk.X, pady=(8, 2))
            tk.Label(hdr, text=f"📚 {shelf['name']}", font=("Helvetica", 12, "bold"),
                     bg=c["bg_mid"], fg=c["success"]).pack(side=tk.LEFT, padx=8, pady=4)
            tk.Button(hdr, text="편집", bg=c["bg_dark"], fg=c["text_muted"],
                      bd=0, cursor="hand2",
                      command=lambda i=shelf_idx: self._edit_shelf(i)).pack(side=tk.RIGHT, padx=4)
            tk.Button(hdr, text="삭제", bg=c["bg_dark"], fg=c["accent"],
                      bd=0, cursor="hand2",
                      command=lambda i=shelf_idx: self._delete_shelf(i)).pack(side=tk.RIGHT)

            # 책들 (가로 스크롤)
            books_canvas = tk.Canvas(self.shelf_frame, bg=c["bg_dark"],
                                     height=160, highlightthickness=0)
            scrollbar = tk.Scrollbar(self.shelf_frame, orient="horizontal",
                                     command=books_canvas.xview)
            books_canvas.configure(xscrollcommand=scrollbar.set)
            books_canvas.pack(fill=tk.X, padx=8)
            scrollbar.pack(fill=tk.X, padx=8)

            inner = tk.Frame(books_canvas, bg=c["bg_dark"])
            books_canvas.create_window((0, 0), window=inner, anchor="nw")

            books = shelf.get("books", [])
            filtered = [b for b in books
                        if filter_text.lower() in b.get("title","").lower()
                        or filter_text.lower() in b.get("author","").lower()]
            if not filtered and filter_text:
                filtered = books  # 필터 없으면 전체 표시

            for book in filtered:
                self._book_card(inner, book, shelf_idx)

            inner.update_idletasks()
            books_canvas.config(scrollregion=books_canvas.bbox("all"))

            # 나무 바닥 (책장 선반)
            shelf_line = tk.Frame(self.shelf_frame, bg="#6b4c2a", height=6)
            shelf_line.pack(fill=tk.X, padx=4, pady=(0, 6))

    def _book_card(self, parent, book, shelf_idx):
        c = self.app.colors
        colors_list = [c["accent2"], c["bg_card"], "#2d5a27", "#5a2d2d", "#2d4a5a"]
        book_color = colors_list[hash(book.get("title","")) % len(colors_list)]

        frame = tk.Frame(parent, bg=book_color, width=90, height=130,
                         cursor="hand2", relief="raised", bd=1)
        frame.pack(side=tk.LEFT, padx=6, pady=8)
        frame.pack_propagate(False)

        # 책 제목 (세로 텍스트 느낌 – 줄바꿈)
        title = book.get("title", "?")
        short = title[:12] + "…" if len(title) > 12 else title
        tk.Label(frame, text=short, bg=book_color, fg="white",
                 font=("Helvetica", 8, "bold"), wraplength=80,
                 justify="center").pack(expand=True)

        # 완독 배지
        if book.get("finished"):
            tk.Label(frame, text="✓ 완독", bg=c["success"], fg="black",
                     font=("Helvetica", 7, "bold")).pack(fill=tk.X)

        frame.bind("<Button-1>", lambda e, b=book: self._open_book(b))
        for child in frame.winfo_children():
            child.bind("<Button-1>", lambda e, b=book: self._open_book(b))

    # ── 오른쪽: 오늘 기록 패널 ────────────────────────────
    def _build_record_panel(self, panel):
        c = self.app.colors
        tk.Label(panel, text="오늘의 독서", font=("Helvetica", 13, "bold"),
                 bg=c["bg_mid"], fg=c["text"]).pack(pady=(16, 8))

        # 책 선택
        tk.Label(panel, text="책 선택", bg=c["bg_mid"], fg=c["text_muted"],
                 font=("Helvetica", 9)).pack(anchor="w", padx=12)
        self.selected_book_var = tk.StringVar()
        self.book_combo = ttk.Combobox(panel, textvariable=self.selected_book_var,
                                       state="readonly", width=28)
        self.book_combo.pack(padx=12, pady=4)

        # 시작/끝 페이지
        pg_frame = tk.Frame(panel, bg=c["bg_mid"])
        pg_frame.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(pg_frame, text="시작 쪽", bg=c["bg_mid"], fg=c["text_muted"],
                 font=("Helvetica", 9), width=8).pack(side=tk.LEFT)
        self.start_page = tk.IntVar(value=1)
        tk.Spinbox(pg_frame, from_=1, to=9999, textvariable=self.start_page,
                   width=6, bg=c["bg_card"], fg=c["text"]).pack(side=tk.LEFT)
        tk.Label(pg_frame, text="끝 쪽", bg=c["bg_mid"], fg=c["text_muted"],
                 font=("Helvetica", 9), width=8).pack(side=tk.LEFT, padx=(8,0))
        self.end_page = tk.IntVar(value=10)
        tk.Spinbox(pg_frame, from_=1, to=9999, textvariable=self.end_page,
                   width=6, bg=c["bg_card"], fg=c["text"]).pack(side=tk.LEFT)

        # 단어 추출 버튼
        tk.Button(panel, text="🔍 단어 추출 (n8n)",
                  bg=c["accent"], fg="white", bd=0, pady=6,
                  cursor="hand2", font=("Helvetica", 10, "bold"),
                  command=self._extract_words).pack(fill=tk.X, padx=12, pady=6)

        # 디스커션 입력
        tk.Label(panel, text="오늘 읽은 내용 요약 (영어)",
                 bg=c["bg_mid"], fg=c["text_muted"], font=("Helvetica", 9)).pack(anchor="w", padx=12)
        self.discussion_text = tk.Text(panel, height=5, bg=c["bg_card"],
                                       fg=c["text"], font=("Helvetica", 10),
                                       insertbackground=c["text"], bd=0,
                                       wrap="word")
        self.discussion_text.pack(fill=tk.X, padx=12, pady=4)

        # 문법 검사
        tk.Button(panel, text="✏️ 문법 검사 (n8n)",
                  bg=c["accent2"], fg="white", bd=0, pady=5,
                  cursor="hand2",
                  command=self._check_grammar).pack(fill=tk.X, padx=12, pady=2)

        # 완료
        tk.Button(panel, text="🎉 오독완 (오늘 독서 완료!)",
                  bg=c["success"], fg="black", bd=0, pady=8,
                  cursor="hand2", font=("Helvetica", 10, "bold"),
                  command=self._finish_session).pack(fill=tk.X, padx=12, pady=8)

        # 결과 표시
        self.result_label = tk.Label(panel, text="", bg=c["bg_mid"],
                                     fg=c["text_muted"], wraplength=280,
                                     justify="left", font=("Helvetica", 9))
        self.result_label.pack(padx=12, pady=4)

    # ── 이벤트 핸들러 ─────────────────────────────────────
    def refresh(self):
        """탭 전환 시 새로고침"""
        books_all = []
        for shelf in self.app.reading_log.get("shelves", []):
            books_all.extend([b["title"] for b in shelf.get("books", [])])
        self.book_combo["values"] = books_all
        self._render_shelves()

    def _filter_books(self):
        self._render_shelves(self.search_var.get())

    def _add_book(self):
        dialog = BookAddDialog(self, self.app)
        self.wait_window(dialog)
        self.refresh()

    def _add_shelf(self):
        name = simpledialog.askstring("새 책장", "책장 이름:", parent=self)
        if name:
            self.app.reading_log["shelves"].append({"name": name, "books": []})
            self.app.save_all()
            self.refresh()

    def _edit_shelf(self, idx):
        shelf = self.app.reading_log["shelves"][idx]
        name = simpledialog.askstring("책장 이름 변경", "새 이름:",
                                      initialvalue=shelf["name"], parent=self)
        if name:
            self.app.reading_log["shelves"][idx]["name"] = name
            self.app.save_all()
            self.refresh()

    def _delete_shelf(self, idx):
        if messagebox.askyesno("책장 삭제", "정말 삭제하시겠습니까?"):
            self.app.reading_log["shelves"].pop(idx)
            self.app.save_all()
            self.refresh()

    def _open_book(self, book):
        BookDetailDialog(self, self.app, book)

    def _extract_words(self):
        title = self.selected_book_var.get()
        if not title:
            messagebox.showwarning("선택 필요", "책을 선택하세요.")
            return
        sp, ep = self.start_page.get(), self.end_page.get()
        self.result_label.config(text="⏳ n8n에서 단어 추출 중...")
        def run():
            resp = call_n8n("extract-words", {
                "book_title": title,
                "start_page": sp,
                "end_page":   ep,
                "cefr_level": self.app.user_cefr.get(),
            })
            words = resp.get("words", [])
            if words:
                # 검증 퀴즈 오픈
                self.after(0, lambda: self._open_verification_quiz(words, title, sp, ep))
            else:
                self.after(0, lambda: self.result_label.config(
                    text="단어를 찾지 못했습니다. 책 파일을 확인하세요."))
        threading.Thread(target=run, daemon=True).start()

    def _open_verification_quiz(self, words, title, sp, ep):
        VerificationQuizDialog(self, self.app, words, title, sp, ep)

    def _check_grammar(self):
        text = self.discussion_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("내용 없음", "영어 요약을 입력하세요.")
            return
        self.result_label.config(text="⏳ 문법 검사 중...")
        def run():
            resp = call_n8n("check-grammar", {"text": text})
            feedback = resp.get("feedback", "결과 없음")
            self.after(0, lambda: GrammarResultDialog(self, self.app, text, feedback))
        threading.Thread(target=run, daemon=True).start()

    def _finish_session(self):
        title = self.selected_book_var.get()
        if not title:
            messagebox.showwarning("선택 필요", "책을 선택하세요.")
            return
        session = {
            "date":       datetime.now().strftime("%Y-%m-%d"),
            "book":       title,
            "start_page": self.start_page.get(),
            "end_page":   self.end_page.get(),
            "discussion": self.discussion_text.get("1.0", tk.END).strip(),
        }
        self.app.reading_log.setdefault("sessions", []).append(session)
        self.app.save_all()
        self.result_label.config(text="🎉 오독완! 오늘의 독서가 기록되었습니다.")
        messagebox.showinfo("완료", f"오늘 {title} {session['start_page']}~{session['end_page']}쪽을 읽었습니다! 오독완!")


# ═══════════════════════════════════════════════════════════
#  탭 B : 단어장
# ═══════════════════════════════════════════════════════════
class VocabTab(tk.Frame):
    def __init__(self, parent, app: ReadingApp):
        super().__init__(parent, bg=app.colors["bg_dark"])
        self.app = app
        self._build()

    def _build(self):
        c = self.app.colors

        # 상단
        top = tk.Frame(self, bg=c["bg_mid"])
        top.pack(fill=tk.X)
        tk.Label(top, text="📖 단어장", font=("Helvetica", 16, "bold"),
                 bg=c["bg_mid"], fg=c["text"], pady=12).pack(side=tk.LEFT, padx=20)
        tk.Button(top, text="🖨 출력용 PDF", bg=c["accent"], fg="white",
                  bd=0, padx=10, pady=6, cursor="hand2",
                  command=self._export_print).pack(side=tk.RIGHT, padx=8, pady=8)
        tk.Button(top, text="+ 단어장 만들기", bg=c["accent2"], fg="white",
                  bd=0, padx=10, pady=6, cursor="hand2",
                  command=self._create_list).pack(side=tk.RIGHT, pady=8)

        # 필터 바
        fbar = tk.Frame(self, bg=c["bg_dark"])
        fbar.pack(fill=tk.X, padx=20, pady=6)
        tk.Label(fbar, text="검색:", bg=c["bg_dark"], fg=c["text"]).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *_: self.refresh())
        tk.Entry(fbar, textvariable=self.search_var, bg=c["bg_mid"], fg=c["text"],
                 insertbackground=c["text"], bd=0, width=20).pack(side=tk.LEFT, padx=6, ipady=3)

        tk.Label(fbar, text="책:", bg=c["bg_dark"], fg=c["text"]).pack(side=tk.LEFT, padx=(12,0))
        self.filter_book = tk.StringVar(value="전체")
        self.book_filter_cb = ttk.Combobox(fbar, textvariable=self.filter_book, width=18, state="readonly")
        self.book_filter_cb.pack(side=tk.LEFT, padx=4)
        self.book_filter_cb.bind("<<ComboboxSelected>>", lambda _: self.refresh())

        tk.Label(fbar, text="날짜:", bg=c["bg_dark"], fg=c["text"]).pack(side=tk.LEFT, padx=(12,0))
        self.filter_date = tk.StringVar(value="전체")
        self.date_filter_cb = ttk.Combobox(fbar, textvariable=self.filter_date, width=12, state="readonly")
        self.date_filter_cb.pack(side=tk.LEFT, padx=4)
        self.date_filter_cb.bind("<<ComboboxSelected>>", lambda _: self.refresh())

        # 메인 영역
        main = tk.Frame(self, bg=c["bg_dark"])
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # 왼쪽: 단어 목록
        left = tk.Frame(main, bg=c["bg_dark"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cols = ("단어", "뜻", "CEFR", "책", "날짜")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=20)
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100 if col != "단어" else 140)
        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.LEFT, fill=tk.Y)

        # 오른쪽: 나의 단어장 목록
        right = tk.Frame(main, bg=c["bg_mid"], width=220)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right.pack_propagate(False)
        tk.Label(right, text="나의 단어장들", font=("Helvetica", 12, "bold"),
                 bg=c["bg_mid"], fg=c["text"]).pack(pady=12)

        self.list_box = tk.Listbox(right, bg=c["bg_card"], fg=c["text"],
                                   selectbackground=c["accent"], bd=0,
                                   font=("Helvetica", 10), height=20)
        self.list_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.list_box.bind("<<ListboxSelect>>", self._on_list_select)

        tk.Button(right, text="단어장 삭제", bg=c["accent"], fg="white",
                  bd=0, cursor="hand2", command=self._delete_list).pack(fill=tk.X, padx=8, pady=4)

    def refresh(self):
        c = self.app.colors
        vocab = self.app.vocabulary

        # 필터 옵션 업데이트
        books = ["전체"] + list({w.get("book","") for w in vocab.get("words", [])})
        dates = ["전체"] + sorted({w.get("date","") for w in vocab.get("words", [])}, reverse=True)
        self.book_filter_cb["values"] = books
        self.date_filter_cb["values"] = dates

        # 단어장 목록
        self.list_box.delete(0, tk.END)
        for name in vocab.get("lists", {}).keys():
            self.list_box.insert(tk.END, name)

        self._refresh_tree()

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        search = self.search_var.get().lower()
        fbook  = self.filter_book.get()
        fdate  = self.filter_date.get()

        for w in self.app.vocabulary.get("words", []):
            if search and search not in w.get("word","").lower() and search not in w.get("meaning","").lower():
                continue
            if fbook != "전체" and w.get("book") != fbook:
                continue
            if fdate != "전체" and w.get("date") != fdate:
                continue
            self.tree.insert("", tk.END, values=(
                w.get("word",""),
                w.get("meaning",""),
                w.get("cefr",""),
                w.get("book",""),
                w.get("date",""),
            ))

    def _on_list_select(self, event):
        sel = self.list_box.curselection()
        if not sel:
            return
        name = self.list_box.get(sel[0])
        word_ids = self.app.vocabulary["lists"].get(name, [])
        # 해당 단어장 단어만 표시
        self.tree.delete(*self.tree.get_children())
        for w in self.app.vocabulary.get("words", []):
            if w.get("word") in word_ids:
                self.tree.insert("", tk.END, values=(
                    w.get("word",""), w.get("meaning",""),
                    w.get("cefr",""), w.get("book",""), w.get("date","")
                ))

    def _create_list(self):
        name = simpledialog.askstring("단어장 만들기", "단어장 이름:", parent=self)
        if name:
            # 선택된 단어들
            selected = [self.tree.item(i)["values"][0]
                        for i in self.tree.selection()]
            if not selected:
                messagebox.showinfo("안내", "단어장에 담을 단어를 선택하거나, 나중에 추가하세요.")
            self.app.vocabulary.setdefault("lists", {})[name] = selected
            self.app.save_all()
            self.refresh()

    def _delete_list(self):
        sel = self.list_box.curselection()
        if not sel:
            return
        name = self.list_box.get(sel[0])
        if messagebox.askyesno("삭제", f"'{name}' 단어장을 삭제할까요?"):
            self.app.vocabulary["lists"].pop(name, None)
            self.app.save_all()
            self.refresh()

    def _export_print(self):
        messagebox.showinfo("출력", "출력용 파일을 data/vocab_print.txt 로 저장합니다.")
        lines = []
        for w in self.app.vocabulary.get("words", []):
            lines.append(f"{w.get('word',''):20s} | {w.get('meaning','')}")
        out = os.path.join(DATA_DIR, "vocab_print.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        messagebox.showinfo("완료", f"저장 완료: {out}")


# ═══════════════════════════════════════════════════════════
#  탭 C : 퀴즈
# ═══════════════════════════════════════════════════════════
class QuizTab(tk.Frame):
    def __init__(self, parent, app: ReadingApp):
        super().__init__(parent, bg=app.colors["bg_dark"])
        self.app = app
        self.quiz_words = []
        self.quiz_idx   = 0
        self.score      = 0
        self._build()

    def _build(self):
        c = self.app.colors

        top = tk.Frame(self, bg=c["bg_mid"])
        top.pack(fill=tk.X)
        tk.Label(top, text="🧠 퀴즈", font=("Helvetica", 16, "bold"),
                 bg=c["bg_mid"], fg=c["text"], pady=12).pack(side=tk.LEFT, padx=20)

        # 퀴즈 설정 영역
        setup = tk.Frame(self, bg=c["bg_dark"])
        setup.pack(fill=tk.X, padx=20, pady=10)

        tk.Label(setup, text="퀴즈 종류:", bg=c["bg_dark"], fg=c["text"]).grid(row=0, column=0, sticky="w", padx=6)
        self.quiz_type = tk.StringVar(value="단어")
        for i, t in enumerate(["단어", "복습", "책 내용"]):
            tk.Radiobutton(setup, text=t, variable=self.quiz_type, value=t,
                           bg=c["bg_dark"], fg=c["text"],
                           selectcolor=c["bg_card"],
                           activebackground=c["bg_dark"]).grid(row=0, column=i+1, padx=4)

        tk.Label(setup, text="단어장:", bg=c["bg_dark"], fg=c["text"]).grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.quiz_list_var = tk.StringVar(value="전체")
        self.quiz_list_cb  = ttk.Combobox(setup, textvariable=self.quiz_list_var, width=22, state="readonly")
        self.quiz_list_cb.grid(row=1, column=1, columnspan=2, sticky="w")

        tk.Button(setup, text="▶ 퀴즈 시작", bg=c["accent"], fg="white",
                  bd=0, padx=14, pady=6, cursor="hand2",
                  command=self._start_quiz).grid(row=1, column=3, padx=12)

        # n8n 퀴즈 생성
        tk.Button(setup, text="🤖 AI 퀴즈 생성 (n8n)", bg=c["accent2"], fg="white",
                  bd=0, padx=10, pady=6, cursor="hand2",
                  command=self._ai_quiz).grid(row=1, column=4)

        # 퀴즈 영역
        self.quiz_frame = tk.Frame(self, bg=c["bg_dark"])
        self.quiz_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self._show_idle()

    def refresh(self):
        lists = ["전체"] + list(self.app.vocabulary.get("lists", {}).keys())
        self.quiz_list_cb["values"] = lists

    def _show_idle(self):
        c = self.app.colors
        for w in self.quiz_frame.winfo_children():
            w.destroy()
        tk.Label(self.quiz_frame, text="퀴즈를 시작하려면 위에서 설정 후 ▶ 버튼을 누르세요.",
                 bg=c["bg_dark"], fg=c["text_muted"], font=("Helvetica", 13)).pack(expand=True)

    def _start_quiz(self):
        c = self.app.colors
        list_name = self.quiz_list_var.get()
        all_words = self.app.vocabulary.get("words", [])

        if list_name == "전체":
            self.quiz_words = all_words
        else:
            ids = self.app.vocabulary.get("lists", {}).get(list_name, [])
            self.quiz_words = [w for w in all_words if w.get("word") in ids]

        if not self.quiz_words:
            messagebox.showinfo("단어 없음", "퀴즈를 만들 단어가 없습니다. 먼저 단어를 저장하세요.")
            return

        import random
        random.shuffle(self.quiz_words)
        self.quiz_idx = 0
        self.score    = 0
        self._show_quiz_card()

    def _show_quiz_card(self):
        c = self.app.colors
        for w in self.quiz_frame.winfo_children():
            w.destroy()

        if self.quiz_idx >= len(self.quiz_words):
            self._show_result()
            return

        word_data = self.quiz_words[self.quiz_idx]
        word   = word_data.get("word", "")
        meaning= word_data.get("meaning", "")

        # 진행 바
        prog = tk.Label(self.quiz_frame,
                        text=f"{self.quiz_idx+1} / {len(self.quiz_words)}  |  점수: {self.score}",
                        bg=c["bg_dark"], fg=c["text_muted"], font=("Helvetica", 11))
        prog.pack(pady=(10, 4))

        # 단어 카드
        card = tk.Frame(self.quiz_frame, bg=c["bg_card"],
                        relief="raised", bd=0)
        card.pack(padx=60, pady=20, fill=tk.BOTH, expand=True)

        tk.Label(card, text=word, font=("Helvetica", 40, "bold"),
                 bg=c["bg_card"], fg=c["text"]).pack(expand=True, pady=(40, 10))

        self.reveal_var = tk.BooleanVar(value=False)
        self.meaning_label = tk.Label(card, text="?  (뜻 보기를 누르세요)",
                                      font=("Helvetica", 18),
                                      bg=c["bg_card"], fg=c["text_muted"])
        self.meaning_label.pack(pady=(0, 40))

        # 버튼들
        btn_frame = tk.Frame(self.quiz_frame, bg=c["bg_dark"])
        btn_frame.pack(pady=8)

        tk.Button(btn_frame, text="💡 뜻 보기",
                  bg=c["bg_card"], fg=c["text"], bd=0, padx=16, pady=8,
                  cursor="hand2",
                  command=lambda: self.meaning_label.config(
                      text=meaning, fg=c["warning"])).pack(side=tk.LEFT, padx=8)
        tk.Button(btn_frame, text="✅ 알아요",
                  bg=c["success"], fg="black", bd=0, padx=16, pady=8,
                  cursor="hand2",
                  command=lambda: self._answer(True, word)).pack(side=tk.LEFT, padx=8)
        tk.Button(btn_frame, text="❌ 몰라요",
                  bg=c["accent"], fg="white", bd=0, padx=16, pady=8,
                  cursor="hand2",
                  command=lambda: self._answer(False, word)).pack(side=tk.LEFT, padx=8)

    def _answer(self, known: bool, word: str):
        if known:
            self.score += 1
        self.quiz_idx += 1
        self._show_quiz_card()

    def _show_result(self):
        c = self.app.colors
        for w in self.quiz_frame.winfo_children():
            w.destroy()
        total = len(self.quiz_words)
        pct   = int(self.score / total * 100) if total else 0
        tk.Label(self.quiz_frame,
                 text=f"🎉 퀴즈 완료!\n\n{total}개 중 {self.score}개 정답\n({pct}%)",
                 font=("Helvetica", 26, "bold"),
                 bg=c["bg_dark"], fg=c["success"]).pack(expand=True)
        tk.Button(self.quiz_frame, text="다시 하기",
                  bg=c["accent"], fg="white", bd=0, padx=16, pady=8,
                  cursor="hand2", command=self._start_quiz).pack(pady=16)

    def _ai_quiz(self):
        list_name = self.quiz_list_var.get()
        all_words = self.app.vocabulary.get("words", [])
        if list_name != "전체":
            ids = self.app.vocabulary.get("lists", {}).get(list_name, [])
            words = [w.get("word") for w in all_words if w.get("word") in ids]
        else:
            words = [w.get("word") for w in all_words]

        if not words:
            messagebox.showinfo("단어 없음", "단어를 먼저 저장하세요.")
            return

        def run():
            resp = call_n8n("generate-quiz", {"words": words[:20]})
            quizzes = resp.get("quizzes", [])
            if quizzes:
                self.after(0, lambda: AIQuizDialog(self, self.app, quizzes))
            else:
                self.after(0, lambda: messagebox.showinfo("결과", "AI 퀴즈를 생성할 수 없었습니다."))
        threading.Thread(target=run, daemon=True).start()


# ═══════════════════════════════════════════════════════════
#  다이얼로그들
# ═══════════════════════════════════════════════════════════

class BookAddDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("책 추가")
        self.geometry("420x380")
        c = app.colors
        self.configure(bg=c["bg_dark"])
        self.grab_set()
        self._build(c)

    def _build(self, c):
        tk.Label(self, text="새 책 추가", font=("Helvetica", 14, "bold"),
                 bg=c["bg_dark"], fg=c["text"]).pack(pady=16)

        fields = [("제목", "title"), ("저자", "author"), ("총 쪽수", "total_pages"),
                  ("간단한 줄거리", "synopsis")]
        self.vars = {}
        for label, key in fields:
            tk.Label(self, text=label, bg=c["bg_dark"], fg=c["text_muted"],
                     font=("Helvetica", 10)).pack(anchor="w", padx=24)
            if key == "synopsis":
                t = tk.Text(self, height=3, bg=c["bg_mid"], fg=c["text"],
                            insertbackground=c["text"], bd=0, font=("Helvetica", 10))
                t.pack(fill=tk.X, padx=24, pady=(2, 8))
                self.vars[key] = t
            else:
                v = tk.StringVar()
                tk.Entry(self, textvariable=v, bg=c["bg_mid"], fg=c["text"],
                         insertbackground=c["text"], bd=0,
                         font=("Helvetica", 10)).pack(fill=tk.X, padx=24, pady=(2, 8))
                self.vars[key] = v

        # 책장 선택
        tk.Label(self, text="책장 선택", bg=c["bg_dark"], fg=c["text_muted"],
                 font=("Helvetica", 10)).pack(anchor="w", padx=24)
        self.shelf_var = tk.StringVar()
        shelves = [s["name"] for s in self.app.reading_log.get("shelves", [])]
        if not shelves:
            shelves = ["내 책장"]
        ttk.Combobox(self, textvariable=self.shelf_var,
                     values=shelves, state="readonly").pack(fill=tk.X, padx=24, pady=(2,8))
        if shelves:
            self.shelf_var.set(shelves[0])

        # 텍스트 파일 연결
        tk.Button(self, text="📄 책 텍스트 파일 연결",
                  bg=c["bg_card"], fg=c["text"], bd=0, pady=4, cursor="hand2",
                  command=self._pick_file).pack(padx=24, pady=4)
        self.file_label = tk.Label(self, text="파일 없음", bg=c["bg_dark"],
                                   fg=c["text_muted"], font=("Helvetica", 9))
        self.file_label.pack()
        self.file_path = ""

        tk.Button(self, text="저장", bg=c["accent"], fg="white",
                  bd=0, padx=20, pady=6, cursor="hand2",
                  command=self._save).pack(pady=12)

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="책 텍스트 파일 선택",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
            initialdir=BOOKS_DIR
        )
        if path:
            self.file_path = path
            self.file_label.config(text=os.path.basename(path))

    def _save(self):
        title = self.vars["title"].get().strip()
        if not title:
            messagebox.showwarning("오류", "제목을 입력하세요.", parent=self)
            return
        synopsis = self.vars["synopsis"].get("1.0", tk.END).strip()
        book = {
            "title":       title,
            "author":      self.vars["author"].get().strip(),
            "total_pages": self.vars["total_pages"].get().strip(),
            "synopsis":    synopsis,
            "file_path":   self.file_path,
            "finished":    False,
            "added_date":  datetime.now().strftime("%Y-%m-%d"),
        }
        shelf_name = self.shelf_var.get()
        for shelf in self.app.reading_log.get("shelves", []):
            if shelf["name"] == shelf_name:
                shelf.setdefault("books", []).append(book)
                break
        else:
            self.app.reading_log["shelves"].append({"name": shelf_name, "books": [book]})

        self.app.save_all()
        self.destroy()


class BookDetailDialog(tk.Toplevel):
    def __init__(self, parent, app, book):
        super().__init__(parent)
        self.app  = app
        self.book = book
        self.title(book.get("title","책 상세"))
        self.geometry("600x500")
        c = app.colors
        self.configure(bg=c["bg_dark"])
        self.grab_set()
        self._build(c)

    def _build(self, c):
        tk.Label(self, text=self.book.get("title",""), font=("Helvetica", 18, "bold"),
                 bg=c["bg_dark"], fg=c["accent"]).pack(pady=(16,4))
        tk.Label(self, text=f"저자: {self.book.get('author','')}  |  완독: {'✓' if self.book.get('finished') else '✗'}",
                 bg=c["bg_dark"], fg=c["text_muted"]).pack()
        tk.Label(self, text=self.book.get("synopsis",""),
                 bg=c["bg_dark"], fg=c["text"], wraplength=540,
                 justify="center").pack(pady=8)

        tk.Label(self, text="독서 기록", font=("Helvetica", 12, "bold"),
                 bg=c["bg_dark"], fg=c["success"]).pack(anchor="w", padx=20, pady=(8,2))

        cols = ("날짜", "시작 쪽", "끝 쪽", "쪽수")
        tree = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        tree.pack(fill=tk.BOTH, padx=20, expand=True)

        sessions = [s for s in self.app.reading_log.get("sessions", [])
                    if s.get("book") == self.book.get("title")]
        for s in sessions:
            sp, ep = s.get("start_page",0), s.get("end_page",0)
            tree.insert("", tk.END, values=(s.get("date",""), sp, ep, ep-sp))

        btn_row = tk.Frame(self, bg=c["bg_dark"])
        btn_row.pack(pady=8)
        tk.Button(btn_row, text="완독 표시", bg=c["success"], fg="black",
                  bd=0, padx=10, pady=6, cursor="hand2",
                  command=self._mark_finished).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="퀴즈 바로 이동", bg=c["accent2"], fg="white",
                  bd=0, padx=10, pady=6, cursor="hand2",
                  command=lambda: [self.destroy(),
                                   parent.app._show_tab("quiz")]).pack(side=tk.LEFT, padx=6)

    def _mark_finished(self):
        self.book["finished"] = True
        self.app.save_all()
        messagebox.showinfo("완독!", f"'{self.book['title']}'을 완독했습니다! 🎉")
        self.destroy()


class VerificationQuizDialog(tk.Toplevel):
    """검증 퀴즈: 알아요/몰라요로 단어장 정제"""
    def __init__(self, parent, app, words, book_title, start_p, end_p):
        super().__init__(parent)
        self.app        = app
        self.words      = words  # [{"word":..,"meaning":..,"cefr":..}, ...]
        self.book_title = book_title
        self.start_p    = start_p
        self.end_p      = end_p
        self.idx        = 0
        self.unknown    = []
        self.title("검증 퀴즈")
        self.geometry("480x380")
        c = app.colors
        self.configure(bg=c["bg_dark"])
        self.grab_set()
        self._show_card()

    def _show_card(self):
        c = self.app.colors
        for w in self.winfo_children():
            w.destroy()

        if self.idx >= len(self.words):
            self._finish()
            return

        wd = self.words[self.idx]
        word    = wd.get("word","")
        meaning = wd.get("meaning","")

        tk.Label(self, text=f"{self.idx+1}/{len(self.words)}",
                 bg=c["bg_dark"], fg=c["text_muted"]).pack(pady=(16,4))
        tk.Label(self, text=word, font=("Helvetica", 36, "bold"),
                 bg=c["bg_dark"], fg=c["text"]).pack(pady=(24, 8))
        self.ml = tk.Label(self, text="(아래 버튼을 누르면 뜻이 나옵니다)",
                           font=("Helvetica", 14), bg=c["bg_dark"], fg=c["text_muted"])
        self.ml.pack()
        tk.Button(self, text="뜻 보기", bg=c["bg_card"], fg=c["text"],
                  bd=0, padx=10, pady=4, cursor="hand2",
                  command=lambda: self.ml.config(text=meaning, fg=c["warning"])).pack(pady=8)

        btn = tk.Frame(self, bg=c["bg_dark"])
        btn.pack(pady=16)
        tk.Button(btn, text="✅  알아요 (단어장에서 제외)",
                  bg=c["success"], fg="black", bd=0, padx=12, pady=8,
                  cursor="hand2",
                  command=lambda: self._answer(False)).pack(side=tk.LEFT, padx=8)
        tk.Button(btn, text="❌  몰라요 (단어장에 추가)",
                  bg=c["accent"], fg="white", bd=0, padx=12, pady=8,
                  cursor="hand2",
                  command=lambda: self._answer(True)).pack(side=tk.LEFT, padx=8)

    def _answer(self, add: bool):
        if add:
            self.unknown.append(self.words[self.idx])
        self.idx += 1
        self._show_card()

    def _finish(self):
        c = self.app.colors
        for w in self.winfo_children():
            w.destroy()
        tk.Label(self, text=f"검증 완료!\n모르는 단어 {len(self.unknown)}개를 단어장에 저장합니다.",
                 font=("Helvetica", 14), bg=c["bg_dark"], fg=c["success"]).pack(expand=True)
        today = datetime.now().strftime("%Y-%m-%d")
        for wd in self.unknown:
            wd["book"] = self.book_title
            wd["date"] = today
            self.app.vocabulary.setdefault("words", []).append(wd)
        self.app.save_all()
        tk.Button(self, text="닫기", bg=c["accent"], fg="white",
                  bd=0, padx=16, pady=6, cursor="hand2",
                  command=self.destroy).pack(pady=12)


class GrammarResultDialog(tk.Toplevel):
    def __init__(self, parent, app, original, feedback):
        super().__init__(parent)
        self.title("문법 검사 결과")
        self.geometry("580x440")
        c = app.colors
        self.configure(bg=c["bg_dark"])
        self.grab_set()

        tk.Label(self, text="원문", font=("Helvetica", 12, "bold"),
                 bg=c["bg_dark"], fg=c["text"]).pack(anchor="w", padx=20, pady=(16,2))
        orig_box = tk.Text(self, height=5, bg=c["bg_mid"], fg=c["text"],
                           font=("Helvetica", 10), bd=0, wrap="word")
        orig_box.insert("1.0", original)
        orig_box.config(state="disabled")
        orig_box.pack(fill=tk.X, padx=20, pady=(0,8))

        tk.Label(self, text="AI 피드백 (n8n → Claude)", font=("Helvetica", 12, "bold"),
                 bg=c["bg_dark"], fg=c["accent"]).pack(anchor="w", padx=20, pady=(8,2))
        fb_box = tk.Text(self, height=10, bg=c["bg_mid"], fg=c["success"],
                         font=("Helvetica", 10), bd=0, wrap="word")
        fb_box.insert("1.0", feedback)
        fb_box.config(state="disabled")
        fb_box.pack(fill=tk.BOTH, padx=20, pady=(0,8), expand=True)

        tk.Button(self, text="닫기", bg=c["bg_card"], fg=c["text"],
                  bd=0, padx=16, pady=6, cursor="hand2",
                  command=self.destroy).pack(pady=8)


class AIQuizDialog(tk.Toplevel):
    def __init__(self, parent, app, quizzes):
        super().__init__(parent)
        self.app     = app
        self.quizzes = quizzes
        self.idx     = 0
        self.score   = 0
        self.title("AI 퀴즈")
        self.geometry("520x420")
        c = app.colors
        self.configure(bg=c["bg_dark"])
        self.grab_set()
        self._show()

    def _show(self):
        c = self.app.colors
        for w in self.winfo_children():
            w.destroy()
        if self.idx >= len(self.quizzes):
            tk.Label(self, text=f"완료! {len(self.quizzes)}문제 중 {self.score}개 정답",
                     font=("Helvetica", 18, "bold"), bg=c["bg_dark"], fg=c["success"]).pack(expand=True)
            tk.Button(self, text="닫기", bg=c["accent"], fg="white",
                      bd=0, padx=14, pady=6, cursor="hand2",
                      command=self.destroy).pack(pady=12)
            return

        q = self.quizzes[self.idx]
        tk.Label(self, text=f"Q{self.idx+1}. {q.get('question','')}",
                 font=("Helvetica", 14), bg=c["bg_dark"], fg=c["text"],
                 wraplength=460, justify="left").pack(padx=20, pady=(24, 12))
        self.sel = tk.StringVar()
        for opt in q.get("options", []):
            tk.Radiobutton(self, text=opt, variable=self.sel, value=opt,
                           bg=c["bg_dark"], fg=c["text"],
                           selectcolor=c["bg_card"],
                           font=("Helvetica", 11),
                           activebackground=c["bg_dark"]).pack(anchor="w", padx=40, pady=2)
        tk.Button(self, text="제출", bg=c["accent"], fg="white",
                  bd=0, padx=14, pady=6, cursor="hand2",
                  command=lambda: self._submit(q.get("answer",""))).pack(pady=16)

    def _submit(self, answer):
        c = self.app.colors
        chosen = self.sel.get()
        if not chosen:
            return
        correct = chosen.strip() == answer.strip()
        if correct:
            self.score += 1
        msg = "✅ 정답!" if correct else f"❌ 오답. 정답: {answer}"
        messagebox.showinfo("결과", msg, parent=self)
        self.idx += 1
        self._show()


# ── 진입점 ────────────────────────────────────────────────
if __name__ == "__main__":
    app = ReadingApp()
    app.mainloop()