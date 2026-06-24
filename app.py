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
    """빈 값과 중복 단어를 제거한다."""
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
    """엑셀 파일의 열을 두 개씩 묶어서 Day별 단어장으로 만든다."""
    raw = pd.read_excel(
        BytesIO(file_bytes),
        header=None,
    )

    days = {}

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
    """쉼표로 구분된 뜻을 집합으로 변환한다."""
    normalized_text = str(text).replace("，", ",")

    return {
        item.strip()
        for item in normalized_text.split(",")
        if item.strip()
    }


# =========================================================
# 세션 상태
# =========================================================

def init_state() -> None:
    """필요한 세션 상태를 초기화한다."""
    defaults = {
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

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_quiz_state() -> None:
    """퀴즈를 종료하고 메인 화면 상태로 돌아간다."""
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
    """선택한 단어장으로 퀴즈를 시작한다."""
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
    """입력된 답을 채점한다."""
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

    # 정답이 여러 개라면 일부만 입력해도 정답 처리
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
# 키보드 및 입력창 포커스
# =========================================================

def install_keyboard_handler() -> None:
    """
    새 문제에서 입력창에 자동 포커스를 주고,
    입력창 밖에서도 Enter로 버튼을 누르게 한다.
    """
    components.html(
        """
        <script>
        const parentWindow = window.parent;
        const parentDocument = parentWindow.document;

        function findAnswerInput() {
            const inputs = parentDocument.querySelectorAll(
                'input[aria-label="뜻을 입력하세요"]'
            );

            if (inputs.length === 0) {
                return null;
            }

            return inputs[inputs.length - 1];
        }

        function focusAnswerInput() {
            const input = findAnswerInput();

            if (!input || input.disabled) {
                return false;
            }

            input.focus({
                preventScroll: true
            });

            // 커서를 입력값 마지막으로 이동
            const valueLength = input.value.length;

            try {
                input.setSelectionRange(
                    valueLength,
                    valueLength
                );
            } catch (error) {
                // 일부 브라우저에서 setSelectionRange가 실패해도 무시
            }

            return parentDocument.activeElement === input;
        }

        /*
        Streamlit이 rerun된 직후에는 입력창이 아직 생성되지 않을 수 있으므로
        MutationObserver와 반복 탐색을 함께 사용한다.
        */
        if (parentWindow.quizFocusObserver) {
            parentWindow.quizFocusObserver.disconnect();
        }

        let focusAttempts = 0;

        const tryFocus = () => {
            const focused = focusAnswerInput();
            focusAttempts += 1;

            if (focused || focusAttempts >= 30) {
                clearInterval(parentWindow.quizFocusTimer);

                if (parentWindow.quizFocusObserver) {
                    parentWindow.quizFocusObserver.disconnect();
                }
            }
        };

        clearInterval(parentWindow.quizFocusTimer);

        parentWindow.quizFocusTimer = setInterval(
            tryFocus,
            100
        );

        parentWindow.quizFocusObserver = new MutationObserver(
            tryFocus
        );

        parentWindow.quizFocusObserver.observe(
            parentDocument.body,
            {
                childList: true,
                subtree: true
            }
        );

        // 즉시 한 번 시도
        setTimeout(tryFocus, 0);

        /*
        이전 iframe에서 등록했던 Enter 이벤트를 제거한 뒤
        현재 이벤트를 다시 등록한다.
        */
        if (parentWindow.quizEnterHandler) {
            parentDocument.removeEventListener(
                "keydown",
                parentWindow.quizEnterHandler,
                true
            );
        }

        parentWindow.quizEnterHandler = function(event) {
            if (event.key !== "Enter") {
                return;
            }

            // 한글 조합 중 Enter는 무시
            if (
                event.isComposing
                || event.keyCode === 229
            ) {
                return;
            }

            // Shift + Enter 등의 조합키는 무시
            if (
                event.shiftKey
                || event.ctrlKey
                || event.altKey
                || event.metaKey
            ) {
                return;
            }

            const target = event.target;
            const targetTag = target?.tagName;

            /*
            입력창에 포커스가 있을 때는 Streamlit form의
            기본 Enter 제출 기능을 사용한다.
            */
            if (
                targetTag === "INPUT"
                || targetTag === "TEXTAREA"
            ) {
                return;
            }

            const buttons = parentDocument.querySelectorAll(
                "button"
            );

            for (const button of buttons) {
                if (button.disabled) {
                    continue;
                }

                const buttonText = button.innerText.trim();

                if (
                    buttonText.includes("정답 확인")
                    || buttonText.includes("다음 문제")
                ) {
                    event.preventDefault();
                    event.stopPropagation();
                    button.click();
                    break;
                }
            }
        };

        parentDocument.addEventListener(
            "keydown",
            parentWindow.quizEnterHandler,
            true
        );
        </script>
        """,
        height=0,
    )


# =========================================================
# 공통 화면 요소
# =========================================================

def show_result_message() -> None:
    """채점 결과 메시지를 표시한다."""
    if not st.session_state.result:
        return

    message, message_type = st.session_state.result

    if message_type == "success":
        st.success(message)

    elif message_type == "error":
        st.error(message)

    else:
        st.info(message)


# =========================================================
# 메인 화면
# =========================================================

def show_main_screen(
    days: dict[str, pd.DataFrame],
) -> None:
    """Day 선택 화면을 표시한다."""
    st.subheader("학습할 Day를 선택하세요")

    day_names = list(days.keys())

    for start_index in range(
        0,
        len(day_names),
        3,
    ):
        columns = st.columns(3)

        current_days = day_names[
            start_index:start_index + 3
        ]

        for column, day_name in zip(
            columns,
            current_days,
        ):
            with column:
                if st.button(
                    f"{day_name}\n\n"
                    f"{len(days[day_name])}단어",
                    key=f"day_button_{start_index}_{day_name}",
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
        key="all_days_button",
        use_container_width=True,
    ):
        start_quiz(
            "전체 Day",
            all_words,
        )
        st.rerun()

    st.caption(
        "엑셀 오른쪽에 영어와 한글 열을 두 개씩 추가하면 "
        "새로운 Day가 자동으로 생성됩니다."
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

    st.write(
        f"정답률: **{accuracy:.1f}%**"
    )

    st.write(
        f"틀린 문제: **{wrong_count}개**"
    )

    retry_column, wrong_column, main_column = (
        st.columns(3)
    )

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

def show_quiz_header(
    index: int,
    total_count: int,
) -> None:
    """퀴즈 화면 상단을 표시한다."""
    left_column, center_column, right_column = (
        st.columns([1, 2, 1])
    )

    with left_column:
        if st.button(
            "메인 화면",
            key="quiz_main_button",
        ):
            clear_quiz_state()
            st.rerun()

    with center_column:
        day_name = (
            st.session_state.current_day_name
        )

        st.markdown(
            f"""
            <h4 style="text-align:center;">
                {day_name}
            </h4>
            """,
            unsafe_allow_html=True,
        )

    with right_column:
        st.write(
            f"{index + 1} / {total_count}"
        )


def show_quiz_screen() -> None:
    """현재 문제와 답안 입력창을 표시한다."""
    df = st.session_state.df
    index = st.session_state.current_index
    total_count = len(df)

    if index >= total_count:
        show_complete_screen()
        return

    row = df.iloc[index]

    show_quiz_header(
        index,
        total_count,
    )

    st.divider()

    st.markdown(
        f"""
        <h1 style="text-align:center;">
            {row["eng"]}
        </h1>
        """,
        unsafe_allow_html=True,
    )

    form_key = (
        f"quiz_form_"
        f"{index}_"
        f"{st.session_state.answered}_"
        f"{st.session_state.input_version}"
    )

    input_key = (
        f"answer_input_"
        f"{index}_"
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
            key=input_key,
            placeholder=(
                "뜻을 입력한 후 Enter를 누르세요"
            ),
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

current_file_hash = hashlib.sha256(
    file_bytes
).hexdigest()


# 새로운 엑셀 파일이 업로드되면 기존 퀴즈 초기화
if (
    st.session_state.file_hash
    != current_file_hash
):
    clear_quiz_state()

    st.session_state.file_hash = (
        current_file_hash
    )


try:
    days = load_all_days(file_bytes)

except Exception as error:
    st.error(
        "엑셀 파일을 불러오는 중 "
        "오류가 발생했습니다."
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
