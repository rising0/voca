from io import BytesIO
import hashlib

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# =========================================================
# 기본 설정
# =========================================================

WORD_COLUMNS = ["eng", "kor"]

st.set_page_config(
    page_title="영단어 퀴즈",
    page_icon="📘",
)


# =========================================================
# 데이터 처리
# =========================================================

def clean_words(df: pd.DataFrame) -> pd.DataFrame:
    """빈 값과 중복 단어를 제거하고 문자열을 정리한다."""
    if df.empty:
        return pd.DataFrame(columns=WORD_COLUMNS)

    df = df.dropna(subset=WORD_COLUMNS).copy()

    for column in WORD_COLUMNS:
        df[column] = df[column].astype(str).str.strip()

    df = df[
        (df["eng"] != "")
        & (df["kor"] != "")
    ]

    # 영어 단어는 대소문자를 무시하고 중복 제거
    duplicate_key = df["eng"].str.casefold()
    df = df.loc[~duplicate_key.duplicated()]

    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_all_days(file_bytes: bytes) -> dict[str, pd.DataFrame]:
    """
    엑셀의 열을 두 개씩 묶어서 Day별 단어장으로 만든다.

    예:
    A-B열 → day1
    C-D열 → day2
    E-F열 → day3
    """
    raw = pd.read_excel(
        BytesIO(file_bytes),
        header=None,
    )

    days = {}

    # 영어/한글 두 열이 한 쌍이므로 마지막 단독 열은 제외
    for start_col in range(0, raw.shape[1] - 1, 2):
        header = raw.iat[0, start_col]

        if pd.isna(header) or not str(header).strip():
            day_name = f"day{start_col // 2 + 1}"
        else:
            day_name = str(header).strip()

        day_df = raw.iloc[
            1:,
            [start_col, start_col + 1],
        ].copy()

        day_df.columns = WORD_COLUMNS
        day_df = clean_words(day_df)

        if not day_df.empty:
            days[day_name] = day_df

    return days


def split_answers(text: str) -> set[str]:
    """쉼표로 구분된 정답을 집합으로 변환한다."""
    normalized_text = str(text).replace("，", ",")

    return {
        answer.strip()
        for answer in normalized_text.split(",")
        if answer.strip()
    }


# =========================================================
# 세션 상태
# =========================================================

def init_state() -> None:
    """세션 상태의 기본값을 설정한다."""
    default_state = {
        "file_hash": "",
        "current_day_name": "",
        "df": pd.DataFrame(columns=WORD_COLUMNS),
        "quiz_source": pd.DataFrame(columns=WORD_COLUMNS),
        "current_index": 0,
        "correct_count": 0,
        "answered": False,
        "wrong_words": [],
        "result": None,
        "input_version": 0,
    }

    for key, value in default_state.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_quiz_state() -> None:
    """메인 화면으로 돌아갈 때 퀴즈 상태를 초기화한다."""
    st.session_state.current_day_name = ""
    st.session_state.df = pd.DataFrame(columns=WORD_COLUMNS)
    st.session_state.quiz_source = pd.DataFrame(columns=WORD_COLUMNS)
    st.session_state.current_index = 0
    st.session_state.correct_count = 0
    st.session_state.answered = False
    st.session_state.wrong_words = []
    st.session_state.result = None
    st.session_state.input_version += 1


def start_quiz(day_name: str, df: pd.DataFrame) -> None:
    """선택한 단어장으로 새로운 퀴즈를 시작한다."""
    source_df = df.copy().reset_index(drop=True)

    st.session_state.current_day_name = day_name
    st.session_state.quiz_source = source_df
    st.session_state.df = source_df.sample(frac=1).reset_index(drop=True)
    st.session_state.current_index = 0
    st.session_state.correct_count = 0
    st.session_state.answered = False
    st.session_state.wrong_words = []
    st.session_state.result = None
    st.session_state.input_version += 1


def move_to_next_question() -> None:
    """다음 문제로 이동한다."""
    st.session_state.current_index += 1
    st.session_state.answered = False
    st.session_state.result = None
    st.session_state.input_version += 1


