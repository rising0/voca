from io import BytesIO
import hashlib

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


WORD_COLUMNS = ["eng", "kor"]

DEFAULT_STATE = {
    "file_hash": "",
    "current_day": "",
    "quiz_words": pd.DataFrame(columns=WORD_COLUMNS),
    "original_words": pd.DataFrame(columns=WORD_COLUMNS),
    "current_index": 0,
    "correct_count": 0,
    "answered": False,
    "wrong_words": [],
    "message": "",
    "message_type": "",
}

st.set_page_config(
    page_title="영단어 퀴즈",
    page_icon="📘",
)


# =========================================================
# 데이터 처리
# =========================================================

def clean_words(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=WORD_COLUMNS)

    df = df.dropna(subset=WORD_COLUMNS).copy()

    df[WORD_COLUMNS] = df[WORD_COLUMNS].apply(
        lambda column: column.astype(str).str.strip()
    )

    df = df[
        df["eng"].ne("")
        & df["kor"].ne("")
    ]

    return (
        df.loc[
            ~df["eng"].str.casefold().duplicated()
        ]
        .reset_index(drop=True)
    )


@st.cache_data(show_spinner=False)
def load_all_days(file_bytes: bytes) -> dict[str, pd.DataFrame]:
    raw = pd.read_excel(
        BytesIO(file_bytes),
        header=None,
    )

    days = {}

    for column in range(0, raw.shape[1] - 1, 2):
        header = raw.iat[0, column]

        day_name = (
            str(header).strip()
            if pd.notna(header) and str(header).strip()
            else f"day{column // 2 + 1}"
        )

        day_words = raw.iloc[
            1:,
            [column, column + 1],
        ].copy()

        day_words.columns = WORD_COLUMNS
        day_words = clean_words(day_words)

        if not day_words.empty:
            days[day_name] = day_words

    return days


def split_answers(text: str) -> set[str]:
    return {
        item.strip()
        for item in str(text).replace("，", ",").split(",")
        if item.strip()
    }


# =========================================================
# 상태 관리
# =========================================================

def init_state() -> None:
    for key, value in DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_state(main_screen: bool = False) -> None:
    st.session_state.current_index = 0
    st.session_state.correct_count = 0
    st.session_state.answered = False
    st.session_state.wrong_words = []
    st.session_state.message = ""
    st.session_state.message_type = ""

    if main_screen:
        st.session_state.current_day = ""
        st.session_state.quiz_words = pd.DataFrame(
            columns=WORD_COLUMNS
        )
        st.session_state.original_words = pd.DataFrame(
            columns=WORD_COLUMNS
        )


def start_quiz(day_name: str, words: pd.DataFrame) -> None:
    reset_state()

    source = words.reset_index(drop=True)

    st.session_state.current_day = day_name
    st.session_state.original_words = source
    st.session_state.quiz_words = source.sample(
        frac=1
    ).reset_index(drop=True)


def next_question() -> None:
    st.session_state.current_index += 1
    st.session_state.answered = False
    st.session_state.message = ""
    st.session_state.message_type = ""


def check_answer(answer: str) -> None:
    answer = answer.strip()

    if not answer:
        st.session_state.message = "답을 입력해 주세요."
        st.session_state.message_type = "info"
        return

    row = st.session_state.quiz_words.iloc[
        st.session_state.current_index
    ]

    correct_text = str(row["kor"]).strip()

    user_answers = split_answers(answer)
    correct_answers = split_answers(correct_text)

    is_correct = (
        bool(user_answers)
        and user_answers.issubset(correct_answers)
    )

    if is_correct:
        st.session_state.correct_count += 1
        st.session_state.message = f"정답 · {correct_text}"
        st.session_state.message_type = "success"

    else:
        st.session_state.wrong_words.append(
            {
                "eng": row["eng"],
                "kor": row["kor"],
            }
        )

        st.session_state.message = f"오답 · {correct_text}"
        st.session_state.message_type = "error"

    st.session_state.answered = True


# =========================================================
# 키보드 처리
# =========================================================

def install_keyboard_handler() -> None:
    components.html(
        """
        <script>
        const win = window.parent;
        const doc = win.document;

        function getAnswerInput() {
            return doc.querySelector(
                'input[aria-label="뜻을 입력하세요"]:not([disabled])'
            );
        }

        function focusInput() {
            const input = getAnswerInput();

            if (!input) {
                return false;
            }

            input.focus({ preventScroll: true });

            const end = input.value.length;

            try {
                input.setSelectionRange(end, end);
            } catch (_) {}

            return true;
        }

        if (win.quizFocusObserver) {
            win.quizFocusObserver.disconnect();
        }

        if (!focusInput()) {
            win.quizFocusObserver = new MutationObserver(() => {
                if (focusInput()) {
                    win.quizFocusObserver.disconnect();
                }
            });

            win.quizFocusObserver.observe(
                doc.body,
                {
                    childList: true,
                    subtree: true
                }
            );
        }

        if (win.quizEnterHandler) {
            doc.removeEventListener(
                "keydown",
                win.quizEnterHandler,
                true
            );
        }

        win.quizEnterHandler = function(event) {
            if (
                event.key !== "Enter"
                || event.isComposing
                || event.keyCode === 229
                || event.shiftKey
                || event.ctrlKey
                || event.altKey
                || event.metaKey
            ) {
                return;
            }

            const tagName = event.target?.tagName;

            if (
                tagName === "INPUT"
                || tagName === "TEXTAREA"
            ) {
                return;
            }

            const button = [...doc.querySelectorAll("button")]
                .find((item) => {
                    const text = item.innerText.trim();

                    return (
                        !item.disabled
                        && (
                            text.includes("정답 확인")
                            || text.includes("다음 문제")
                        )
                    );
                });

            if (button) {
                event.preventDefault();
                event.stopPropagation();
                button.click();
            }
        };

        doc.addEventListener(
            "keydown",
            win.quizEnterHandler,
            true
        );
        </script>
        """,
        height=0,
    )


