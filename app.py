import sys

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

FILE_PATH = r"D:\workspace\study\word\word.xlsx"
FONT_NAME = "맑은 고딕"
WORD_COLUMNS = ["eng", "kor"]


class WordQuizApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("영단어 퀴즈")
        self.setFixedSize(560, 500)
        self.set_app_style()

        self.days = self.load_all_days()
        self.quiz_source = pd.DataFrame(columns=WORD_COLUMNS)
        self.df = pd.DataFrame(columns=WORD_COLUMNS)
        self.current_day_name = ""
        self.current_index = 0
        self.correct_count = 0
        self.answered = False
        self.wrong_words = []

        self.stack = QStackedWidget()
        self.main_page = QWidget()
        self.quiz_page = QWidget()

        self.create_main_page()
        self.create_quiz_page()

        self.stack.addWidget(self.main_page)
        self.stack.addWidget(self.quiz_page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

        self.show_main_page()

    # 엑셀 처리 ---------------------------------------------------------
    def load_all_days(self):
        try:
            raw = pd.read_excel(FILE_PATH, header=None)
        except FileNotFoundError:
            QMessageBox.critical(
                self, "파일 오류", f"엑셀 파일을 찾을 수 없습니다.\n\n{FILE_PATH}"
            )
            return {}
        except Exception as error:
            QMessageBox.critical(
                self,
                "파일 오류",
                f"엑셀 파일을 불러오는 중 오류가 발생했습니다.\n\n{error}",
            )
            return {}

        days = {}

        # 영어/한글 두 열을 한 Day로 처리
        for col in range(0, raw.shape[1] - 1, 2):
            header = raw.iat[0, col]
            day_name = (
                f"day{col // 2 + 1}"
                if pd.isna(header) or not str(header).strip()
                else str(header).strip()
            )

            day_df = raw.iloc[1:, [col, col + 1]].copy()
            day_df.columns = WORD_COLUMNS
            day_df = self.clean_words(day_df)

            if not day_df.empty:
                days[day_name] = day_df

        return days

    @staticmethod
    def clean_words(df):
        df = df.dropna(subset=WORD_COLUMNS).copy()
        df[WORD_COLUMNS] = df[WORD_COLUMNS].apply(
            lambda column: column.astype(str).str.strip()
        )
        df = df[(df["eng"] != "") & (df["kor"] != "")]
        duplicate_key = df["eng"].str.casefold()
        return df.loc[~duplicate_key.duplicated()].reset_index(drop=True)

    def get_all_words(self):
        if not self.days:
            return pd.DataFrame(columns=WORD_COLUMNS)
        return self.clean_words(pd.concat(self.days.values(), ignore_index=True))

    # 화면 공통 ---------------------------------------------------------
    @staticmethod
    def make_label(text="", size=10, bold=False, color=None):
        label = QLabel(text)
        label.setFont(
            QFont(FONT_NAME, size, QFont.Weight.Bold if bold else QFont.Weight.Normal)
        )
        if color:
            label.setStyleSheet(f"color: {color};")
        return label

    def set_app_style(self):
        self.setStyleSheet(
            """
            QWidget {
                background-color: #f4f4f4;
                color: #222222;
                font-family: "맑은 고딕";
            }
            QLineEdit {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 10px;
            }
            QLineEdit:focus { border: 2px solid #3b8ed0; }
            QPushButton {
                background-color: #3b8ed0;
                color: white;
                border: none;
                border-radius: 7px;
                padding: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #367eb8; }
            QPushButton:pressed { background-color: #2d6d9f; }
            QPushButton#secondaryButton { background-color: #777777; }
            QPushButton#secondaryButton:hover { background-color: #666666; }
            """
        )

    # 메인 화면 ---------------------------------------------------------
    def create_main_page(self):
        layout = QVBoxLayout(self.main_page)
        layout.setContentsMargins(45, 40, 45, 40)

        title = self.make_label("영단어 퀴즈", 27, True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = self.make_label("학습할 Day를 선택하세요.", 11, color="#777777")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(28)

        day_grid = QGridLayout()
        day_grid.setSpacing(12)

        for index, (day_name, words) in enumerate(self.days.items()):
            button = QPushButton(f"{day_name}\n{len(words)}단어")
            button.setMinimumHeight(66)
            button.clicked.connect(
                lambda _checked=False, name=day_name: self.start_day_quiz(name)
            )
            day_grid.addWidget(button, index // 3, index % 3)

        layout.addLayout(day_grid)
        layout.addSpacing(18)

        all_button = QPushButton("전체 Day 학습")
        all_button.setMinimumHeight(52)
        all_button.setEnabled(bool(self.days))
        all_button.clicked.connect(self.start_all_quiz)
        layout.addWidget(all_button)
        layout.addStretch()

        info = self.make_label(
            "엑셀 오른쪽에 두 열씩 day3, day4를 추가하면\n"
            "다음 실행부터 버튼이 자동으로 생성됩니다.",
            9,
            color="#888888",
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        if not self.days:
            warning = self.make_label(
                "불러온 단어가 없습니다. 엑셀 파일을 확인하세요.",
                color="#c0392b",
            )
            warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.insertWidget(3, warning)

    def show_main_page(self):
        self.stack.setCurrentWidget(self.main_page)

    def start_day_quiz(self, day_name):
        words = self.days.get(day_name)
        if words is not None:
            self.start_quiz(day_name, words)

    def start_all_quiz(self):
        self.start_quiz("전체 Day", self.get_all_words())

    # 퀴즈 화면 ---------------------------------------------------------
    def create_quiz_page(self):
        layout = QVBoxLayout(self.quiz_page)
        layout.setContentsMargins(45, 30, 45, 35)

        top_layout = QHBoxLayout()
        self.home_button = QPushButton("메인 화면")
        self.home_button.setObjectName("secondaryButton")
        self.home_button.setFixedWidth(100)
        self.home_button.clicked.connect(self.confirm_go_home)

        self.day_label = self.make_label(size=11, bold=True)
        self.progress_label = self.make_label(color="#777777")

        top_layout.addWidget(self.home_button)
        top_layout.addStretch()
        top_layout.addWidget(self.day_label)
        top_layout.addStretch()
        top_layout.addWidget(self.progress_label)
        layout.addLayout(top_layout)
        layout.addSpacing(45)

        self.word_label = self.make_label(size=25, bold=True)
        self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.word_label)
        layout.addSpacing(30)

        self.answer_entry = QLineEdit()
        self.answer_entry.setFont(QFont(FONT_NAME, 16))
        self.answer_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.answer_entry.setFixedHeight(50)
        self.answer_entry.setPlaceholderText("뜻을 입력하세요")
        self.answer_entry.returnPressed.connect(self.handle_enter)
        layout.addWidget(self.answer_entry)
        layout.addSpacing(15)

        self.submit_button = QPushButton("정답 확인")
        self.submit_button.setFixedHeight(48)
        self.submit_button.clicked.connect(self.handle_enter)
        layout.addWidget(self.submit_button)
        layout.addSpacing(15)

        self.result_label = self.make_label(size=11)
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        layout.addStretch()

        self.score_label = self.make_label(color="#777777")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.score_label)

        finish_layout = QHBoxLayout()
        self.retry_button = QPushButton("같은 문제 다시 풀기")
        self.wrong_retry_button = QPushButton("틀린 문제 다시 풀기")
        self.finish_home_button = QPushButton("메인 화면")
        self.finish_home_button.setObjectName("secondaryButton")

        self.retry_button.clicked.connect(self.restart_current_quiz)
        self.wrong_retry_button.clicked.connect(self.start_wrong_quiz)
        self.finish_home_button.clicked.connect(self.show_main_page)

        self.finish_buttons = (
            self.retry_button,
            self.wrong_retry_button,
            self.finish_home_button,
        )
        for button in self.finish_buttons:
            finish_layout.addWidget(button)

        layout.addLayout(finish_layout)
        self.set_finish_buttons_visible(False)

    def start_quiz(self, day_name, dataframe):
        if dataframe.empty:
            QMessageBox.information(self, "알림", "선택한 Day에 단어가 없습니다.")
            return

        self.current_day_name = day_name
        self.quiz_source = dataframe.copy().reset_index(drop=True)
        self.df = self.quiz_source.sample(frac=1).reset_index(drop=True)
        self.current_index = 0
        self.correct_count = 0
        self.answered = False
        self.wrong_words.clear()

        self.word_label.setFont(QFont(FONT_NAME, 25, QFont.Weight.Bold))
        self.set_quiz_controls_visible(True)
        self.set_finish_buttons_visible(False)
        self.stack.setCurrentWidget(self.quiz_page)
        self.show_question()

    def show_question(self):
        if self.current_index >= len(self.df):
            self.finish_quiz()
            return

        self.answered = False
        row = self.df.iloc[self.current_index]

        self.day_label.setText(self.current_day_name)
        self.word_label.setText(str(row["eng"]))
        self.progress_label.setText(f"{self.current_index + 1} / {len(self.df)}")
        self.score_label.setText(f"정답 {self.correct_count}개")
        self.result_label.clear()

        self.answer_entry.clear()
        self.answer_entry.setReadOnly(False)
        self.answer_entry.setFocus()
        self.submit_button.setText("정답 확인")

    def handle_enter(self):
        if self.answered:
            self.current_index += 1
            self.show_question()
        else:
            self.check_answer()

    @staticmethod
    def split_answers(text):
        return {
            item.strip()
            for item in str(text).replace("，", ",").split(",")
            if item.strip()
        }

    def check_answer(self):
        answer = self.answer_entry.text().strip()
        if not answer:
            self.show_result("답을 입력해 주세요.", "#777777")
            return

        row = self.df.iloc[self.current_index]
        korean = str(row["kor"]).strip()
        user_answers = self.split_answers(answer)
        correct_answers = self.split_answers(korean)
        is_correct = bool(user_answers) and user_answers.issubset(correct_answers)

        if is_correct:
            self.correct_count += 1
            self.show_result(f"정답 · {korean}", "#16803c")
        else:
            self.wrong_words.append(row[WORD_COLUMNS].to_dict())
            self.show_result(f"오답 · {korean}", "#c0392b")

        self.answered = True
        self.answer_entry.setReadOnly(True)
        self.score_label.setText(f"정답 {self.correct_count}개")
        self.submit_button.setText("다음 문제")

    def show_result(self, text, color):
        self.result_label.setText(text)
        self.result_label.setStyleSheet(f"color: {color};")

    def finish_quiz(self):
        total = len(self.df)
        accuracy = self.correct_count / total * 100 if total else 0

        self.progress_label.setText("완료")
        self.word_label.setText("퀴즈 완료")
        self.word_label.setFont(QFont(FONT_NAME, 22, QFont.Weight.Bold))
        self.set_quiz_controls_visible(False)

        self.show_result(
            f"{total}문제 중 {self.correct_count}문제를 맞혔습니다.\n"
            f"정답률 {accuracy:.1f}%\n"
            f"틀린 문제 {len(self.wrong_words)}개",
            "#222222",
        )
        self.score_label.clear()
        self.wrong_retry_button.setEnabled(bool(self.wrong_words))
        self.set_finish_buttons_visible(True)

    def restart_current_quiz(self):
        self.start_quiz(self.current_day_name, self.quiz_source)

    def start_wrong_quiz(self):
        if self.wrong_words:
            self.start_quiz("틀린 문제 복습", pd.DataFrame(self.wrong_words))

    def confirm_go_home(self):
        reply = QMessageBox.question(
            self,
            "메인 화면",
            "현재 퀴즈를 종료하고 메인 화면으로 돌아갈까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.show_main_page()

    def set_quiz_controls_visible(self, visible):
        self.answer_entry.setVisible(visible)
        self.submit_button.setVisible(visible)
        self.home_button.setVisible(visible)

    def set_finish_buttons_visible(self, visible):
        for button in self.finish_buttons:
            button.setVisible(visible)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WordQuizApp()
    window.show()
    sys.exit(app.exec())