def check_answer(answer: str) -> None:
    """사용자가 입력한 답을 채점한다."""
    answer = answer.strip()

    if not answer:
        st.session_state.result = (
            "답을 입력해 주세요.",
            "info",
        )
        return

    index = st.session_state.current_index
    row = st.session_state.df.iloc[index]

    correct_text = str(row["kor"]).strip()

    user_answers = split_answers(answer)
    correct_answers = split_answers(correct_text)

    # 정답이 여러 개일 경우 그중 일부만 입력해도 정답 처리
    is_correct = (
        bool(user_answers)
        and user_answers.issubset(correct_answers)
    )

    if is_correct:
        st.session_state.correct_count += 1
        st.session_state.result = (
            f"정답 · {correct_text}",
            "success",
        )
    else:
        st.session_state.wrong_words.append(
            {
                "eng": row["eng"],
                "kor": row["kor"],
            }
        )

        st.session_state.result = (
            f"오답 · {correct_text}",
            "error",
        )

    st.session_state.answered = True


# =========================================================
# 공통 UI
# =========================================================

def show_result_message() -> None:
    """정답, 오답 또는 안내 메시지를 표시한다."""
    if not st.session_state.result:
        return

    message, message_type = st.session_state.result

    if message_type == "success":
        st.success(message)
    elif message_type == "error":
        st.error(message)
    else:
        st.info(message)


def install_enter_handler() -> None:
    """
    입력창 밖에서도 Enter로 현재 폼 버튼을 누르게 한다.

    입력창에 포커스가 있을 때는 Streamlit form의 기본 Enter 제출을
    사용하고, 입력창 밖에 있을 때만 버튼을 직접 클릭한다.
    """
    components.html(
        """
        <script>
        const parentWindow = window.parent;
        const parentDocument = parentWindow.document;

        // 이전 iframe에서 등록한 이벤트가 있으면 제거
        if (parentWindow.quizEnterHandler) {
            parentDocument.removeEventListener(
                "keydown",
                parentWindow.quizEnterHandler
            );
        }

        parentWindow.quizEnterHandler = function(event) {
            if (event.key !== "Enter") {
                return;
            }

            // 한글 입력 조합 중 Enter는 무시
            if (event.isComposing || event.keyCode === 229) {
                return;
            }

            const targetTag = event.target.tagName;

            // 입력창에서는 Streamlit form의 기본 Enter 제출 사용
            if (
                targetTag === "INPUT"
                || targetTag === "TEXTAREA"
                || targetTag === "BUTTON"
            ) {
                return;
            }

            const buttons = parentDocument.querySelectorAll("button");

            for (const button of buttons) {
                const buttonText = button.innerText.trim();

                if (
                    buttonText.includes("정답 확인")
                    || buttonText.includes("다음 문제")
                ) {
                    event.preventDefault();
                    button.click();
                    break;
                }
            }
        };

        parentDocument.addEventListener(
            "keydown",
            parentWindow.quizEnterHandler
        );
        </script>
        """,
        height=0,
    )


# =========================================================
# 메인 화면
# =========================================================

def show_main_screen(days: dict[str, pd.DataFrame]) -> None:
    """Day 선택 화면을 표시한다."""
    st.subheader("학습할 Day를 선택하세요")

    day_names = list(days.keys())

    for start_index in range(0, len(day_names), 3):
        columns = st.columns(3)
        current_days = day_names[start_index:start_index + 3]

        for column, day_name in zip(columns, current_days):
            word_count = len(days[day_name])

            with column:
                if st.button(
                    f"{day_name}\n\n{word_count}단어",
                    key=f"day_button_{day_name}",
                    use_container_width=True,
                ):
                    start_quiz(day_name, days[day_name])
                    st.rerun()

    st.divider()

    all_words = clean_words(
        pd.concat(
            days.values(),
            ignore_index=True,
        )
    )

    if st.button(
        f"전체 Day 학습\n\n{len(all_words)}단어",
        key="all_days_button",
        use_container_width=True,
    ):
        start_quiz("전체 Day", all_words)
        st.rerun()

    st.caption(
        "엑셀 오른쪽에 영어·한글 두 열씩 추가하면 "
        "day3, day4도 자동으로 생성됩니다."
    )