# =========================================================
# 메시지
# =========================================================

def show_message() -> None:
    message = st.session_state.message
    message_type = st.session_state.message_type

    if not message:
        return

    getattr(st, message_type)(message)


# =========================================================
# 메인 화면
# =========================================================

def show_main_screen(
    days: dict[str, pd.DataFrame],
) -> None:
    st.subheader("학습할 Day를 선택하세요")

    day_names = list(days)

    for start in range(0, len(day_names), 3):
        columns = st.columns(3)

        for column, day_name in zip(
            columns,
            day_names[start:start + 3],
        ):
            with column:
                if st.button(
                    f"{day_name}\n\n"
                    f"{len(days[day_name])}단어",
                    key=f"day_{day_name}",
                    use_container_width=True,
                ):
                    start_quiz(
                        day_name,
                        days[day_name],
                    )
                    st.rerun()

    st.divider()

    all_words = clean_words(
        pd.concat(
            days.values(),
            ignore_index=True,
        )
    )

    if st.button(
        f"전체 Day 학습\n\n"
        f"{len(all_words)}단어",
        use_container_width=True,
    ):
        start_quiz(
            "전체 Day",
            all_words,
        )
        st.rerun()

    st.caption(
        "엑셀 오른쪽에 영어와 한글 열을 두 개씩 "
        "추가하면 Day가 자동으로 생성됩니다."
    )


# =========================================================
# 결과 화면
# =========================================================

def show_complete_screen() -> None:
    total = len(st.session_state.quiz_words)
    correct = st.session_state.correct_count
    wrong = len(st.session_state.wrong_words)

    accuracy = correct / total * 100 if total else 0

    st.subheader("퀴즈 완료")
    st.write(f"{total}문제 중 {correct}문제를 맞혔습니다.")
    st.write(f"정답률: **{accuracy:.1f}%**")
    st.write(f"틀린 문제: **{wrong}개**")

    retry_col, wrong_col, main_col = st.columns(3)

    with retry_col:
        if st.button(
            "같은 문제 다시 풀기",
            use_container_width=True,
        ):
            start_quiz(
                st.session_state.current_day,
                st.session_state.original_words,
            )
            st.rerun()

    with wrong_col:
        if st.button(
            "틀린 문제 다시 풀기",
            disabled=wrong == 0,
            use_container_width=True,
        ):
            wrong_df = pd.DataFrame(
                st.session_state.wrong_words,
                columns=WORD_COLUMNS,
            )

            start_quiz(
                "틀린 문제 복습",
                wrong_df,
            )
            st.rerun()

    with main_col:
        if st.button(
            "메인 화면",
            use_container_width=True,
        ):
            reset_state(main_screen=True)
            st.rerun()


# =========================================================
# 퀴즈 화면
# =========================================================

def show_quiz_screen() -> None:
    words = st.session_state.quiz_words
    index = st.session_state.current_index

    if index >= len(words):
        show_complete_screen()
        return

    row = words.iloc[index]

    left, center, right = st.columns([1, 2, 1])

    with left:
        if st.button(
            "메인 화면",
            key="quiz_main",
        ):
            reset_state(main_screen=True)
            st.rerun()

    with center:
        st.markdown(
            f"""
            <h4 style="text-align:center;">
                {st.session_state.current_day}
            </h4>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.write(f"{index + 1} / {len(words)}")

    st.divider()

    st.markdown(
        f"""
        <h1 style="text-align:center;">
            {row["eng"]}
        </h1>
        """,
        unsafe_allow_html=True,
    )

    button_text = (
        "다음 문제"
        if st.session_state.answered
        else "정답 확인"
    )

    with st.form(
        key=f"quiz_form_{index}_{st.session_state.answered}",
    ):
        answer = st.text_input(
            "뜻을 입력하세요",
            key=f"answer_{index}_{st.session_state.answered}",
            placeholder="뜻을 입력한 후 Enter를 누르세요",
            disabled=st.session_state.answered,
        )

        submitted = st.form_submit_button(
            button_text,
            use_container_width=True,
        )

    if submitted:
        if st.session_state.answered:
            next_question()
        else:
            check_answer(answer)

        st.rerun()

    show_message()

    st.write(
        f"현재 정답: "
        f"**{st.session_state.correct_count}개**"
    )

    install_keyboard_handler()


# =========================================================
# 앱 실행
# =========================================================

init_state()

st.title("📘 영단어 퀴즈")

uploaded_file = st.file_uploader(
    "엑셀 파일을 업로드하세요",
    type=["xlsx"],
)

if uploaded_file is None:
    st.info(
        "word.xlsx 파일을 업로드하면 "
        "Day 선택 화면이 나타납니다."
    )
    st.stop()


file_bytes = uploaded_file.getvalue()
file_hash = hashlib.sha256(file_bytes).hexdigest()

if st.session_state.file_hash != file_hash:
    reset_state(main_screen=True)
    st.session_state.file_hash = file_hash


try:
    days = load_all_days(file_bytes)

except Exception as error:
    st.error(
        "엑셀 파일을 불러오는 중 오류가 발생했습니다."
        f"\n\n{error}"
    )
    st.stop()


if not days:
    st.error(
        "불러온 단어가 없습니다. "
        "엑셀 구조를 확인하세요."
    )
    st.stop()


if st.session_state.current_day:
    show_quiz_screen()
else:
    show_main_screen(days)