# =========================================================
# 퀴즈 완료 화면
# =========================================================

def show_complete_screen() -> None:
    """퀴즈 결과 화면을 표시한다."""
    total_count = len(st.session_state.df)
    correct_count = st.session_state.correct_count
    wrong_count = len(st.session_state.wrong_words)

    accuracy = (
        correct_count / total_count * 100
        if total_count
        else 0
    )

    st.subheader("퀴즈 완료")

    st.write(
        f"{total_count}문제 중 "
        f"{correct_count}문제를 맞혔습니다."
    )
    st.write(f"정답률: **{accuracy:.1f}%**")
    st.write(f"틀린 문제: **{wrong_count}개**")

    retry_column, wrong_column, main_column = st.columns(3)

    with retry_column:
        if st.button(
            "같은 문제 다시 풀기",
            use_container_width=True,
        ):
            start_quiz(
                st.session_state.current_day_name,
                st.session_state.quiz_source,
            )
            st.rerun()

    with wrong_column:
        if st.button(
            "틀린 문제 다시 풀기",
            use_container_width=True,
            disabled=wrong_count == 0,
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

    with main_column:
        if st.button(
            "메인 화면",
            use_container_width=True,
        ):
            clear_quiz_state()
            st.rerun()


# =========================================================
# 퀴즈 화면
# =========================================================

def show_quiz_header(index: int, total_count: int) -> None:
    """퀴즈 화면 상단을 표시한다."""
    left_column, center_column, right_column = st.columns(
        [1, 2, 1]
    )

    with left_column:
        if st.button(
            "메인 화면",
            key="quiz_main_button",
        ):
            clear_quiz_state()
            st.rerun()

    with center_column:
        day_name = st.session_state.current_day_name

        st.markdown(
            f"""
            <h4 style="text-align: center;">
                {day_name}
            </h4>
            """,
            unsafe_allow_html=True,
        )

    with right_column:
        st.write(f"{index + 1} / {total_count}")


def show_quiz_screen() -> None:
    """현재 문제와 입력 폼을 표시한다."""
    df = st.session_state.df
    index = st.session_state.current_index
    total_count = len(df)

    if index >= total_count:
        show_complete_screen()
        return

    row = df.iloc[index]

    show_quiz_header(index, total_count)

    st.divider()

    st.markdown(
        f"""
        <h1 style="text-align: center;">
            {row["eng"]}
        </h1>
        """,
        unsafe_allow_html=True,
    )

    # 문제·채점 상태가 변경될 때 새로운 폼으로 생성
    form_key = (
        f"quiz_form_"
        f"{index}_"
        f"{st.session_state.answered}_"
        f"{st.session_state.input_version}"
    )

    button_text = (
        "다음 문제"
        if st.session_state.answered
        else "정답 확인"
    )

    with st.form(
        key=form_key,
        clear_on_submit=False,
    ):
        answer = st.text_input(
            "뜻을 입력하세요",
            placeholder="뜻을 입력한 후 Enter를 누르세요",
            disabled=st.session_state.answered,
        )

        submitted = st.form_submit_button(
            button_text,
            use_container_width=True,
        )

    if submitted:
        if st.session_state.answered:
            move_to_next_question()
        else:
            check_answer(answer)

        st.rerun()

    show_result_message()

    st.write(
        f"현재 정답: "
        f"**{st.session_state.correct_count}개**"
    )

    install_enter_handler()


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
current_file_hash = hashlib.sha256(file_bytes).hexdigest()

# 다른 파일이 업로드되면 이전 퀴즈 상태 제거
if st.session_state.file_hash != current_file_hash:
    clear_quiz_state()
    st.session_state.file_hash = current_file_hash

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


if not st.session_state.current_day_name:
    show_main_screen(days)
else:
    show_quiz_screen()
